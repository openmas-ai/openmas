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

from openmas.agent import BaseAgent
from openmas.communication import (
    COMMUNICATOR_LOADERS,
    BaseCommunicator,
    discover_communicator_extensions,
    discover_local_communicators,
    get_communicator_by_type,
    get_communicator_class,
    load_local_communicator,
    register_communicator,
)
from openmas.communication.base import _COMMUNICATOR_REGISTRY
from openmas.exceptions import ConfigurationError, DependencyError
from openmas.testing import MockCommunicator


@pytest.mark.no_collect
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


def test_discover_communicator_extensions(monkeypatch):
    """Test discovering communicator extensions via entry points."""
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
    monkeypatch.setattr("openmas.communication.base.register_communicator", mock_register)

    # Setup a mock entry point that will be returned
    mock_entry_point = mock.Mock()
    mock_entry_point.name = "mock_communicator"
    mock_entry_point.load.return_value = TestCommunicator

    # Mock importlib.metadata.entry_points to return our mock entry point
    mock_entry_points = mock.Mock(return_value=[mock_entry_point])
    monkeypatch.setattr("importlib.metadata.entry_points", mock_entry_points)

    # Call the function
    discover_communicator_extensions()

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
from openmas.communication import BaseCommunicator

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
    """Test discovering communicator extensions from local extensions."""
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
    """Test initializing an agent with extension_paths in the config."""
    # Add the extension directory to sys.path
    monkeypatch.syspath_prepend(str(create_extension_dir))

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Initialize with extension_paths and a custom communicator type
    agent = MockAgent(
        name="test_agent",
        config={
            "name": "test_agent",
            "communicator_type": "custom_communicator",
            "extension_paths": [str(create_extension_dir)],
        },
    )

    # Verify the custom communicator was used
    assert agent.communicator.__class__.__name__ == "CustomCommunicator"


def test_agent_init_with_extension_paths_array(create_extension_dir, monkeypatch):
    """Test initializing an agent with multiple extension_paths in the config."""
    # Add the extension directory to sys.path
    monkeypatch.syspath_prepend(str(create_extension_dir))

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Initialize with multiple extension_paths and a custom communicator type
    agent = MockAgent(
        name="test_agent",
        config={
            "name": "test_agent",
            "communicator_type": "custom_communicator",
            "extension_paths": [str(create_extension_dir), "/another/path"],
        },
    )

    # Verify the custom communicator was used
    assert agent.communicator.__class__.__name__ == "CustomCommunicator"


def test_missing_mcp_dependency(monkeypatch):
    """Test that a helpful error is raised when the mcp dependency is missing."""
    # Preserve the original COMMUNICATOR_LOADERS
    original_loaders = COMMUNICATOR_LOADERS.copy()

    try:
        # Create a mock MCP loader function that raises DependencyError
        def mock_mcp_loader():
            raise DependencyError(
                "The MCP SSE communicator requires the 'mcp' package. "
                "Please install it using: pip install openmas[mcp]",
                dependency="mcp",
                extras="mcp",
            )

        # Override the MCP loader
        COMMUNICATOR_LOADERS["mcp-sse"] = mock_mcp_loader

        # Try to get the MCP communicator
        with pytest.raises(DependencyError) as exc_info:
            get_communicator_by_type("mcp-sse")

        # Verify the error message mentions mcp and pip install
        assert "mcp" in str(exc_info.value)
        assert "pip install" in str(exc_info.value)
        assert hasattr(exc_info.value, "dependency")
        assert exc_info.value.dependency == "mcp"
        assert hasattr(exc_info.value, "extras")
        assert exc_info.value.extras == "mcp"
    finally:
        # Restore original loaders
        COMMUNICATOR_LOADERS.clear()
        COMMUNICATOR_LOADERS.update(original_loaders)


