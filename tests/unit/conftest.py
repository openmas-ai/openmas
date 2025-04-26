"""Common fixtures for unit tests."""

from unittest import mock

import pytest

from openmas.agent import BaseAgent
from openmas.config import AgentConfig


@pytest.fixture
def config():
    """Create a basic AgentConfig for testing."""
    return AgentConfig(
        name="test-agent",
        communicator_type="mock",
        service_urls={"service1": "mock://service1"},
    )


@pytest.fixture
def mock_communicator():
    """Create a mock communicator with standard methods."""
    communicator = mock.AsyncMock()
    communicator.agent_name = "test-agent"
    communicator.start = mock.AsyncMock()
    communicator.stop = mock.AsyncMock()
    communicator.send_request = mock.AsyncMock(return_value={"result": "success"})
    communicator.send_notification = mock.AsyncMock()
    communicator.register_handler = mock.AsyncMock()
    communicator._is_started = False
    return communicator


class SimpleAgent(BaseAgent):
    """A simple agent implementation for testing."""

    def __init__(self, config: AgentConfig):
        """Initialize the agent with a config."""
        # Pass the config directly to the parent class, ensuring it won't try to load from env
        super().__init__(config=config)
        # Default test values
        self.run_duration = 0.1
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False

    async def setup(self) -> None:
        """Setup the agent."""
        self.setup_called = True
        await super().setup()

    async def run(self) -> None:
        """Run the agent's main logic."""
        self.run_called = True
        await super().run()

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.shutdown_called = True
        await super().shutdown()


@pytest.fixture
def simple_agent(config, mock_communicator):
    """Create a simple agent with mocked components."""
    agent = SimpleAgent(config)
    agent.set_communicator(mock_communicator)
    return agent
