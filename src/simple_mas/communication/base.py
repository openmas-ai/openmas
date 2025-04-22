"""Base communicator interface for SimpleMAS."""

import abc
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Registry for communicator plugins
_COMMUNICATOR_REGISTRY: Dict[str, Type["BaseCommunicator"]] = {}


def register_communicator(communicator_type: str, communicator_class: Type["BaseCommunicator"]) -> None:
    """Register a communicator class for a specific type.

    Args:
        communicator_type: The type identifier for the communicator
        communicator_class: The communicator class to register

    Raises:
        ValueError: If the communicator type is already registered
    """
    if communicator_type in _COMMUNICATOR_REGISTRY:
        logger.warning(
            "Communicator type already registered, overwriting",
            communicator_type=communicator_type,
            old_class=_COMMUNICATOR_REGISTRY[communicator_type].__name__,
            new_class=communicator_class.__name__,
        )
    _COMMUNICATOR_REGISTRY[communicator_type] = communicator_class
    logger.debug(
        "Registered communicator",
        communicator_type=communicator_type,
        communicator_class=communicator_class.__name__,
    )


def get_communicator_class(communicator_type: str) -> Type["BaseCommunicator"]:
    """Get a communicator class for a specific type.

    Args:
        communicator_type: The type identifier for the communicator

    Returns:
        The communicator class

    Raises:
        ValueError: If the communicator type is not registered
    """
    if communicator_type not in _COMMUNICATOR_REGISTRY:
        available_types = ", ".join(_COMMUNICATOR_REGISTRY.keys())
        raise ValueError(
            f"Communicator type '{communicator_type}' not registered. " f"Available types: {available_types or 'none'}"
        )
    return _COMMUNICATOR_REGISTRY[communicator_type]


def get_available_communicator_types() -> Dict[str, Type["BaseCommunicator"]]:
    """Get all registered communicator types.

    Returns:
        Dictionary mapping communicator types to their classes
    """
    return _COMMUNICATOR_REGISTRY.copy()


def discover_communicator_plugins() -> None:
    """Discover and register communicator plugins using entry points.

    This function loads communicator plugins that are registered using
    the 'simple_mas.communicators' entry point.
    """
    try:
        # Try to use importlib.metadata (Python 3.8+)
        from importlib.metadata import entry_points

        try:
            # Python 3.10+ style
            eps = entry_points(group="simple_mas.communicators")
        except TypeError:
            # Python 3.8-3.9 style
            eps = entry_points().get("simple_mas.communicators", [])
        for ep in eps:
            try:
                communicator_class = ep.load()
                register_communicator(ep.name, communicator_class)
                logger.debug(f"Loaded communicator plugin from entry point: {ep.name}")
            except Exception as e:
                logger.error(f"Failed to load communicator plugin {ep.name}: {e}")
    except ImportError:
        # Fallback for Python < 3.8
        try:
            import pkg_resources

            for ep in pkg_resources.iter_entry_points("simple_mas.communicators"):
                try:
                    communicator_class = ep.load()
                    register_communicator(ep.name, communicator_class)
                    logger.debug(f"Loaded communicator plugin from entry point: {ep.name}")
                except Exception as e:
                    logger.error(f"Failed to load communicator plugin {ep.name}: {e}")
        except ImportError:
            logger.warning("pkg_resources not available, cannot load plugins from entry points")


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