def test_missing_grpc_dependency(monkeypatch):
    """Test that a helpful error is raised when the grpc dependency is missing."""
    # Preserve the original COMMUNICATOR_LOADERS
    original_loaders = COMMUNICATOR_LOADERS.copy()

    try:
        # Create a mock gRPC loader function that raises DependencyError
        def mock_grpc_loader():
            raise DependencyError(
                "The gRPC communicator requires the 'grpcio' and 'grpcio-tools' packages. "
                "Please install them using: pip install openmas[grpc]",
                dependency="grpcio",
                extras="grpc",
            )

        # Override the gRPC loader
        COMMUNICATOR_LOADERS["grpc"] = mock_grpc_loader

        # Try to get the gRPC communicator
        with pytest.raises(DependencyError) as exc_info:
            get_communicator_by_type("grpc")

        # Verify the error message mentions grpc and pip install
        assert "grpc" in str(exc_info.value)
        assert "pip install" in str(exc_info.value)
        assert hasattr(exc_info.value, "dependency")
        assert exc_info.value.dependency == "grpcio"
        assert hasattr(exc_info.value, "extras")
        assert exc_info.value.extras == "grpc"
    finally:
        # Restore original loaders
        COMMUNICATOR_LOADERS.clear()
        COMMUNICATOR_LOADERS.update(original_loaders)


def test_agent_with_missing_dependency(monkeypatch):
    """Test that an agent correctly handles a missing dependency for a communicator."""
    # Preserve the original COMMUNICATOR_LOADERS
    original_loaders = COMMUNICATOR_LOADERS.copy()

    try:
        # Create a mock MCP loader function that raises DependencyError
        def mock_mcp_loader():
            raise DependencyError(
                "The MCP SSE communicator requires the 'mcp' package. "
                "Please install it using: pip install openmas[mcp]",
                dependency="mcp",
                extras="mcp",
            )

        # Override the MCP loader
        COMMUNICATOR_LOADERS["mcp-sse"] = mock_mcp_loader

        # Create a mock agent class
        class MockAgent(BaseAgent):
            async def setup(self):
                pass

            async def run(self):
                pass

            async def shutdown(self):
                pass

        # Try to initialize an agent with mcp-sse communicator type
        with pytest.raises(DependencyError) as exc_info:
            MockAgent(name="test_agent", config={"name": "test_agent", "communicator_type": "mcp-sse"})

        # Verify the error message mentions mcp and pip install
        assert "mcp" in str(exc_info.value)
        assert "pip install" in str(exc_info.value)
    finally:
        # Restore original loaders
        COMMUNICATOR_LOADERS.clear()
        COMMUNICATOR_LOADERS.update(original_loaders)


def test_nonexistent_communicator_type_in_agent():
    """Test that an agent correctly handles a non-existent communicator type."""

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Try to initialize an agent with a non-existent communicator type
    with pytest.raises(ConfigurationError) as exc_info:
        MockAgent(name="test_agent", config={"name": "test_agent", "communicator_type": "nonexistent_type"})

    # Verify the error message mentions the communicator type
    assert "nonexistent_type" in str(exc_info.value)


def test_missing_mcp_sse_dependency(mocker):
    """Test that DependencyError is raised when mcp-sse is requested but mcp is not installed."""

    # Create a mock loader function that simulates the failure
    def mock_mcp_sse_loader():
        raise DependencyError(
            "The MCP SSE communicator requires the 'mcp' package. " "Please install it using: pip install openmas[mcp]",
            dependency="mcp",
            extras="mcp",
        )

    # Store original loader
    original_loader = COMMUNICATOR_LOADERS.get("mcp-sse")

    try:
        # Replace the loader with our mock
        COMMUNICATOR_LOADERS["mcp-sse"] = mock_mcp_sse_loader

        # Attempt to get the MCP SSE communicator
        with pytest.raises(DependencyError) as exc_info:
            get_communicator_by_type("mcp-sse")

        # Verify error details
        error = exc_info.value
        assert "MCP SSE communicator requires the 'mcp' package" in str(error)
        assert "pip install openmas[mcp]" in str(error)
        assert error.dependency == "mcp"
        assert error.extras == "mcp"
    finally:
        # Restore original loader if it existed
        if original_loader:
            COMMUNICATOR_LOADERS["mcp-sse"] = original_loader


def test_missing_mcp_stdio_dependency(mocker):
    """Test that DependencyError is raised when mcp-stdio is requested but mcp is not installed."""

    # Create a mock loader function that simulates the failure
    def mock_mcp_stdio_loader():
        raise DependencyError(
            "The MCP STDIO communicator requires the 'mcp' package. "
            "Please install it using: pip install openmas[mcp]",
            dependency="mcp",
            extras="mcp",
        )

    # Store original loader
    original_loader = COMMUNICATOR_LOADERS.get("mcp-stdio")

    try:
        # Replace the loader with our mock
        COMMUNICATOR_LOADERS["mcp-stdio"] = mock_mcp_stdio_loader

        # Attempt to get the MCP STDIO communicator
        with pytest.raises(DependencyError) as exc_info:
            get_communicator_by_type("mcp-stdio")

        # Verify error details
        error = exc_info.value
        assert "MCP STDIO communicator requires the 'mcp' package" in str(error)
        assert "pip install openmas[mcp]" in str(error)
        assert error.dependency == "mcp"
        assert error.extras == "mcp"
    finally:
        # Restore original loader if it existed
        if original_loader:
            COMMUNICATOR_LOADERS["mcp-stdio"] = original_loader


