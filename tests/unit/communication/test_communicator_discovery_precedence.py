"""Tests for communicator discovery precedence."""
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

from openmas.communication import (
    COMMUNICATOR_LOADERS,
    COMMUNICATOR_TYPES,
    BaseCommunicator,
    discover_communicator_extensions,
    discover_local_communicators,
    get_communicator_by_type,
    get_communicator_class,
    register_communicator,
)
from openmas.communication.base import _COMMUNICATOR_REGISTRY
from openmas.testing import MockCommunicator


# Define test communicator classes for each discovery source
class BuiltInTestCommunicator(BaseCommunicator):
    """Built-in test communicator for testing discovery precedence."""

    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        """Mock implementation for testing."""
        return {"source": "built-in"}

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


class LazyLoadedTestCommunicator(BaseCommunicator):
    """Lazy-loaded test communicator for testing discovery precedence."""

    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        """Mock implementation for testing."""
        return {"source": "lazy-loaded"}

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


class ExtensionTestCommunicator(BaseCommunicator):
    """Extension test communicator for testing discovery precedence."""

    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        """Mock implementation for testing."""
        return {"source": "extension"}

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


class PackageTestCommunicator(BaseCommunicator):
    """Package test communicator for testing discovery precedence."""

    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        """Mock implementation for testing."""
        return {"source": "package"}

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


@pytest.fixture
def setup_communicator_registry():
    """Set up a clean communicator registry for testing."""
    # Save original registry state
    original_registry = _COMMUNICATOR_REGISTRY.copy()
    original_types = COMMUNICATOR_TYPES.copy()
    original_loaders = COMMUNICATOR_LOADERS.copy()

    # Clear registry for tests
    _COMMUNICATOR_REGISTRY.clear()

    # Yield to allow tests to run
    yield

    # Restore original registry state
    _COMMUNICATOR_REGISTRY.clear()
    _COMMUNICATOR_REGISTRY.update(original_registry)

    # Restore built-in types and loaders
    COMMUNICATOR_TYPES.clear()
    COMMUNICATOR_TYPES.update(original_types)

    COMMUNICATOR_LOADERS.clear()
    COMMUNICATOR_LOADERS.update(original_loaders)


def test_builtin_communicator_precedence(setup_communicator_registry):
    """Test that built-in communicators have highest precedence."""
    # Set up test communicators in all sources with the same name
    comm_name = "test_precedence"

    # Register a built-in communicator
    COMMUNICATOR_TYPES[comm_name] = BuiltInTestCommunicator

    # Register communicators in the registry (as if from extensions and packages)
    register_communicator(comm_name, ExtensionTestCommunicator)

    # Get the communicator - should return the built-in version
    comm_class = get_communicator_by_type(comm_name)

    # Verify it's the correct class (built-in has precedence)
    assert comm_class is BuiltInTestCommunicator


def test_lazy_loaded_communicator_precedence(setup_communicator_registry, monkeypatch):
    """Test that lazy-loaded communicators have second highest precedence."""
    # Set up test communicators with the same name
    comm_name = "test_precedence"

    # Create a mock lazy loader
    def mock_lazy_loader():
        return LazyLoadedTestCommunicator

    # Register a lazy-loaded communicator
    COMMUNICATOR_LOADERS[comm_name] = mock_lazy_loader

    # Register communicators in the registry (as if from extensions and packages)
    register_communicator(comm_name, ExtensionTestCommunicator)

    # Get the communicator - should return the lazy-loaded version
    comm_class = get_communicator_by_type(comm_name)

    # Verify it's the correct class (lazy-loaded has precedence over extensions)
    assert comm_class is LazyLoadedTestCommunicator


