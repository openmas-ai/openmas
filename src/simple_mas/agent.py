"""Base agent implementation for SimpleMAS."""

import abc
import asyncio
from typing import Optional, Type

from simple_mas.communication import BaseCommunicator, get_available_communicator_types, get_communicator_class
from simple_mas.config import AgentConfig, load_config
from simple_mas.exceptions import ConfigurationError, LifecycleError
from simple_mas.logging import configure_logging, get_logger

logger = get_logger(__name__)


class BaseAgent(abc.ABC):
    """Base agent class for all SimpleMAS agents.

    This class provides the basic structure for agents, including configuration loading,
    communication setup, and lifecycle management.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        config_model: Type[AgentConfig] = AgentConfig,
        communicator_class: Optional[Type[BaseCommunicator]] = None,
        env_prefix: str = "",
    ):
        """Initialize the agent.

        Args:
            name: The name of the agent (overrides config)
            config: The agent configuration (if not provided, will be loaded from environment)
            config_model: The configuration model class to use
            communicator_class: Optional communicator class to use (overrides config.communicator_type)
            env_prefix: Optional prefix for environment variables

        Raises:
            ConfigurationError: If the specified communicator type is not available
        """
        # Load configuration
        self.config = config or load_config(config_model, env_prefix)

        # Override name if provided
        if name:
            self.config.name = name

        # Configure logging
        configure_logging(log_level=self.config.log_level)
        self.logger = get_logger(self.__class__.__name__)

        # Create communicator
        if communicator_class is not None:
            # Use explicitly provided communicator class
            self.communicator = communicator_class(self.config.name, self.config.service_urls)
            self.logger.debug(
                "Using explicitly provided communicator class", communicator_class=communicator_class.__name__
            )
        else:
            # Use communicator type from config
            try:
                comm_class = get_communicator_class(self.config.communicator_type)

                # Initialize the communicator with required args and any additional options
                self.communicator = comm_class(
                    self.config.name, self.config.service_urls, **self.config.communicator_options
                )

                self.logger.debug(
                    "Using communicator from registry",
                    communicator_type=self.config.communicator_type,
                    communicator_class=comm_class.__name__,
                    communicator_options=self.config.communicator_options,
                )
            except ValueError as e:
                available_types = ", ".join(get_available_communicator_types().keys())
                error_msg = (
                    f"Invalid communicator type '{self.config.communicator_type}'. "
                    f"Available types: {available_types}"
                )
                self.logger.error(error_msg)
                raise ConfigurationError(error_msg) from e
            except Exception as e:
                error_msg = f"Failed to initialize communicator of type '{self.config.communicator_type}': {e}"
                self.logger.error(error_msg)
                raise ConfigurationError(error_msg) from e

        # Internal state
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

        self.logger.info("Initialized agent", agent_name=self.config.name, agent_type=self.__class__.__name__)

    @property
    def name(self) -> str:
        """Get the agent name."""
        return self.config.name

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
