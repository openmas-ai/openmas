"""Tests for communicator discovery functionality."""
# flake8: noqa: E402

import sys
from unittest import mock

import pytest

# Mock MCP imports to isolate tests
sys.modules["mcp"] = mock.MagicMock()
sys.modules["mcp.server"] = mock.MagicMock()
sys.modules["mcp.server.context"] = mock.MagicMock()
sys.modules["mcp.client"] = mock.MagicMock()
sys.modules["mcp.types"] = mock.MagicMock()

from simple_mas.agent import BaseAgent
from simple_mas.communication import (
    BaseCommunicator,
    discover_communicator_plugins,
    discover_local_communicators,
    get_communicator_class,
    load_local_communicator,
    register_communicator,
)
from simple_mas.communication.base import _COMMUNICATOR_REGISTRY
from simple_mas.testing import MockCommunicator


class TestCommunicator(BaseCommunicator):
    """Test communicator for testing discovery."""

    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        """Mock implementation for testing."""
        return {}

    async def send_notification(self, target_service, method, params=None):
        """Mock implementation for testing."""
        pass

    async def register_handler(self, method, handler):
        """Mock implementation for testing."""
        pass

    async def start(self):
        """Mock implementation for testing."""
        pass

    async def stop(self):
        """Mock implementation for testing."""
        pass


def test_register_and_get_communicator():
    """Test registering and retrieving a communicator class."""
    # Clear registry to ensure clean test
    _COMMUNICATOR_REGISTRY.clear()

    # Register a test communicator
    register_communicator("test", TestCommunicator)

    # Get the registered communicator
    communicator_class = get_communicator_class("test")

    # Verify it's the correct class
    assert communicator_class is TestCommunicator


def test_get_nonexistent_communicator():
    """Test getting a non-existent communicator type."""
    # Clear registry to ensure clean test
    _COMMUNICATOR_REGISTRY.clear()

    # Register a test communicator to have something in the registry
    register_communicator("test", TestCommunicator)

    # Try to get a non-existent communicator
    with pytest.raises(ValueError) as exc_info:
        get_communicator_class("nonexistent")

    # Verify error message contains available types
    assert "Available types: test" in str(exc_info.value)


@pytest.fixture
def mock_entry_point():
    """Create a mock entry point that returns TestCommunicator."""
    mock_ep = mock.MagicMock()
    mock_ep.name = "mock_communicator"
    mock_ep.load.return_value = TestCommunicator
    return mock_ep


def test_discover_communicator_plugins(monkeypatch):
    """Test discovering communicator plugins via entry points."""
    # Clear registry to ensure clean test
    _COMMUNICATOR_REGISTRY.clear()

    # Keep track of registered communicators
    registered_communicators = []

    # Mock the register_communicator function
    def mock_register(comm_type, comm_class):
        registered_communicators.append((comm_type, comm_class))
        # Still call the original to update the registry
        _COMMUNICATOR_REGISTRY[comm_type] = comm_class

    # Patch the register_communicator function
    monkeypatch.setattr("simple_mas.communication.base.register_communicator", mock_register)

    # Setup a mock entry point that will be returned
    mock_entry_point = mock.Mock()
    mock_entry_point.name = "mock_communicator"
    mock_entry_point.load.return_value = TestCommunicator

    # Mock importlib.metadata.entry_points to return our mock entry point
    mock_entry_points = mock.Mock(return_value=[mock_entry_point])
    monkeypatch.setattr("importlib.metadata.entry_points", mock_entry_points)

    # Call the function
    discover_communicator_plugins()

    # Verify the communicator was registered correctly
    assert ("mock_communicator", TestCommunicator) in registered_communicators
    assert "mock_communicator" in _COMMUNICATOR_REGISTRY
    assert _COMMUNICATOR_REGISTRY["mock_communicator"] is TestCommunicator


@pytest.fixture
def create_extension_dir(tmp_path):
    """Create a temporary directory with a sample communicator module."""

    # Create extension directory structure
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    communicators_dir = ext_dir / "communicators"
    communicators_dir.mkdir()

    # Create a sample communicator module
    comm_file = communicators_dir / "custom_communicator.py"
    comm_file.write_text(
        """
from simple_mas.communication import BaseCommunicator

class CustomCommunicator(BaseCommunicator):
    \"\"\"A custom communicator implementation.\"\"\"

    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        \"\"\"Mock implementation for testing.\"\"\"
        return {}

    async def send_notification(self, target_service, method, params=None):
        \"\"\"Mock implementation for testing.\"\"\"
        pass

    async def register_handler(self, method, handler):
        \"\"\"Mock implementation for testing.\"\"\"
        pass

    async def start(self):
        \"\"\"Mock implementation for testing.\"\"\"
        pass

    async def stop(self):
        \"\"\"Mock implementation for testing.\"\"\"
        pass
"""
    )

    return ext_dir


def test_discover_local_communicators(create_extension_dir):
    """Test discovering communicator plugins from local extensions."""
    # Clear registry to ensure clean test
    _COMMUNICATOR_REGISTRY.clear()

    # Call discover_local_communicators with the extension path
    discover_local_communicators([str(create_extension_dir)])

    # Verify the custom communicator was registered
    assert "custom_communicator" in _COMMUNICATOR_REGISTRY
    assert _COMMUNICATOR_REGISTRY["custom_communicator"].__name__ == "CustomCommunicator"


def test_load_local_communicator(create_extension_dir, monkeypatch):
    """Test loading a communicator from a local module path."""
    # Clear registry to ensure clean test
    _COMMUNICATOR_REGISTRY.clear()

    # Add extension directory to sys.path
    monkeypatch.syspath_prepend(str(create_extension_dir))

    # Load the communicator module
    load_local_communicator("communicators.custom_communicator", "custom")

    # Verify the communicator was registered
    assert "custom" in _COMMUNICATOR_REGISTRY
    assert _COMMUNICATOR_REGISTRY["custom"].__name__ == "CustomCommunicator"


def test_load_local_communicator_not_found(monkeypatch):
    """Test loading a non-existent communicator module."""
    # Try to load a non-existent module
    with pytest.raises(ImportError):
        load_local_communicator("nonexistent_module", "nonexistent")


def test_agent_init_with_explicit_communicator():
    """Test initializing an agent with an explicit communicator class."""

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Initialize with explicit communicator class
    agent = MockAgent(name="test_agent", config={"name": "test_agent"}, communicator_class=MockCommunicator)

    # Verify the communicator class was used
    assert isinstance(agent.communicator, MockCommunicator)


def test_agent_init_with_communicator_type(monkeypatch):
    """Test initializing an agent with a communicator type."""
    # Register a test communicator
    _COMMUNICATOR_REGISTRY.clear()
    register_communicator("test_type", TestCommunicator)

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Initialize with communicator type
    agent = MockAgent(name="test_agent", config={"name": "test_agent", "communicator_type": "test_type"})

    # Verify the communicator type was used
    assert isinstance(agent.communicator, TestCommunicator)


def test_agent_init_with_extension_paths(create_extension_dir, monkeypatch):
    """Test initializing an agent with extension paths."""
    # Clear registry to ensure clean test
    _COMMUNICATOR_REGISTRY.clear()

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Initialize with extension paths
    agent = MockAgent(
        name="test_agent",
        config={
            "name": "test_agent",
            "communicator_type": "custom_communicator",
            "extension_paths": [str(create_extension_dir)],
        },
    )

    # Verify the communicator from extension path was used
    assert agent.communicator.__class__.__name__ == "CustomCommunicator"