def test_extension_communicator_precedence(setup_communicator_registry, monkeypatch):
    """Test that extension communicators have precedence over package communicators."""
    # Set up test communicators with the same name
    comm_name = "test_precedence"

    # Mock the discover_communicator_extensions function to register a package communicator
    original_discover_extensions = discover_communicator_extensions

    def mock_discover_extensions():
        register_communicator(comm_name, PackageTestCommunicator)

    monkeypatch.setattr("openmas.communication.discover_communicator_extensions", mock_discover_extensions)

    # Register an extension communicator
    register_communicator(comm_name, ExtensionTestCommunicator)

    # Get the communicator - discovery_extensions will be called, but extension should have precedence
    comm_class = get_communicator_by_type(comm_name)

    # Verify it's the correct class (extension has precedence over package)
    assert comm_class is ExtensionTestCommunicator


def test_fallback_to_package_communicator(setup_communicator_registry, monkeypatch):
    """Test fallback to package communicators when no built-in or extension communicator exists."""
    # Set up test communicators with the same name
    comm_name = "test_precedence"

    # Mock the discover_communicator_extensions function to register a package communicator
    def mock_discover_extensions():
        register_communicator(comm_name, PackageTestCommunicator)

    monkeypatch.setattr("openmas.communication.discover_communicator_extensions", mock_discover_extensions)

    # Get the communicator - should trigger discovery and return the package communicator
    comm_class = get_communicator_by_type(comm_name)

    # Verify it's the correct class (package communicator)
    assert comm_class is PackageTestCommunicator


def test_communicator_not_found(setup_communicator_registry, monkeypatch):
    """Test that ValueError is raised when a communicator is not found anywhere."""
    # Set up a non-existent communicator name
    comm_name = "nonexistent_communicator"

    # Mock the discover_communicator_extensions function to do nothing
    def mock_discover_extensions():
        pass

    monkeypatch.setattr("openmas.communication.discover_communicator_extensions", mock_discover_extensions)

    # Attempt to get the non-existent communicator
    with pytest.raises(ValueError) as exc_info:
        get_communicator_by_type(comm_name)

    # Verify error message contains "not found"
    assert f"Communicator type '{comm_name}' not found" in str(exc_info.value)


def test_communicator_discovery_order_simulation(setup_communicator_registry, monkeypatch):
    """Test the full discovery process with all sources."""
    # This test simulates the complete discovery process to ensure correct precedence

    # Set up unique test communicator names for each source
    builtin_name = "builtin_comm"
    lazy_name = "lazy_comm"
    extension_name = "extension_comm"
    package_name = "package_comm"
    conflict_name = "conflict_comm"  # Will exist in multiple sources

    # Set up built-in communicator
    COMMUNICATOR_TYPES[builtin_name] = BuiltInTestCommunicator
    COMMUNICATOR_TYPES[conflict_name] = BuiltInTestCommunicator

    # Set up lazy-loaded communicator
    def mock_lazy_loader():
        return LazyLoadedTestCommunicator

    COMMUNICATOR_LOADERS[lazy_name] = mock_lazy_loader

    # Mock extension discovery to register extension communicators
    original_discover_locals = discover_local_communicators

    def mock_discover_locals(paths):
        register_communicator(extension_name, ExtensionTestCommunicator)
        register_communicator(conflict_name, ExtensionTestCommunicator)  # Conflict with built-in

    monkeypatch.setattr("openmas.communication.discover_local_communicators", mock_discover_locals)

    # Mock package discovery to register package communicators
    original_discover_extensions = discover_communicator_extensions

    def mock_discover_extensions():
        register_communicator(package_name, PackageTestCommunicator)
        register_communicator(conflict_name, PackageTestCommunicator)  # Conflict with built-in and extension

    monkeypatch.setattr("openmas.communication.discover_communicator_extensions", mock_discover_extensions)

    # Test built-in communicator
    assert get_communicator_by_type(builtin_name) is BuiltInTestCommunicator

    # Test lazy-loaded communicator
    assert get_communicator_by_type(lazy_name) is LazyLoadedTestCommunicator

    # Test extension communicator (requires discovering locals first)
    mock_discover_locals([])
    assert get_communicator_by_type(extension_name) is ExtensionTestCommunicator

    # Test package communicator (requires discovering extensions)
    assert get_communicator_by_type(package_name) is PackageTestCommunicator

    # Test conflict case - built-in should win
    assert get_communicator_by_type(conflict_name) is BuiltInTestCommunicator
