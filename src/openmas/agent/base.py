"""Base agent implementation for OpenMAS."""

import abc
import asyncio
from typing import Any, Dict, Optional, Type, Union

from pydantic import ValidationError

from openmas.communication import BaseCommunicator, discover_local_communicators
from openmas.config import AgentConfig, load_config
from openmas.exceptions import ConfigurationError, DependencyError, LifecycleError
from openmas.logging import configure_logging, get_logger

logger = get_logger(__name__)


class BaseAgent(abc.ABC):
    """Base agent class for all OpenMAS agents.

    This class provides the basic structure for agents, including configuration loading,
    communication setup, and lifecycle management.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Union[Dict[str, Any], AgentConfig]] = None,
        config_model: Type[AgentConfig] = AgentConfig,
        communicator_class: Optional[Type[BaseCommunicator]] = None,
        env_prefix: str = "",
    ):
        """Initialize the agent.

        Args:
            name: The name of the agent (overrides config)
            config: The agent configuration (if not provided, will be loaded from environment)
            config_model: The configuration model class to use
            communicator_class: The communicator class to use (overrides config.communicator_type)
            env_prefix: Optional prefix for environment variables
        """
        # Load configuration
        # If config is a dict, convert it to an AgentConfig instance
        # If config is None, load from environment variables
        if config is None:
            self.config = load_config(config_model, env_prefix)
        elif isinstance(config, dict):
            # Add name to the config dictionary if provided
            if name and "name" not in config:
                config["name"] = name
            try:
                self.config = config_model(**config)
            except ValidationError as e:
                error_msg = f"Configuration validation failed: {e}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
        else:
            # config is already an AgentConfig instance
            self.config = config

        # Override name if provided
        if name:
            self.config.name = name

        # Configure logging
        configure_logging(log_level=self.config.log_level)
        self.logger = get_logger(self.__class__.__name__)

        # Discover and create communicator
        # If communicator_class is provided, use it directly
        # Otherwise, look it up based on config.communicator_type
        if communicator_class is None:
            communicator_class = self._get_communicator_class(self.config.communicator_type)

        self.communicator = communicator_class(self.config.name, self.config.service_urls)

        # Internal state
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

        self.logger.info("Initialized agent", agent_name=self.config.name, agent_type=self.__class__.__name__)

    def _get_communicator_class(self, communicator_type: str) -> Type[BaseCommunicator]:
        """Get the communicator class for the specified type.

        This method uses the lazy-loading mechanism to find communicator classes without
        importing unnecessary dependencies.

        Args:
            communicator_type: The type identifier for the communicator

        Returns:
            The communicator class

        Raises:
            ConfigurationError: If the communicator type cannot be found
            DependencyError: If the communicator requires an optional dependency that is not installed
        """
        try:
            # First try to get using our lazy loading mechanism
            from openmas.communication import get_communicator_by_type

            return get_communicator_by_type(communicator_type)
        except DependencyError as e:
            # This is a special error case for missing optional dependencies - propagate it
            # with the helpful installation instructions already included
            self.logger.error(f"Missing dependency for communicator type '{communicator_type}': {str(e)}")
            raise
        except ValueError:
            # If not found, check extension/plugin paths (extension_paths is deprecated
            # but supported for backwards compatibility)
            check_paths = self.config.plugin_paths or self.config.extension_paths
            if check_paths:
                discover_local_communicators(check_paths)
                try:
                    # Try again after discovering local communicators
                    from openmas.communication import get_communicator_by_type

                    return get_communicator_by_type(communicator_type)
                except DependencyError as e:
                    # This is a special error case for missing optional dependencies
                    self.logger.error(f"Missing dependency for communicator type '{communicator_type}': {str(e)}")
                    raise
                except ValueError:
                    pass

            # If we get here, the communicator type is not found
            from openmas.communication.base import _COMMUNICATOR_REGISTRY

            available_types = ", ".join(sorted(list(_COMMUNICATOR_REGISTRY.keys())))
            available = available_types or "none"
            message = (
                f"Communicator type '{communicator_type}' not found. "
                f"Available types: {available}. "
                f"Check your configuration or provide a valid communicator_class."
            )
            self.logger.error(message)
            raise ConfigurationError(message)

    @property
    def name(self) -> str:
        """Get the agent name."""
        return self.config.name

    def set_communicator(self, communicator: BaseCommunicator) -> None:
        """Set the communicator for this agent.

        This method allows changing the communicator after agent initialization.

        Args:
            communicator: The communicator to use
        """
        self.communicator = communicator
        self.logger.info("Set communicator", agent_name=self.name, communicator_type=communicator.__class__.__name__)

    async def start(self) -> None:
        """Start the agent.

        This method initializes the agent, sets up the communicator, and starts the main loop.
        """
        if self._is_running:
            raise LifecycleError("Agent is already running")

        self.logger.info("Starting agent", agent_name=self.name)

        # Start the communicator
        await self.communicator.start()

        # Call setup hook
        await self.setup()

        # Start the main loop
        self._is_running = True
        self._task = asyncio.create_task(self._run_lifecycle())

        self.logger.info("Agent started", agent_name=self.name)

    async def stop(self) -> None:
        """Stop the agent.

        This method stops the main loop, calls the shutdown hook, and stops the communicator.
        """
        if not self._is_running:
            return

        self.logger.info("Stopping agent", agent_name=self.name)

        # Cancel the main loop task
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Call shutdown hook
        await self.shutdown()

        # Stop the communicator
        await self.communicator.stop()

        self._is_running = False
        self.logger.info("Agent stopped", agent_name=self.name)

    async def _run_lifecycle(self) -> None:
        """Run the agent lifecycle.

        This method runs the main loop and handles exceptions.
        """
        try:
            await self.run()
        except asyncio.CancelledError:
            self.logger.info("Agent lifecycle cancelled", agent_name=self.name)
            raise
        except Exception as e:
            self.logger.exception("Error in agent lifecycle", agent_name=self.name, error=str(e))
            raise

    @abc.abstractmethod
    async def setup(self) -> None:
        """Set up the agent.

        This method is called when the agent starts and can be used to initialize
        resources, register handlers, etc.
        """
        pass

    @abc.abstractmethod
    async def run(self) -> None:
        """Run the agent's main loop.

        This method should implement the agent's core logic. It will be called
        after setup() and should run until the agent is stopped.
        """
        pass

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """Shut down the agent.

        This method is called when the agent stops and can be used to clean up
        resources, close connections, etc.
        """
        pass
