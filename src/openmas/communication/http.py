"""HTTP communicator implementation for OpenMAS."""

import asyncio
import uuid
from typing import Any, Callable, Dict, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

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

    def __init__(self, agent_name: str, service_urls: Dict[str, str]):
        """Initialize the HTTP communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs
        """
        super().__init__(agent_name, service_urls)
        self.client = httpx.AsyncClient(timeout=30.0)
        self.handlers: Dict[str, Callable] = {}
        self.server_task: Optional[asyncio.Task] = None

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
                except ValidationError as e:
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

    async def start(self) -> None:
        """Start the communicator.

        This sets up the HTTP client but doesn't start a server by default.
        Subclasses that need to listen for incoming requests should override this.
        """
        logger.info("Started HTTP communicator")

    async def stop(self) -> None:
        """Stop the communicator.

        This cleans up the HTTP client and stops any server that might be running.
        """
        if self.server_task is not None:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
            self.server_task = None

        await self.client.aclose()
        logger.info("Stopped HTTP communicator")
