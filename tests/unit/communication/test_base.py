"""Tests for src/openmas/communication/base.py."""

import logging

import pytest

from openmas.communication.base import (
    _COMMUNICATOR_REGISTRY,
    BaseCommunicator,
    get_available_communicator_types,
    get_communicator_class,
    register_communicator,
)


# Mock Communicator Classes
class MockCommA(BaseCommunicator):
    async def send_request(self, *args, **kwargs):
        pass

    async def send_notification(self, *args, **kwargs):
        pass

    async def register_handler(self, *args, **kwargs):
        pass

    async def start(self, *args, **kwargs):
        pass

    async def stop(self, *args, **kwargs):
        pass


class MockCommB(BaseCommunicator):
    async def send_request(self, *args, **kwargs):
        pass

    async def send_notification(self, *args, **kwargs):
        pass

    async def register_handler(self, *args, **kwargs):
        pass

    async def start(self, *args, **kwargs):
        pass

    async def stop(self, *args, **kwargs):
        pass


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensures the registry is clean before and after each test."""
    original_registry = _COMMUNICATOR_REGISTRY.copy()
    _COMMUNICATOR_REGISTRY.clear()
    yield
    _COMMUNICATOR_REGISTRY.clear()
    _COMMUNICATOR_REGISTRY.update(original_registry)


def test_register_communicator_success():
    """Test successful registration."""
    register_communicator("type_a", MockCommA)
    assert "type_a" in _COMMUNICATOR_REGISTRY
    assert _COMMUNICATOR_REGISTRY["type_a"] is MockCommA


def test_register_communicator_overwrite_logs_warning(caplog):
    """Test that overwriting an existing registration logs a warning."""
    register_communicator("type_a", MockCommA)  # Initial registration
    with caplog.at_level(logging.WARNING):
        register_communicator("type_a", MockCommB)  # Overwrite

    assert "type_a" in _COMMUNICATOR_REGISTRY
    assert _COMMUNICATOR_REGISTRY["type_a"] is MockCommB  # Should be overwritten
    assert len(caplog.records) == 1
    assert "Communicator type already registered, overwriting" in caplog.text
    assert "old_class=MockCommA" in caplog.text
    assert "new_class=MockCommB" in caplog.text


def test_get_communicator_class_success():
    """Test successfully retrieving a registered class."""
    register_communicator("type_a", MockCommA)
    comm_class = get_communicator_class("type_a")
    assert comm_class is MockCommA


def test_get_communicator_class_not_found_raises_value_error():
    """Test that getting a non-existent type raises ValueError."""
    register_communicator("type_a", MockCommA)  # Register something else
    with pytest.raises(ValueError) as excinfo:
        get_communicator_class("type_b")

    assert "Communicator type 'type_b' not registered" in str(excinfo.value)
    assert "Available types: type_a" in str(excinfo.value)


def test_get_communicator_class_not_found_empty_registry():
    """Test ValueError message when the registry is empty."""
    with pytest.raises(ValueError) as excinfo:
        get_communicator_class("type_c")
    assert "Communicator type 'type_c' not registered" in str(excinfo.value)
    assert "Available types: none" in str(excinfo.value)


def test_get_available_communicator_types():
    """Test getting the dictionary of available types."""
    register_communicator("type_a", MockCommA)
    register_communicator("type_b", MockCommB)
    available = get_available_communicator_types()
    assert available == {"type_a": MockCommA, "type_b": MockCommB}
    # Ensure it's a copy
    available["new"] = None  # type: ignore
    assert "new" not in _COMMUNICATOR_REGISTRY


# --- Tests for BaseCommunicator ABC ---


# Create a minimal concrete subclass for testing __init__
class ConcreteCommunicator(BaseCommunicator):
    async def send_request(self, *args, **kwargs):
        pass

    async def send_notification(self, *args, **kwargs):
        pass

    async def register_handler(self, *args, **kwargs):
        pass

    async def start(self, *args, **kwargs):
        pass

    async def stop(self, *args, **kwargs):
        pass


def test_base_communicator_init():
    """Test the initialization of BaseCommunicator attributes."""
    agent_name = "test-agent"
    service_urls = {"s1": "url1"}
    comm = ConcreteCommunicator(agent_name=agent_name, service_urls=service_urls)

    # Attributes assigned directly from args (no underscore in __init__ assignment)
    assert comm.agent_name == agent_name
    assert comm.service_urls == service_urls
    # Attributes assigned internally (using underscore in __init__ assignment)
    assert comm._server_mode is False  # Default
    assert comm._server_instructions is None  # Default
    assert comm._service_args == {}  # Default is {} due to "or {}"
    assert comm._port is None  # Default
    # Note: handlers, lock, _started, _tasks are not initialized in base __init__


def test_base_communicator_init_with_optional_args():
    """Test initialization with optional arguments."""
    agent_name = "test-agent-2"
    service_urls = {"s2": "url2"}
    server_instructions = "Do something"
    service_args = {"s2": ["--flag"]}
    port = 9999

    comm = ConcreteCommunicator(
        agent_name=agent_name,
        service_urls=service_urls,
        server_mode=True,
        server_instructions=server_instructions,
        service_args=service_args,
        port=port,
    )

    # Attributes assigned directly from args (no underscore in __init__ assignment)
    assert comm.agent_name == agent_name
    assert comm.service_urls == service_urls
    # Attributes assigned internally (using underscore in __init__ assignment)
    assert comm._server_mode is True
    assert comm._server_instructions == server_instructions
    assert comm._service_args == service_args
    assert comm._port == port
    # Note: handlers, lock, _started, _tasks are not initialized in base __init__
