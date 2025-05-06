"""Base communicator interface for OpenMAS."""

# mypy: disable-error-code="assignment"

import abc
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from openmas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Registry for communicator extensions
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
        available = available_types or "none"
        message = f"Communicator type '{communicator_type}' not registered. " f"Available types: {available}"
        raise ValueError(message)
    return _COMMUNICATOR_REGISTRY[communicator_type]


def get_available_communicator_types() -> Dict[str, Type["BaseCommunicator"]]:
    """Get all registered communicator types.

    Returns:
        Dictionary mapping communicator types to their classes
    """
    return _COMMUNICATOR_REGISTRY.copy()


def load_local_communicator(module_path: str, communicator_type: str) -> None:
    """Load a communicator from a local module path.

    This function attempts to import a module at the given path and
    register any BaseCommunicator subclasses found in it.

    Args:
        module_path: The dotted path to the module to import
        communicator_type: The type to register the communicator as

    Raises:
        ImportError: If the module cannot be imported
        ValueError: If no BaseCommunicator subclass is found in the module
    """
    try:
        import importlib
        import inspect

        # Import the module
        module = importlib.import_module(module_path)

        # Find all BaseCommunicator subclasses in the module
        communicator_classes = []
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, BaseCommunicator) and obj is not BaseCommunicator:
                communicator_classes.append(obj)

        if not communicator_classes:
            raise ValueError(f"No BaseCommunicator subclass found in module: {module_path}")

        # Use the first communicator class found
        communicator_class = communicator_classes[0]
        register_communicator(communicator_type, communicator_class)
        logger.debug(
            "Loaded local communicator",
            module_path=module_path,
            communicator_type=communicator_type,
            communicator_class=communicator_class.__name__,
        )
        return
    except ImportError as e:
        logger.error(f"Failed to import module {module_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading communicator from {module_path}: {e}")
        raise


def discover_local_communicators(extension_paths: list[str]) -> None:
    """Discover and register communicator extensions from local extensions.

    This function searches the provided paths for communicator implementations
    and registers them. It assumes that sys.path has already been set up
    correctly to include these paths.

    The precedence is handled by the register_communicator function, which
    logs a warning when overwriting an existing communicator and follows the
    precedence order: built-ins -> extensions -> packages.

    Args:
        extension_paths: List of paths to search for extensions
    """
    import importlib.util
    import os

    logger.debug("Discovering local communicators", extension_paths=extension_paths)

    for base_path in extension_paths:
        try:
            if not base_path:
                logger.warning("Empty extension path provided, skipping")
                continue

            # Convert to absolute path if it's not already
            abs_path = os.path.abspath(base_path)

            # Check if the path exists
            if not os.path.exists(abs_path):
                logger.warning(f"Extension path does not exist: {abs_path}")
                continue

            logger.debug(f"Searching for communicators in: {abs_path}")

            # Walk through the directory looking for Python files
            for root, _, files in os.walk(abs_path):
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, abs_path)
                        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")

                        # Try to import the module and look for communicator classes
                        try:
                            logger.debug(f"Examining potential communicator module: {module_name} at {file_path}")
                            spec = importlib.util.spec_from_file_location(module_name, file_path)
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                try:
                                    spec.loader.exec_module(module)
                                except Exception as e:
                                    logger.error(f"Error loading module {module_name}: {str(e)}", exc_info=True)
                                    continue

                                # Check if any BaseCommunicator subclasses exist in the module
                                found_communicator = False
                                for item_name in dir(module):
                                    item = getattr(module, item_name)
                                    if (
                                        isinstance(item, type)
                                        and issubclass(item, BaseCommunicator)
                                        and item is not BaseCommunicator
                                    ):
                                        # Use the module name as the communicator type
                                        communicator_type = module_name.split(".")[-1]
                                        register_communicator(communicator_type, item)
                                        logger.debug(
                                            "Registered local communicator",
                                            communicator_type=communicator_type,
                                            communicator_class=item.__name__,
                                            file_path=file_path,
                                        )
                                        found_communicator = True

                                if found_communicator:
                                    logger.info(f"Loaded communicator(s) from {file_path}")
                        except ImportError as e:
                            logger.error(
                                f"Import error loading module {module_name} from {file_path}: {str(e)}", exc_info=True
                            )
                        except Exception as e:
                            logger.error(
                                f"Unexpected error loading module {module_name} from {file_path}: {str(e)}",
                                exc_info=True,
                            )
        except Exception as e:
            logger.error(f"Error processing extension path {base_path}: {str(e)}", exc_info=True)


