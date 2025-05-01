"""Tests for src/openmas/communication/__init__.py."""

from unittest.mock import MagicMock, patch

import pytest

# Import the actual module to access its globals like COMMUNICATOR_TYPES
import openmas.communication as comm_module

# Import functions/classes to test directly
from openmas.communication import create_communicator  # Add functions to be tested later
from openmas.communication import get_communicator_by_type  # Add functions to be tested later
from openmas.communication import DependencyError, _load_mqtt_communicator
from openmas.communication.base import BaseCommunicator
from openmas.communication.http import HttpCommunicator

# Mock communicator classes to avoid actual imports for *success* cases
# Add __name__ because register_communicator uses it.
# Remove spec to allow arbitrary kwargs in tests
MockMqttCommunicator = MagicMock(__name__="MockMqttCommunicator")
MockHttpCommunicator = MagicMock(__name__="MockHttpCommunicator")
MockMcpSseCommunicator = MagicMock(__name__="MockMcpSseCommunicator")


# Helper to reset state between tests modifying global COMMUNICATOR_TYPES
@pytest.fixture(autouse=True)
def ensure_clean_communicator_types():
    original_types = comm_module.COMMUNICATOR_TYPES.copy()
    # Preserve the original HTTP one if it exists, as it's built-in
    http_orig = original_types.get("http")
    yield  # Run the test
    comm_module.COMMUNICATOR_TYPES = original_types
    # Ensure HTTP is restored if it was there originally
    if http_orig and "http" not in comm_module.COMMUNICATOR_TYPES:
        comm_module.COMMUNICATOR_TYPES["http"] = http_orig


@patch("openmas.communication.register_communicator")
# Patch the location where MqttCommunicator is defined
@patch("openmas.communication.mqtt.MqttCommunicator", new=MockMqttCommunicator, create=True)
def test_load_mqtt_communicator_success(mock_register):
    """Test _load_mqtt_communicator successfully loads and registers when import works (mocked)."""
    comm_module.COMMUNICATOR_TYPES.pop("mqtt", None)  # Ensure not present
    loaded_class = _load_mqtt_communicator()
    assert loaded_class is MockMqttCommunicator
    mock_register.assert_called_once_with("mqtt", MockMqttCommunicator)
    assert comm_module.COMMUNICATOR_TYPES["mqtt"] is MockMqttCommunicator


@patch("openmas.communication.register_communicator")
@patch("openmas.communication.mqtt.MqttCommunicator", new=MockMqttCommunicator, create=True)
def test_load_mqtt_communicator_already_registered(mock_register):
    """Test _load_mqtt_communicator returns class without re-registering if already present."""
    comm_module.COMMUNICATOR_TYPES["mqtt"] = MockMqttCommunicator  # Ensure present
    loaded_class = _load_mqtt_communicator()
    assert loaded_class is MockMqttCommunicator
    mock_register.assert_not_called()
    assert "mqtt" in comm_module.COMMUNICATOR_TYPES


# --- Tests for get_communicator_by_type ---


# Use the real HttpCommunicator for this test, as it's guaranteed available
def test_get_communicator_by_type_builtin():
    """Test getting a built-in communicator type like http."""
    comm_class = get_communicator_by_type("http")
    assert comm_class is HttpCommunicator


# Use patch.dict on the COMMUNICATOR_LOADERS dictionary
@patch.dict(comm_module.COMMUNICATOR_LOADERS, {"mqtt": MagicMock(return_value=MockMqttCommunicator)})
def test_get_communicator_by_type_lazy_load_success():
    """Test getting a communicator type via a successful lazy load."""
    # Ensure it's not already loaded directly in COMMUNICATOR_TYPES
    comm_module.COMMUNICATOR_TYPES.pop("mqtt", None)

    mock_loader = comm_module.COMMUNICATOR_LOADERS["mqtt"]  # Get the mock loader
    comm_class = get_communicator_by_type("mqtt")

    assert comm_class is MockMqttCommunicator
    mock_loader.assert_called_once()  # Verify the loader (our mock) was called


# Use patch.dict on the COMMUNICATOR_LOADERS dictionary
@patch.dict(
    comm_module.COMMUNICATOR_LOADERS,
    {"mqtt": MagicMock(side_effect=DependencyError("Missing MQTT", dependency="paho-mqtt", extras="mqtt"))},
)
def test_get_communicator_by_type_lazy_load_failure():
    """Test getting a communicator type raises DependencyError if lazy load fails."""
    # Ensure it's not already loaded directly
    comm_module.COMMUNICATOR_TYPES.pop("mqtt", None)

    mock_loader = comm_module.COMMUNICATOR_LOADERS["mqtt"]  # Get the mock loader

    with pytest.raises(DependencyError) as excinfo:
        get_communicator_by_type("mqtt")

    assert excinfo.value.dependency == "paho-mqtt"
    assert excinfo.value.extras == "mqtt"
    mock_loader.assert_called_once()  # Verify the loader (our mock) was called


def test_get_communicator_by_type_not_found():
    """Test getting an unknown communicator type raises ValueError."""
    # Ensure the type doesn't exist via any mechanism (built-in, loader, registry)
    unknown_type = "nonexistent-protocol-v9000"
    comm_module.COMMUNICATOR_TYPES.pop(unknown_type, None)
    comm_module.COMMUNICATOR_LOADERS.pop(unknown_type, None)
    comm_module._COMMUNICATOR_REGISTRY.pop(unknown_type, None)

    with pytest.raises(ValueError) as excinfo:
        get_communicator_by_type(unknown_type)

    assert unknown_type in str(excinfo.value)
    assert "not found" in str(excinfo.value)


