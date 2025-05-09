"""Test harness for OpenMAS agents.

This module provides utilities for testing OpenMAS agents, making it easier
to initialize, run, and interact with agents during tests.
"""

import asyncio
import contextlib
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypedDict, TypeVar

from openmas.agent.base import BaseAgent
from openmas.assets.manager import AssetManager
from openmas.config import AgentConfig
from openmas.logging import get_logger
from openmas.testing.mock_communicator import MockCommunicator

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseAgent)


class AgentTestContext(TypedDict, total=False):
    """Context object for agent test scenarios."""

    agent: BaseAgent
    communicator: MockCommunicator
    test_data: Dict[str, Any]


class AgentTestHarness(Generic[T]):
    """Test harness for OpenMAS agents.

    This class provides a convenient way to test OpenMAS agents by:
    1. Simplifying agent initialization with test configuration
    2. Managing agent lifecycle (start/stop) within test contexts
    3. Facilitating simulated communication and state assertions
    4. Providing utilities for multi-agent testing

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
        project_root: Optional[Path] = None,
        communicator_class: Optional[Type[Any]] = None,
        communicator_kwargs: Optional[Dict[str, Any]] = None,
        agent_init_kwargs: Optional[Dict[str, Any]] = None,
        default_asset_manager: Optional[AssetManager] = None,
    ):
        """Initialize the agent test harness.

        Args:
            agent_class: The agent class to test (a subclass of BaseAgent)
            default_config: Default configuration values for test agents
            config_model: The configuration model class to use
            project_root: The project root directory to pass to agents (for prompt/template resolution)
            communicator_class: The communicator class to use for agents (default: MockCommunicator)
            communicator_kwargs: Additional kwargs to pass to communicator constructor
            agent_init_kwargs: Additional kwargs to pass to agent constructor
            default_asset_manager: Default AssetManager instance to use for all agents
        """
        self.agent_class = agent_class
        self.default_config = default_config or {}
        self.config_model = config_model
        self.project_root = project_root or Path.cwd()
        self.default_asset_manager = default_asset_manager

        self._harness_communicator_class = communicator_class or MockCommunicator
        self._harness_communicator_kwargs = communicator_kwargs or {}
        self.agent_init_kwargs = agent_init_kwargs or {}

        # For multi-agent testing
        self.agents: List[T] = []
        self.communicators: Dict[str, Any] = {}

        self.logger = logger.bind(agent_class=agent_class.__name__, harness_id=id(self))
        self.logger.debug("Initialized agent test harness")

    def _get_communicator_for_creation(self, agent_name: str, agent_config_obj: AgentConfig) -> Any:
        """Get a communicator instance for the agent.

        Creates and returns a communicator instance for the agent.
        The communicator type is determined by the harness configuration,
        and it's initialized with the agent's specific AgentConfig and any
        additional harness-level communicator kwargs.
        """
        communicator_instance = self._harness_communicator_class(
            agent_name=agent_name, config=agent_config_obj, **self._harness_communicator_kwargs
        )
        return communicator_instance

    async def create_agent(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        env_prefix: str = "",
        track: bool = True,
        use_real_communicator: bool = False,
        asset_manager: Optional[AssetManager] = None,
    ) -> T:
        """Create an agent instance with the configured communicator.

        Args:
            name: The name of the agent (overrides config)
            config: The agent configuration (overrides default_config)
            env_prefix: Optional prefix for environment variables
            track: Whether to track this agent for multi-agent testing (default: True)
            use_real_communicator: If True, use the communicator type specified in the config
                                  instead of overriding with the harness communicator (default: False)
            asset_manager: Optional AssetManager instance (overrides default_asset_manager)

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
        agent_config = self.config_model(**merged_config)

        # Determine which asset manager to use
        effective_asset_manager = asset_manager or self.default_asset_manager

        # Create the agent with the config - cast to silence mypy
        agent = self.agent_class(
            config=agent_config,  # type: ignore
            env_prefix=env_prefix,
            project_root=self.project_root,
            asset_manager=effective_asset_manager,
            **self.agent_init_kwargs,
        )

        # Use the harness-configured communicator unless use_real_communicator is True
        if not use_real_communicator:
            agent_communicator = self._get_communicator_for_creation(agent.name, agent_config)
            agent.communicator = agent_communicator
            if track:
                self.agents.append(agent)
                self.communicators[agent.name] = agent_communicator
        elif track:
            self.agents.append(agent)

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

    @contextlib.asynccontextmanager
    async def running_agents(self, *agents: T) -> Any:
        """Run multiple agents simultaneously within a single context.

        Args:
            *agents: The agents to run

        Yields:
            The list of running agents
        """
        try:
            for agent in agents:
                await self.start_agent(agent)
            yield list(agents)
        finally:
            for agent in reversed(agents):  # Stop in reverse order
                try:
                    await self.stop_agent(agent)
                except Exception as e:
                    self.logger.warning(f"Error stopping agent {agent.name}: {e}")

    async def link_agents(self, *agents: T) -> None:
        """Link multiple agents together for direct communication.

        This method:
        1. Updates each agent's service_urls to know about the others
        2. Links their mock communicators for direct message passing

        Args:
            *agents: The agents to link
        """
        if len(agents) < 2:
            raise ValueError("At least two agents are required for linking")

        # Update service URLs
        for agent in agents:
            for other in agents:
                if agent != other:
                    # Update the agent config's service URLs
                    agent.config.service_urls[other.name] = f"mock://{other.name}"

                    # Check if communicator is a MockCommunicator before setting its service_urls
                    if isinstance(agent.communicator, MockCommunicator):
                        agent.communicator.service_urls[other.name] = f"mock://{other.name}"

        # Link communicators
        for i, agent in enumerate(agents):
            for j in range(i + 1, len(agents)):
                other = agents[j]
                # Type check to ensure we're working with MockCommunicator
                if not isinstance(agent.communicator, MockCommunicator) or not isinstance(
                    other.communicator, MockCommunicator
                ):
                    raise TypeError("Both agents must use MockCommunicator for linking")
                # Safe to call link_communicator after type check
                agent.communicator.link_communicator(other.communicator)

        self.logger.debug(f"Linked {len(agents)} agents for direct communication")

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
        # Get the agent's communicator
        communicator = agent.communicator
        if not isinstance(communicator, MockCommunicator):
            raise TypeError(f"Agent {agent.name} does not have a MockCommunicator")

        result = await communicator.trigger_handler(method, params)
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

    def verify_all_communicators(self) -> None:
        """Verify all expectations for all tracked communicators.

        Useful for multi-agent test scenarios to ensure all expected
        communications across all agents were met.

        Raises:
            AssertionError: If any communicator has unmet expectations
        """
        errors = []
        for name, comm in self.communicators.items():
            try:
                comm.verify_all_expectations_met()
            except AssertionError as e:
                errors.append(f"Agent '{name}': {str(e)}")

        if errors:
            raise AssertionError("Unmet expectations:\n" + "\n".join(errors))

    def reset(self) -> None:
        """Reset the harness state.

        This clears tracked agents and resets all communicators.
        Useful between tests when reusing the same harness.
        """
        for comm in self.communicators.values():
            comm.reset()

        self.agents = []
        self.communicators = {}
        self.logger.debug("Reset test harness state")

    async def send_request(
        self,
        sender_agent: T,
        target_agent_name: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[Any]] = None,
    ) -> Any:
        """Send a request from one agent to another.

        This is a convenience method for testing inter-agent communication.
        It sets up the necessary mock expectations and sends the request.

        Args:
            sender_agent: The agent sending the request
            target_agent_name: The name of the target agent
            method: The method to call on the target agent
            params: The parameters to pass to the method
            response_model: Optional Pydantic model to validate and parse the response

        Returns:
            The response from the target agent

        Raises:
            ValueError: If the target agent is not found in the communicators
        """
        # Get the target agent's communicator
        if target_agent_name not in self.communicators:
            raise ValueError(f"Target agent '{target_agent_name}' not found in communicators")

        target_comm = self.communicators[target_agent_name]
        sender_comm = sender_agent.communicator

        if not isinstance(sender_comm, MockCommunicator) or not isinstance(target_comm, MockCommunicator):
            raise TypeError("Both sender and target must use MockCommunicator")

        # Make sure the sender and target are linked
        if target_agent_name not in sender_comm.service_urls:
            raise ValueError(f"Agent {sender_agent.name} is not linked to {target_agent_name}")

        # If target has a handler for the method, prepare to route the request
        if method in target_comm._handlers:
            handler = target_comm._handlers[method]

            # Create a response message
            response = await handler(
                {
                    "sender_id": sender_agent.name,
                    "recipient_id": target_agent_name,
                    "content": params or {},
                    "message_type": method,
                }
            )

            return response
        else:
            raise ValueError(f"Target agent does not have a handler for method '{method}'")