def discover_communicator_extensions() -> None:
    """Discover and register communicator extensions using entry points.

    This function loads communicator extensions that are registered using
    the 'openmas.communicators' entry point.
    """
    try:
        # Try to use importlib.metadata (Python 3.8+)
        import importlib.metadata

        # Try different ways to get entry points based on Python version
        try:
            # Python 3.10+ style with explicit group parameter
            entry_points = importlib.metadata.entry_points(group="openmas.communicators")
            # Process each entry point
            for ep in entry_points:
                try:
                    communicator_class = ep.load()
                    register_communicator(ep.name, communicator_class)
                    logger.debug(f"Loaded communicator extension from entry point: {ep.name}")
                except Exception as e:
                    logger.error(f"Failed to load communicator extension {ep.name}: {e}")
        except (TypeError, AttributeError):
            # Fallback for Python 3.8-3.9
            try:
                # Try to get entry_points as a dict-like object
                entry_points_collection = importlib.metadata.entry_points()

                # Handle different return types from entry_points()
                try:
                    # Try the get method if available
                    if hasattr(entry_points_collection, "get"):
                        # type: ignore[arg-type]
                        entry_points = entry_points_collection.get("openmas.communicators", [])
                        # No type checking here, just iterate
                        for ep in entry_points:
                            if hasattr(ep, "load") and hasattr(ep, "name"):
                                try:
                                    communicator_class = ep.load()
                                    register_communicator(ep.name, communicator_class)  # type: ignore[assignment]
                                    logger.debug(f"Loaded communicator extension from entry point: {ep.name}")
                                except Exception as e:
                                    logger.error(f"Failed to load communicator extension {ep.name}: {e}")
                    else:
                        # It's probably an iterable - filter by group
                        for ep in entry_points_collection:
                            if hasattr(ep, "group") and getattr(ep, "group") == "openmas.communicators":
                                if hasattr(ep, "load") and hasattr(ep, "name"):
                                    try:
                                        communicator_class = ep.load()
                                        register_communicator(ep.name, communicator_class)
                                        logger.debug(f"Loaded communicator extension from entry point: {ep.name}")
                                    except Exception as e:
                                        logger.error(f"Failed to load communicator extension {ep.name}: {e}")
                except Exception as e:
                    logger.error(f"Failed to process entry points: {e}")
            except Exception as e:
                logger.error(f"Failed to get entry points: {e}")
    except ImportError:
        # Fallback for Python < 3.8 - Use pkg_resources
        # This avoids any type checking between incompatible EntryPoint types
        try:
            import pkg_resources

            # Load from pkg_resources directly
            for ep in pkg_resources.iter_entry_points("openmas.communicators"):
                try:
                    # pkg_resources EntryPoints are different from importlib.metadata.EntryPoint
                    # but they have compatible interfaces
                    communicator_class = ep.load()  # type: ignore
                    register_communicator(ep.name, communicator_class)  # type: ignore[assignment]
                    logger.debug(f"Loaded communicator extension from entry point: {ep.name}")
                except Exception as e:
                    logger.error(f"Failed to load communicator extension {ep.name}: {e}")
        except ImportError:
            logger.warning("pkg_resources not available, cannot load extensions from entry points")


class BaseCommunicator(abc.ABC):
    """Abstract base class for all communicators.

    Communicators handle the communication between agents and services.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        server_instructions: Optional[str] = None,
        service_args: Optional[Dict[str, List[str]]] = None,
        port: Optional[int] = None,
    ):
        """Initialize the communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs
            server_mode: Whether to run in server mode
            server_instructions: Instructions for the server
            service_args: Additional arguments for each service
            port: Port for HTTP-based communicators
        """
        self.agent_name = agent_name
        self.service_urls = service_urls
        # Revert these back to use underscore prefix for internal storage
        self._server_mode = server_mode
        self._server_instructions = server_instructions
        self._service_args = service_args or {}
        self._port = port
        # Placeholder for server status
        self._is_server_running = False

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
