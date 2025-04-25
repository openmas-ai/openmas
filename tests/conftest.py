"""Global test fixtures for OpenMAS tests.

This module contains common fixtures used across multiple test files.
"""

import asyncio
from typing import Any, AsyncGenerator, Dict
from unittest import mock

import pytest

from openmas.agent import BaseAgent
from openmas.agent.bdi import BdiAgent
from openmas.communication.base import _COMMUNICATOR_REGISTRY, register_communicator
from openmas.communication.http import HttpCommunicator
from openmas.config import AgentConfig
from openmas.testing import AgentTestHarness
from openmas.testing.mock_communicator import MockCommunicator

# These registrations can be removed since they're now handled by the fixture below
# register_communicator("mock", MockCommunicator)
# register_communicator("http", HttpCommunicator)


@pytest.fixture(autouse=True, scope="function")
def reset_communicator_registry():
    """Reset the communicator registry before each test and re-register essential communicators.

    This ensures that all tests start with a clean registry and the required communicators.
    """
    # Store original registry to restore after test
    original_registry = _COMMUNICATOR_REGISTRY.copy()

    try:
        # Clear registry and register essential communicators
        _COMMUNICATOR_REGISTRY.clear()
        register_communicator("mock", MockCommunicator)
        register_communicator("http", HttpCommunicator)
        # No need to eagerly register gRPC communicator - it will be loaded lazily if needed
        yield
    finally:
        # Restore original registry after test
        _COMMUNICATOR_REGISTRY.clear()
        _COMMUNICATOR_REGISTRY.update(original_registry)


class SimpleAgent(BaseAgent):
    """A simple agent for testing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False
        self.run_duration = 0.1  # seconds

    async def setup(self) -> None:
        """Set up the agent."""
        self.setup_called = True
        await super().setup()

    async def run(self) -> None:
        """Run the agent."""
        self.run_called = True
        await asyncio.sleep(self.run_duration)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.shutdown_called = True
        await super().shutdown()


@pytest.fixture
def default_service_urls() -> Dict[str, str]:
    """Return default service URLs for testing."""
    return {"test-service": "http://localhost:8000", "other-service": "http://localhost:8001"}


@pytest.fixture
def agent_name() -> str:
    """Return a default agent name for testing."""
    return "test-agent"


@pytest.fixture
def config(agent_name: str) -> AgentConfig:
    """Create a standard agent configuration for testing."""
    return AgentConfig(name=agent_name, service_urls={})


@pytest.fixture
def mock_communicator(agent_name: str) -> mock.AsyncMock:
    """Create a mock communicator for testing."""
    return mock.AsyncMock()


@pytest.fixture
def real_mock_communicator(agent_name: str) -> MockCommunicator:
    """Create a real MockCommunicator instance for testing."""
    return MockCommunicator(agent_name, {})


@pytest.fixture
def simple_agent(config: AgentConfig, mock_communicator: mock.AsyncMock) -> SimpleAgent:
    """Create a simple agent instance with the mock communicator."""
    agent = SimpleAgent(config=config)
    agent.communicator = mock_communicator
    return agent


@pytest.fixture
def bdi_agent(config: AgentConfig) -> BdiAgent:
    """Create a BDI agent instance for testing."""
    return BdiAgent(config=config)


@pytest.fixture
def agent_test_harness() -> AgentTestHarness:
    """Create an AgentTestHarness for testing."""
    return AgentTestHarness(SimpleAgent, default_config={"name": "test-agent", "service_urls": {}})


@pytest.fixture
async def running_simple_agent(simple_agent: SimpleAgent) -> AsyncGenerator[SimpleAgent, None]:
    """Create and start a simple agent, then clean up after the test."""
    await simple_agent.start()
    yield simple_agent
    await simple_agent.stop()


@pytest.fixture
async def agent_with_mock_communicator(real_mock_communicator: MockCommunicator) -> SimpleAgent:
    """Create a SimpleAgent with a real MockCommunicator."""
    agent = SimpleAgent(
        name="test-agent",
        config=AgentConfig(name="test-agent", service_urls={}),
    )
    agent.communicator = real_mock_communicator
    return agent