@patch("openmas.communication.discover_communicator_extensions")
def test_get_communicator_by_type_discovery(mock_discover):
    """Test that discovery is triggered if type is not immediately found."""
    discovered_type = "discovered-comm"
    MockDiscoveredComm = MagicMock(spec=BaseCommunicator, __name__="MockDiscoveredComm")

    # Simulate discovery adding the type to the registry
    def side_effect():
        comm_module._COMMUNICATOR_REGISTRY[discovered_type] = MockDiscoveredComm

    mock_discover.side_effect = side_effect

    # Ensure the type doesn't exist initially
    comm_module.COMMUNICATOR_TYPES.pop(discovered_type, None)
    comm_module.COMMUNICATOR_LOADERS.pop(discovered_type, None)
    comm_module._COMMUNICATOR_REGISTRY.pop(discovered_type, None)

    comm_class = get_communicator_by_type(discovered_type)

    mock_discover.assert_called_once()
    assert comm_class is MockDiscoveredComm
    assert discovered_type in comm_module._COMMUNICATOR_REGISTRY


# --- Tests for create_communicator ---


# Mock the actual get_communicator_by_type to control which class is returned
@patch("openmas.communication.get_communicator_by_type", return_value=MockHttpCommunicator)
def test_create_communicator_http(mock_get_class):
    """Test creating the HTTP communicator."""
    agent_name = "test_agent_http"
    service_urls = {"service1": "http://url1"}
    kwargs = {"extra_arg": "value"}  # This should be passed via **kwargs

    communicator = create_communicator(
        communicator_type="http", agent_name=agent_name, service_urls=service_urls, **kwargs  # Pass extra_arg here
    )

    mock_get_class.assert_called_once_with("http")
    # Verify the returned mock class was called with the correct args
    # HTTP communicator takes agent_name, service_urls, **kwargs
    MockHttpCommunicator.assert_called_once_with(
        agent_name=agent_name, service_urls=service_urls, extra_arg="value"  # Assert the kwarg directly
    )
    assert isinstance(communicator, MagicMock)  # Should be instance of our mock class


@patch("openmas.communication.get_communicator_by_type", return_value=MockMcpSseCommunicator)
def test_create_communicator_mcp(mock_get_class):
    """Test creating an MCP communicator with its specific arguments."""
    agent_name = "test_agent_mcp"
    service_urls = {"mcp_service": "http://mcp_url"}
    server_instructions = "Be helpful."
    service_args = {"mcp_service": ["--model", "claude-3-opus"]}
    kwargs = {"timeout": 30}  # This should be passed via **kwargs

    communicator = create_communicator(
        communicator_type="mcp-sse",
        agent_name=agent_name,
        service_urls=service_urls,
        server_mode=True,  # MCP specific
        server_instructions=server_instructions,  # MCP specific
        service_args=service_args,  # MCP specific
        **kwargs,  # Pass timeout here
    )

    mock_get_class.assert_called_once_with("mcp-sse")
    # Verify the returned mock class was called with the correct args including MCP specific ones and kwargs
    MockMcpSseCommunicator.assert_called_once_with(
        agent_name=agent_name,
        service_urls=service_urls,
        server_mode=True,
        server_instructions=server_instructions,
        service_args=service_args,
        timeout=30,  # Assert the kwarg directly
    )
    assert isinstance(communicator, MagicMock)


@patch("openmas.communication.get_communicator_by_type", return_value=MockMqttCommunicator)
def test_create_communicator_other(mock_get_class):
    """Test creating a non-HTTP, non-MCP communicator."""
    agent_name = "test_agent_other"
    service_urls = {"mqtt_broker": "tcp://broker"}
    kwargs = {"client_id": "test_client"}  # This should be passed via **kwargs

    # Note: We pass MCP args here, but they should be ignored by the default instantiation path
    communicator = create_communicator(
        communicator_type="mqtt",
        agent_name=agent_name,
        service_urls=service_urls,
        server_mode=True,  # Should be ignored
        server_instructions="ignore me",  # Should be ignored
        service_args={"a": ["b"]},  # Should be ignored
        **kwargs,  # Pass client_id here
    )

    mock_get_class.assert_called_once_with("mqtt")
    # Verify the returned mock class was called with the standard args (agent_name, service_urls, **kwargs)
    MockMqttCommunicator.assert_called_once_with(
        agent_name=agent_name, service_urls=service_urls, client_id="test_client"  # Assert the kwarg directly
    )
    assert isinstance(communicator, MagicMock)


@patch("openmas.communication.get_communicator_by_type", side_effect=ValueError("Not found"))
def test_create_communicator_not_found(mock_get_class):
    """Test create_communicator raises ValueError if get_communicator_by_type fails."""
    with pytest.raises(ValueError):
        create_communicator(communicator_type="unknown", agent_name="test_agent")
    mock_get_class.assert_called_once_with("unknown")


@patch(
    "openmas.communication.get_communicator_by_type", side_effect=DependencyError("Missing Dep", dependency="some-dep")
)
def test_create_communicator_dep_error(mock_get_class):
    """Test create_communicator raises DependencyError if get_communicator_by_type fails."""
    with pytest.raises(DependencyError):
        create_communicator(communicator_type="missing-dep", agent_name="test_agent")
    mock_get_class.assert_called_once_with("missing-dep")


# Cleanup after tests modify global state
def teardown_function(function):
    if "mqtt" in comm_module.COMMUNICATOR_TYPES:
        # Attempt to restore original state - might need more robust handling
        # depending on how COMMUNICATOR_TYPES is managed across the suite.
        # For now, just remove the test mock.
        if comm_module.COMMUNICATOR_TYPES["mqtt"] is MockMqttCommunicator:
            del comm_module.COMMUNICATOR_TYPES["mqtt"]
