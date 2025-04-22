"""gRPC communicator implementation for SimpleMAS."""

import asyncio
import json
import time
import uuid
from concurrent import futures
from typing import Any, Callable, Dict, Optional, Type, TypeVar

# Import gRPC and protobuf libraries
import grpc
from grpc.aio import server as aio_server
from pydantic import BaseModel, ValidationError

# Import the generated protobuf modules
# Note: These will be generated from the proto file using protoc
# For production, you'd run protoc to generate these files
try:
    from simple_mas.communication.grpc import simple_mas_pb2 as pb2
    from simple_mas.communication.grpc import simple_mas_pb2_grpc as pb2_grpc
except ImportError:
    # This is just to provide linting support while developing
    # In a real installation, these modules will be properly generated
    # by setup.py or a build script
    import sys

    print("Warning: simple_mas_pb2 modules not found - they should be generated from proto files.", file=sys.stderr)

from simple_mas.communication.base import BaseCommunicator
from simple_mas.exceptions import CommunicationError, MethodNotFoundError, RequestTimeoutError, ServiceNotFoundError
from simple_mas.exceptions import ValidationError as SimpleMasValidationError
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class SimpleMasServicer(pb2_grpc.SimpleMasServiceServicer):
    """Implementation of the SimpleMasService gRPC service.

    This servicer handles incoming gRPC requests by delegating them
    to the appropriate handler methods registered with the communicator.
    """

    def __init__(self, communicator: "GrpcCommunicator"):
        """Initialize the gRPC servicer.

        Args:
            communicator: The parent GrpcCommunicator instance
        """
        self.communicator = communicator

    async def SendRequest(self, request: pb2.RequestMessage, context: grpc.aio.ServicerContext) -> pb2.ResponseMessage:
        """Handle a SendRequest RPC call.

        Args:
            request: The request message
            context: The gRPC servicer context

        Returns:
            A ResponseMessage with the result or error
        """
        response = pb2.ResponseMessage()
        response.id = request.id
        response.source = request.target  # Swap source/target for the response
        response.target = request.source
        response.timestamp = int(time.time() * 1000)

        method = request.method

        # Check if we have a handler for this method
        if method in self.communicator.handlers:
            try:
                handler = self.communicator.handlers[method]

                # Parse parameters from JSON
                params = json.loads(request.params) if request.params else {}

                # Call the handler
                result = await handler(**params)

                # Serialize the result
                if isinstance(result, (dict, list)):
                    response.result = json.dumps(result).encode()
                else:
                    response.result = str(result).encode()
            except Exception as e:
                # Create an error response
                response.error.code = 500
                response.error.message = str(e)
                response.error.details = type(e).__name__
        else:
            # Method not found
            response.error.code = 404
            response.error.message = f"Method '{method}' not found"
            response.error.details = "MethodNotFoundError"

        return response

    async def SendNotification(self, request: pb2.NotificationMessage, context: grpc.aio.ServicerContext) -> pb2.Empty:
        """Handle a SendNotification RPC call.

        Args:
            request: The notification message
            context: The gRPC servicer context

        Returns:
            An Empty message
        """
        method = request.method

        # Check if we have a handler for this method
        if method in self.communicator.handlers:
            try:
                handler = self.communicator.handlers[method]

                # Parse parameters from JSON
                params = json.loads(request.params) if request.params else {}

                # Call the handler (don't await the result)
                asyncio.create_task(handler(**params))
            except Exception as e:
                logger.error(
                    "Error handling notification",
                    method=method,
                    error=str(e),
                    error_type=type(e).__name__,
                )
        else:
            logger.warning(
                "Notification for unknown method",
                method=method,
            )

        return pb2.Empty()


