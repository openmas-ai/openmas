"""Test harness for SimpleMAS agents.

This module provides utilities for testing SimpleMAS agents, making it easier
to initialize, run, and interact with agents during tests.
"""

import asyncio
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar

from simple_mas.agent.base import BaseAgent
from simple_mas.config import AgentConfig
from simple_mas.logging import get_logger
from simple_mas.testing.mock_communicator import MockCommunicator

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseAgent)


class AgentTestHarness(Generic[T]):
    """Test harness for SimpleMAS agents.

    This class provides a convenient way to test SimpleMAS agents by:
    1. Simplifying agent initialization with test configuration
    2. Managing agent lifecycle (start/stop) within test contexts
    3. Facilitating simulated communication and state assertions

    The harness automatically configures a MockCommunicator to intercept and
    verify all agent communications.

    Example:
        ```python
        # Create a test harness for a specific agent type
        harness = AgentTestHarness(MyAgent)

        # Initialize an agent with test configuration
        agent = await harness.create_agent(name="test-agent")

        # Set up expected service request/response
        harness.communicator.expect_request(
            "external-service", "get_data", {"id": "123"}, {"result": "test-data"}
        )

        # Start the agent (in a managed way)
        async with harness.running_agent(agent):
            # Trigger agent behavior (e.g., by sending a message)
            await harness.trigger_handler(agent, "process_request", {"param": "value"})

            # Agent communicates with "external-service" during processing...

            # Verify all expected communications occurred
            harness.communicator.verify()

            # Assert agent state
            assert agent.some_property == expected_value
        ```
    """

    def __init__(
        self,
        agent_class: Type[T],
        default_config: Optional[Dict[str, Any]] = None,
        config_model: Type[AgentConfig] = AgentConfig,
    ):
        """Initialize the agent test harness.

        Args:
            agent_class: The agent class to test (a subclass of BaseAgent)
            default_config: Default configuration values for test agents
            config_model: The configuration model class to use
        """
        self.agent_class = agent_class
        self.default_config = default_config or {}
        self.config_model = config_model
        self.communicator = MockCommunicator(agent_name="test-agent")

        self.logger = logger.bind(agent_class=agent_class.__name__, harness_id=id(self))

        self.logger.debug("Initialized agent test harness")

    async def create_agent(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        env_prefix: str = "",
    ) -> T:
        """Create an agent instance with a MockCommunicator.

        Args:
            name: The name of the agent (overrides config)
            config: The agent configuration (overrides default_config)
            env_prefix: Optional prefix for environment variables

        Returns:
            An initialized agent instance
        """
        # Merge configurations with precedence: config > default_config
        merged_config = self.default_config.copy()
        if config:
            merged_config.update(config)

        # Set a default name if none provided
        if name:
            merged_config["name"] = name
        elif "name" not in merged_config:
            merged_config["name"] = f"test-agent-{id(self)}"

        # Ensure service_urls is present
        if "service_urls" not in merged_config:
            merged_config["service_urls"] = {}

        # Create a config instance directly
        agent_config = self.config_model(
            name=merged_config["name"],
            service_urls=merged_config.get("service_urls", {}),
            log_level=merged_config.get("log_level", "info"),
            communicator_type=merged_config.get("communicator_type", "mock"),
            communicator_options=merged_config.get("communicator_options", {}),
        )

        # Create the agent with the config - cast to silence mypy
        agent = self.agent_class(
            config=agent_config,  # type: ignore
            env_prefix=env_prefix,
        )

        # Replace the agent's communicator with our mock
        self.communicator = MockCommunicator(agent_name=agent.name)
        agent.communicator = self.communicator

        self.logger.debug("Created test agent", agent_name=agent.name)
        return agent

    async def start_agent(self, agent: T) -> None:
        """Start the agent.

        This method starts the agent and its mock communicator.

        Args:
            agent: The agent to start
        """
        await agent.start()
        self.logger.debug("Started test agent", agent_name=agent.name)

    async def stop_agent(self, agent: T) -> None:
        """Stop the agent.

        This method stops the agent and its mock communicator.

        Args:
            agent: The agent to stop
        """
        await agent.stop()
        self.logger.debug("Stopped test agent", agent_name=agent.name)

    class RunningAgent:
        """Context manager for running an agent during tests."""

        def __init__(self, harness: "AgentTestHarness", agent: BaseAgent) -> None:
            """Initialize the running agent context.

            Args:
                harness: The parent test harness
                agent: The agent to run
            """
            self.harness = harness
            self.agent = agent

        async def __aenter__(self) -> BaseAgent:
            """Start the agent when entering the context.

            Returns:
                The running agent
            """
            await self.harness.start_agent(self.agent)
            return self.agent

        async def __aexit__(
            self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[Any]
        ) -> None:
            """Stop the agent when exiting the context."""
            await self.harness.stop_agent(self.agent)

    def running_agent(self, agent: T) -> RunningAgent:
        """Get a context manager for running an agent during tests.

        This context manager ensures that the agent is properly started and stopped
        even if exceptions occur during the test.

        Args:
            agent: The agent to run

        Returns:
            A context manager that starts and stops the agent
        """
        return self.RunningAgent(self, agent)

    async def trigger_handler(self, agent: T, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Trigger a handler method on the agent.

        This method simulates an incoming request to the agent by triggering
        one of its registered handlers directly.

        Args:
            agent: The agent to test
            method: The handler method name to trigger
            params: The parameters to pass to the handler

        Returns:
            The result of the handler call

        Raises:
            AssertionError: If no handler has been registered for the method
        """
        result = await self.communicator.trigger_handler(method, params)
        self.logger.debug(
            "Triggered handler on test agent",
            agent_name=agent.name,
            method=method,
            params=params,
        )
        return result

    async def wait_for(
        self, condition_func: Callable[[], bool], timeout: float = 1.0, check_interval: float = 0.01
    ) -> bool:
        """Wait for a condition to become true.

        This utility method is useful for tests that need to wait for an asynchronous
        operation to complete before making assertions.

        Args:
            condition_func: A function that returns True when the condition is met
            timeout: Maximum time to wait (in seconds)
            check_interval: How often to check the condition (in seconds)

        Returns:
            True if the condition was met, False if timed out
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if condition_func():
                return True
            await asyncio.sleep(check_interval)
        return False
