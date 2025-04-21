"""Base communicator interface for SimpleMAS."""

import abc
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseCommunicator(abc.ABC):
    """Abstract base class for all communicators.

    Communicators handle the communication between agents and services.
    """

    def __init__(self, agent_name: str, service_urls: Dict[str, str]):
        """Initialize the communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs
        """
        self.agent_name = agent_name
        self.service_urls = service_urls
        logger.debug(
            "Initialized communicator",
            communicator_type=self.__class__.__name__,
            agent_name=agent_name,
            services=list(service_urls.keys()),
        )

    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        pass

    @abc.abstractmethod
    async def start(self) -> None:
        """Start the communicator.

        This method is called when the agent starts and can be used to initialize connections.
        """
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop the communicator.

        This method is called when the agent stops and can be used to clean up connections.
        """
        pass