def test_missing_grpc_dependency_lazy_loading(mocker):
    """Test that DependencyError is raised when grpc is requested but grpcio is not installed."""

    # Create a mock loader function that simulates the failure
    def mock_grpc_loader():
        raise DependencyError(
            "The gRPC communicator requires the 'grpcio' and 'grpcio-tools' packages. "
            "Please install them using: pip install openmas[grpc]",
            dependency="grpcio",
            extras="grpc",
        )

    # Store original loader
    original_loader = COMMUNICATOR_LOADERS.get("grpc")

    try:
        # Replace the loader with our mock
        COMMUNICATOR_LOADERS["grpc"] = mock_grpc_loader

        # Attempt to get the gRPC communicator
        with pytest.raises(DependencyError) as exc_info:
            get_communicator_by_type("grpc")

        # Verify error details
        error = exc_info.value
        assert "gRPC communicator requires" in str(error)
        assert "pip install openmas[grpc]" in str(error)
        assert error.dependency == "grpcio"
        assert error.extras == "grpc"
    finally:
        # Restore original loader if it existed
        if original_loader:
            COMMUNICATOR_LOADERS["grpc"] = original_loader


def test_missing_mqtt_dependency(mocker):
    """Test that DependencyError is raised when mqtt is requested but paho.mqtt is not installed."""

    # Create a mock loader function that simulates the failure
    def mock_mqtt_loader():
        raise DependencyError(
            "The MQTT communicator requires the 'paho-mqtt' package. "
            "Please install it using: pip install openmas[mqtt]",
            dependency="paho-mqtt",
            extras="mqtt",
        )

    # Store original loader
    original_loader = COMMUNICATOR_LOADERS.get("mqtt")

    try:
        # Replace the loader with our mock
        COMMUNICATOR_LOADERS["mqtt"] = mock_mqtt_loader

        # Attempt to get the MQTT communicator
        with pytest.raises(DependencyError) as exc_info:
            get_communicator_by_type("mqtt")

        # Verify error details
        error = exc_info.value
        assert "MQTT communicator requires the 'paho-mqtt' package" in str(error)
        assert "pip install openmas[mqtt]" in str(error)
        assert error.dependency == "paho-mqtt"
        assert error.extras == "mqtt"
    finally:
        # Restore original loader if it existed
        if original_loader:
            COMMUNICATOR_LOADERS["mqtt"] = original_loader


def test_communicator_type_with_missing_dependency_in_agent():
    """Test that a DependencyError is correctly propagated when initializing an agent with a communicator that has missing dependencies."""

    # Create a mock agent class
    class MockAgent(BaseAgent):
        async def setup(self):
            pass

        async def run(self):
            pass

        async def shutdown(self):
            pass

    # Create a mock loader function that simulates the failure
    def mock_problematic_loader():
        raise DependencyError(
            "This communicator requires a package that is not installed. "
            "Please install it using pip install openmas[extra]",
            dependency="missing-package",
            extras="extra",
        )

    # Store original loader if it exists
    original_loader = COMMUNICATOR_LOADERS.get("problematic")

    try:
        # Add a problematic communicator type
        COMMUNICATOR_LOADERS["problematic"] = mock_problematic_loader

        # Try to initialize an agent with this communicator type
        with pytest.raises(DependencyError) as exc_info:
            MockAgent(name="test_agent", config={"name": "test_agent", "communicator_type": "problematic"})

        # Verify the error message mentions installation instructions
        assert "package that is not installed" in str(exc_info.value)
        assert "pip install openmas[extra]" in str(exc_info.value)
        # Check the dependency and extras attributes
        assert exc_info.value.dependency == "missing-package"
        assert exc_info.value.extras == "extra"
    finally:
        # Clean up: remove our test loader
        if "problematic" in COMMUNICATOR_LOADERS:
            del COMMUNICATOR_LOADERS["problematic"]

        # Restore original if it existed
        if original_loader:
            COMMUNICATOR_LOADERS["problematic"] = original_loader
