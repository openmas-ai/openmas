"""HTTP communicator implementation for OpenMAS."""

import asyncio
import contextlib
import uuid
from typing import Any, Callable, Dict, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from openmas.communication.base import BaseCommunicator
from openmas.exceptions import CommunicationError, MethodNotFoundError, RequestTimeoutError, ServiceNotFoundError
from openmas.exceptions import ValidationError as OpenMasValidationError
from openmas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class HttpCommunicator(BaseCommunicator):
    """HTTP-based communicator implementation.

    This communicator uses HTTP for communication between services.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        port: Optional[int] = None,
        **kwargs: Any,
    ):
        """Initialize the HTTP communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs
            port: Optional port to use for the server (default is determined by configuration)
        """
        super().__init__(agent_name, service_urls)
        self.client = httpx.AsyncClient(timeout=30.0)
        self.handlers: Dict[str, Callable] = {}
        self.server_task: Optional[asyncio.Task] = None
        self.port = port

        # Check communicator options for the port if not explicitly provided
        if self.port is None and kwargs.get("communicator_options"):
            self.port = kwargs.get("communicator_options", {}).get("port")

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

        url = self.service_urls[target_service]
        request_id = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}

        logger.debug("Sending request", target=target_service, method=method, request_id=request_id)

        try:
            response = await self.client.post(url, json=payload, timeout=timeout or self.client.timeout.read)
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                error = result["error"]
                error_code = error.get("code", 0)
                error_message = error.get("message", "Unknown error")

                if error_code == -32601:  # Method not found
                    raise MethodNotFoundError(
                        f"Method '{method}' not found on service '{target_service}'",
                        target=target_service,
                        details={"method": method, "error": error},
                    )

                raise CommunicationError(
                    f"Error from service '{target_service}': {error_message}",
                    target=target_service,
                    details={"method": method, "error": error},
                )

            if "result" not in result:
                raise CommunicationError(
                    f"Invalid response from service '{target_service}': missing 'result'",
                    target=target_service,
                    details={"method": method, "response": result},
                )

            response_data = result["result"]

            # Validate the response if a model was provided
            if response_model is not None:
                try:
                    return response_model.model_validate(response_data)
                except PydanticValidationError as e:
                    raise OpenMasValidationError(f"Response validation failed: {e}")

            return response_data

        except httpx.TimeoutException:
            raise RequestTimeoutError(
                f"Request to '{target_service}' timed out", target=target_service, details={"method": method}
            )
        except httpx.HTTPStatusError as e:
            raise CommunicationError(
                f"HTTP error from '{target_service}': {e.response.status_code} {e.response.reason_phrase}",
                target=target_service,
                details={"method": method, "status_code": e.response.status_code},
            )
        except httpx.HTTPError as e:
            raise CommunicationError(
                f"HTTP error from '{target_service}': {str(e)}", target=target_service, details={"method": method}
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

        url = self.service_urls[target_service]
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}

        logger.debug("Sending notification", target=target_service, method=method)

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise CommunicationError(
                f"HTTP error from '{target_service}': {str(e)}", target=target_service, details={"method": method}
            )

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self.handlers[method] = handler
        logger.debug("Registered handler", method=method)

        # If we have handlers and no server is running, start the server
        if self.handlers and self.server_task is None:
            await self._ensure_server_running()

    async def _ensure_server_running(self) -> None:
        """Ensure the server is running if needed.

        This method starts a FastAPI server if the communicator has registered handlers
        and no server is currently running.
        """
        if self.server_task is None and self.handlers:
            logger.debug("Starting HTTP server")
            try:
                import uvicorn
                from fastapi import FastAPI, Request, Response
                from fastapi.responses import JSONResponse

                # Get port from agent config
                agent_name = self.agent_name
                port = self.port

                # Default port if not specified
                if port is None:
                    # Try to extract port from the current hostname if this agent is in service_urls
                    if agent_name in self.service_urls:
                        url = self.service_urls[agent_name]
                        try:
                            import re

                            port_match = re.search(r":(\d+)", url)
                            if port_match:
                                port = int(port_match.group(1))
                        except Exception as e:
                            logger.debug(f"Could not extract port from URL: {e}")

                # Fall back to a default port if still none
                if port is None:
                    # Hard-coded fallback as a last resort
                    if agent_name == "consumer":
                        port = 8082  # For example, consumer agents use port 8082
                    elif agent_name == "producer":
                        port = 8081  # For example, producer agents use port 8081
                    else:
                        # This is a reasonable fallback, but may collide with other services
                        port = 8000

                # Update the instance port attribute with the determined value
                self.port = port
                logger.debug(f"Using port {port} for HTTP server")

                # Create FastAPI app
                app = FastAPI(title=f"{agent_name}-api")

                @app.post("/")  # type: ignore[misc]
                async def handle_jsonrpc(request: Request) -> Response:
                    """Handle JSON-RPC requests."""
                    try:
                        data = await request.json()

                        # Validate request format
                        if "method" not in data:
                            return JSONResponse(
                                content={
                                    "jsonrpc": "2.0",
                                    "error": {"code": -32600, "message": "Invalid request: missing method"},
                                    "id": data.get("id", None),
                                },
                                status_code=400,
                            )

                        method = data["method"]
                        params = data.get("params", {})
                        request_id = data.get("id")

                        # Check if method exists
                        if method not in self.handlers:
                            return JSONResponse(
                                content={
                                    "jsonrpc": "2.0",
                                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                                    "id": request_id,
                                },
                                status_code=404,
                            )

                        # Call the handler
                        handler = self.handlers[method]
                        try:
                            result = await handler(params)
                        except Exception as e:
                            # Convert handler exceptions to JSON-RPC error response
                            logger.exception(f"Handler error: {e}")
                            return JSONResponse(
                                content={
                                    "jsonrpc": "2.0",
                                    "error": {"code": -32000, "message": f"Handler error: {str(e)}"},
                                    "id": request_id,
                                },
                                status_code=500,
                            )

                        # If it's a notification (no ID), return no content
                        if request_id is None:
                            return Response(status_code=204)

                        # Return the result
                        return JSONResponse(content={"jsonrpc": "2.0", "result": result, "id": request_id})
                    except Exception as e:
                        logger.exception(f"Error handling request: {e}")
                        # Return a JSON-RPC error response
                        return JSONResponse(
                            content={
                                "jsonrpc": "2.0",
                                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                                "id": data.get("id", None) if "data" in locals() else None,
                            },
                            status_code=500,
                        )

                # Use the newer FastAPI lifespan API instead of deprecated on_event
                from contextlib import asynccontextmanager
                from typing import AsyncIterator

                @asynccontextmanager
                async def lifespan(app: FastAPI) -> AsyncIterator[None]:
                    """Handle application lifespan events."""
                    # Startup event
                    logger.debug("HTTP server starting up")
                    yield
                    # Shutdown event
                    logger.debug("HTTP server shutting down")

                # Set the lifespan handler for the app
                app.router.lifespan_context = lifespan  # type: ignore[assignment]

                # Create a server config with proper lifespan setting
                config = uvicorn.Config(
                    app=app,
                    host="0.0.0.0",  # Listen on all interfaces
                    port=port,
                    log_level="info",
                    lifespan="on",  # Ensure proper lifespan management
                )

                # Start the server
                server = uvicorn.Server(config)

                # Define an async task to run the server
                async def run_server_task() -> None:
                    """Run the uvicorn server in a controlled way."""
                    try:
                        await server.serve()
                    except asyncio.CancelledError:
                        logger.debug("Server cancelled, shutting down gracefully")
                    except Exception as e:
                        logger.error(f"HTTP server error: {e}")

                # Run the server in a background task
                self.server_task = asyncio.create_task(run_server_task())
                logger.info(f"Started HTTP server on port {port}")
            except ImportError as e:
                logger.error(f"Cannot start HTTP server: missing dependencies: {e}")
                raise CommunicationError(
                    f"Cannot start HTTP server: {e}. "
                    f"Make sure you have fastapi and uvicorn installed: pip install fastapi uvicorn"
                )
            except Exception as e:
                logger.exception(f"Error starting HTTP server: {e}")
                raise CommunicationError(f"Failed to start HTTP server: {e}")

    async def start(self) -> None:
        """Start the communicator.

        This sets up the HTTP client and starts a server if handlers are registered.
        """
        logger.info("Started HTTP communicator")

        # If we have handlers, make sure the server is running
        if self.handlers:
            await self._ensure_server_running()

    async def stop(self) -> None:
        """Stop the communicator.

        This cleans up the HTTP client and stops any server that might be running.
        """
        if self.server_task is not None:
            logger.debug("Stopping HTTP server task")
            try:
                # In tests, we might need special handling
                if hasattr(self.server_task, "_is_coroutine") and self.server_task._is_coroutine is False:
                    # This is a mock, just cancel it and reset
                    self.server_task.cancel()
                    self.server_task = None
                else:
                    # It's a real coroutine/task, cancel and await it
                    self.server_task.cancel()

                    # Use a very short timeout to avoid hanging in tests
                    try:
                        # shield() prevents the wait_for cancellation from propagating to the task
                        # but we still want to give it a chance to clean up properly
                        with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                            await asyncio.wait_for(self.server_task, timeout=0.2)
                    except Exception as e:
                        # Log but don't raise other exceptions during cleanup
                        logger.warning(f"Error while stopping HTTP server: {e}")
            except Exception as e:
                # Handle any errors during task cancellation
                logger.warning(f"Error while stopping HTTP server: {e}")
            finally:
                # Always ensure the task reference is cleared
                self.server_task = None
                logger.debug("HTTP server task stopped")

        # Close the HTTP client
        try:
            await self.client.aclose()
            logger.debug("HTTP client closed")
        except Exception as e:
            logger.warning(f"Error closing HTTP client: {e}")

        logger.info("Stopped HTTP communicator")