class GrpcCommunicator(BaseCommunicator):
    """gRPC-based communicator implementation.

    This communicator uses gRPC for communication between services.
    It can act as both a client (sending requests) and a server (handling requests).
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_address: str = "[::]:50051",
        max_workers: int = 10,
        server_mode: bool = False,
        channel_options: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the gRPC communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to gRPC server addresses
            server_address: The address to bind the gRPC server to (if server_mode is True)
            max_workers: Maximum number of server workers
            server_mode: Whether to start a gRPC server
            channel_options: Optional gRPC channel options
        """
        super().__init__(agent_name, service_urls)

        self.server_address = server_address
        self.max_workers = max_workers
        self.server_mode = server_mode
        self.channel_options = channel_options or {}

        # Initialize client channels and stubs (lazily)
        self._channels: Dict[str, grpc.aio.Channel] = {}
        self._stubs: Dict[str, pb2_grpc.SimpleMasServiceStub] = {}

        # Server state
        self.server = None
        self.servicer = None
        self.handlers: Dict[str, Callable] = {}

        logger.debug(
            "Initialized gRPC communicator",
            agent_name=agent_name,
            server_mode=server_mode,
            server_address=server_address if server_mode else None,
        )

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a target service.

        Args:
            target_service: The name of the service to send the request to
            method: The method to call on the service
            params: The parameters to pass to the method
            response_model: Optional Pydantic model to validate and parse the response
            timeout: Optional timeout in seconds

        Returns:
            The response from the service

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
            ValidationError: If the response validation fails
        """
        if target_service not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{target_service}' not found", target=target_service)

        # Get or create the stub for this service
        stub = await self._get_stub(target_service)

        # Create a request message
        request = pb2.RequestMessage(
            id=str(uuid.uuid4()),
            source=self.agent_name,
            target=target_service,
            method=method,
            params=json.dumps(params) if params else "",
            timestamp=int(time.time() * 1000),
            timeout_ms=int(timeout * 1000) if timeout else 0,
        )

        logger.debug(
            "Sending gRPC request",
            target=target_service,
            method=method,
            request_id=request.id,
        )

        try:
            # Call the service with the given timeout
            rpc_timeout = timeout if timeout else None
            response = await stub.SendRequest(request, timeout=rpc_timeout)

            # Check for errors
            if response.error and response.error.code != 0:
                error_code = response.error.code
                error_message = response.error.message
                error_details = response.error.details

                if error_code == 404:  # Method not found
                    raise MethodNotFoundError(
                        f"Method '{method}' not found on service '{target_service}'",
                        target=target_service,
                        details={"method": method, "error": error_message},
                    )

                raise CommunicationError(
                    f"Error from service '{target_service}': {error_message}",
                    target=target_service,
                    details={"method": method, "error_code": error_code, "error_details": error_details},
                )

            # Parse the response
            if not response.result:
                return None

            try:
                result_data = json.loads(response.result.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If it's not valid JSON, return the raw bytes or decoded string
                try:
                    return response.result.decode()
                except UnicodeDecodeError:
                    return response.result

            # Validate the response if a model was provided
            if response_model is not None:
                try:
                    return response_model.model_validate(result_data)
                except ValidationError as e:
                    raise SimpleMasValidationError(f"Response validation failed: {e}")

            return result_data

        except grpc.RpcError as e:
            if isinstance(e, grpc.Call):
                if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    raise RequestTimeoutError(
                        f"Request to '{target_service}' timed out",
                        target=target_service,
                        details={"method": method},
                    )
                elif e.code() == grpc.StatusCode.UNAVAILABLE:
                    raise ServiceNotFoundError(
                        f"Service '{target_service}' is unavailable",
                        target=target_service,
                        details={"method": method},
                    )

            raise CommunicationError(
                f"gRPC error from '{target_service}': {str(e)}",
                target=target_service,
                details={"method": method},
            )

    async def send_notification(
        self, target_service: str, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification to a target service.

        Args:
            target_service: The name of the service to send the notification to
            method: The method to call on the service
            params: The parameters to pass to the method

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        if target_service not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{target_service}' not found", target=target_service)

        # Get or create the stub for this service
        stub = await self._get_stub(target_service)

        # Create a notification message
        notification = pb2.NotificationMessage(
            source=self.agent_name,
            target=target_service,
            method=method,
            params=json.dumps(params) if params else "",
            timestamp=int(time.time() * 1000),
        )

        logger.debug(
            "Sending gRPC notification",
            target=target_service,
            method=method,
        )

        try:
            # Call the service (don't wait for response)
            await stub.SendNotification(notification)
        except grpc.RpcError as e:
            if isinstance(e, grpc.Call) and e.code() == grpc.StatusCode.UNAVAILABLE:
                raise ServiceNotFoundError(
                    f"Service '{target_service}' is unavailable",
                    target=target_service,
                    details={"method": method},
                )

            raise CommunicationError(
                f"gRPC error from '{target_service}': {str(e)}",
                target=target_service,
                details={"method": method},
            )

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self.handlers[method] = handler
        logger.debug("Registered handler", method=method)

    async def start(self) -> None:
        """Start the gRPC communicator.

        This method starts the gRPC server if server_mode is True,
        and initializes client connections.
        """
        # Start server if in server mode
        if self.server_mode:
            self.servicer = SimpleMasServicer(self)
            self.server = aio_server(futures.ThreadPoolExecutor(max_workers=self.max_workers))
            pb2_grpc.add_SimpleMasServiceServicer_to_server(self.servicer, self.server)
            self.server.add_insecure_port(self.server_address)
            await self.server.start()
            logger.info(
                "Started gRPC server",
                address=self.server_address,
            )

        logger.info("Started gRPC communicator")

    async def stop(self) -> None:
        """Stop the gRPC communicator.

        This method stops the gRPC server if it's running,
        and closes client connections.
        """
        # Stop server if it's running
        if self.server:
            await self.server.stop(grace=1.0)
            self.server = None
            logger.info("Stopped gRPC server")

        # Close all client channels
        for service, channel in self._channels.items():
            await channel.close()
        self._channels.clear()
        self._stubs.clear()

        logger.info("Stopped gRPC communicator")

    async def _get_stub(self, service_name: str) -> pb2_grpc.SimpleMasServiceStub:
        """Get or create a gRPC stub for the given service.

        Args:
            service_name: The name of the service

        Returns:
            A gRPC stub for the service

        Raises:
            ServiceNotFoundError: If the service is not found in service_urls
        """
        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

        # Return existing stub if available
        if service_name in self._stubs:
            return self._stubs[service_name]

        # Create a new channel and stub
        service_url = self.service_urls[service_name]
        channel = grpc.aio.insecure_channel(service_url, options=list(self.channel_options.items()))
        stub = pb2_grpc.SimpleMasServiceStub(channel)

        # Cache them for future use
        self._channels[service_name] = channel
        self._stubs[service_name] = stub

        return stub
