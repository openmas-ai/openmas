"""Tests for the MockCommunicator.

This file contains tests for the MockCommunicator class and demonstrates how to use it
for testing agents without real network dependencies.
"""

import re
from typing import Any, Dict

import pytest

from simple_mas.exceptions import ServiceNotFoundError
from simple_mas.testing.mock_communicator import MockCommunicator, ParamsMatcher
from tests.conftest import SimpleAgent

# Import fixtures from conftest.py instead of defining them locally
# The real_mock_communicator fixture replaces the local mock_communicator
# The agent_with_mock_communicator fixture replaces the local agent_with_mock


class TestMockCommunicator:
    """Tests for the MockCommunicator class."""

    @pytest.mark.asyncio
    async def test_send_request(self, real_mock_communicator: MockCommunicator) -> None:
        """Test sending a request with a predefined response."""
        # Arrange
        real_mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act
        result = await real_mock_communicator.send_request("test-service", "test-method", {"param": "value"})

        # Assert
        assert result == {"result": "success"}
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_send_notification(self, real_mock_communicator: MockCommunicator) -> None:
        """Test sending a notification."""
        # Arrange
        real_mock_communicator.expect_notification("test-service", "test-method", {"param": "value"})

        # Act
        await real_mock_communicator.send_notification("test-service", "test-method", {"param": "value"})

        # Assert
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_exception_for_unexpected_request(self, real_mock_communicator: MockCommunicator) -> None:
        """Test that an exception is raised for an unexpected request."""
        # Act & Assert
        with pytest.raises(AssertionError) as excinfo:
            await real_mock_communicator.send_request("test-service", "test-method", {"param": "value"})
        assert "Unexpected request" in str(excinfo.value)
        assert "test-service:test-method" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_exception_for_parameter_mismatch(self, real_mock_communicator: MockCommunicator) -> None:
        """Test that an exception is raised for a parameter mismatch."""
        # Arrange
        real_mock_communicator.expect_request(
            "test-service", "test-method", {"param": "expected"}, {"result": "success"}
        )

        # Act & Assert
        with pytest.raises(AssertionError) as excinfo:
            await real_mock_communicator.send_request("test-service", "test-method", {"param": "actual"})
        assert "Parameter mismatch" in str(excinfo.value)
        assert "Value mismatch for key 'param'" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_predefined_exception(self, real_mock_communicator: MockCommunicator) -> None:
        """Test that a predefined exception is raised."""
        # Arrange
        exception = ServiceNotFoundError("test-service not found")
        real_mock_communicator.expect_request_exception("test-service", "test-method", {"param": "value"}, exception)

        # Act & Assert
        with pytest.raises(ServiceNotFoundError) as excinfo:
            await real_mock_communicator.send_request("test-service", "test-method", {"param": "value"})
        assert str(excinfo.value) == "test-service not found"
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_register_and_trigger_handler(self, real_mock_communicator: MockCommunicator) -> None:
        """Test registering and triggering a handler."""
        # Arrange
        handler_called = False
        received_content = None

        async def test_handler(message: Dict[str, Any]) -> None:
            nonlocal handler_called, received_content
            handler_called = True
            received_content = message["content"]

        await real_mock_communicator.register_handler("test-method", test_handler)

        # Act
        await real_mock_communicator.trigger_handler("test-method", {"param": "value"})

        # Assert
        assert handler_called
        assert received_content == {"param": "value"}

    @pytest.mark.asyncio
    async def test_reset(self, real_mock_communicator: MockCommunicator) -> None:
        """Test resetting the mock communicator."""
        # Arrange
        real_mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act
        real_mock_communicator.reset()

        # Assert
        with pytest.raises(AssertionError):
            await real_mock_communicator.send_request("test-service", "test-method", {"param": "value"})

    @pytest.mark.asyncio
    async def test_with_agent(
        self, agent_with_mock_communicator: SimpleAgent, real_mock_communicator: MockCommunicator
    ) -> None:
        """Test using the mock communicator with an agent."""
        # Arrange
        agent = await agent_with_mock_communicator
        real_mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act
        result = await agent.communicator.send_request("test-service", "test-method", {"param": "value"})

        # Assert
        assert result == {"result": "success"}
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_multiple_expectations(self, real_mock_communicator: MockCommunicator) -> None:
        """Test handling multiple expectations in sequence."""
        # Arrange
        real_mock_communicator.expect_request("service1", "method1", {"param": "value1"}, {"result": "success1"})
        real_mock_communicator.expect_request("service2", "method2", {"param": "value2"}, {"result": "success2"})

        # Act
        result1 = await real_mock_communicator.send_request("service1", "method1", {"param": "value1"})
        result2 = await real_mock_communicator.send_request("service2", "method2", {"param": "value2"})

        # Assert
        assert result1 == {"result": "success1"}
        assert result2 == {"result": "success2"}
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_verify_unmet_expectations(self, real_mock_communicator: MockCommunicator) -> None:
        """Test that verify raises an exception if expectations are not met."""
        # Arrange
        real_mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act & Assert
        with pytest.raises(AssertionError) as excinfo:
            real_mock_communicator.verify_all_expectations_met()

        error_msg = str(excinfo.value)
        assert "Unmet request expectations" in error_msg
        assert "test-service:test-method" in error_msg
        assert "params" in error_msg
        assert "response" in error_msg

    @pytest.mark.asyncio
    async def test_regex_pattern_matching(self, real_mock_communicator: MockCommunicator) -> None:
        """Test regex pattern matching for parameters."""
        # Arrange - use regex pattern for user_id
        real_mock_communicator.expect_request(
            "users-service", "get_user", {"user_id": re.compile(r"^user_\d+$")}, {"name": "Test User"}
        )

        # Act
        result = await real_mock_communicator.send_request("users-service", "get_user", {"user_id": "user_123"})

        # Assert
        assert result == {"name": "Test User"}
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_regex_pattern_mismatch(self, real_mock_communicator: MockCommunicator) -> None:
        """Test regex pattern mismatch for parameters."""
        # Arrange - use regex pattern for user_id
        real_mock_communicator.expect_request(
            "users-service", "get_user", {"user_id": re.compile(r"^user_\d+$")}, {"name": "Test User"}
        )

        # Act & Assert - should fail for invalid format
        with pytest.raises(AssertionError) as excinfo:
            await real_mock_communicator.send_request("users-service", "get_user", {"user_id": "invalid-user"})
        assert "does not match pattern" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_custom_matcher_function(self, real_mock_communicator: MockCommunicator) -> None:
        """Test custom matcher function for parameters."""

        # Arrange - define a custom matcher for age validation
        def is_valid_age(value: Any) -> bool:
            return isinstance(value, int) and 0 <= value <= 120

        real_mock_communicator.expect_request(
            "users-service", "update_user", {"user_id": "123", "age": is_valid_age}, {"status": "updated"}
        )

        # Act - send with valid age
        result = await real_mock_communicator.send_request(
            "users-service", "update_user", {"user_id": "123", "age": 30}
        )

        # Assert
        assert result == {"status": "updated"}
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_custom_matcher_function_failure(self, real_mock_communicator: MockCommunicator) -> None:
        """Test custom matcher function failure for parameters."""

        # Arrange - define a custom matcher for age validation
        def is_valid_age(value: Any) -> bool:
            return isinstance(value, int) and 0 <= value <= 120

        real_mock_communicator.expect_request(
            "users-service", "update_user", {"user_id": "123", "age": is_valid_age}, {"status": "updated"}
        )

        # Act & Assert - should fail for invalid age
        with pytest.raises(AssertionError) as excinfo:
            await real_mock_communicator.send_request("users-service", "update_user", {"user_id": "123", "age": -5})
        assert "Failed custom matcher check" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_nested_dict_matching(self, real_mock_communicator: MockCommunicator) -> None:
        """Test nested dictionary matching for parameters."""
        # Arrange - expect a nested structure
        real_mock_communicator.expect_request(
            "users-service",
            "create_user",
            {"user": {"profile": {"name": "John", "role": "admin"}}},
            {"user_id": "new_123"},
        )

        # Act - send with matching nested structure plus extra fields
        result = await real_mock_communicator.send_request(
            "users-service",
            "create_user",
            {
                "user": {
                    "profile": {"name": "John", "role": "admin", "extra": "field"},  # Extra field should be fine
                    "preferences": {},  # Extra field should be fine
                }
            },
        )

        # Assert
        assert result == {"user_id": "new_123"}
        real_mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_nested_dict_mismatch(self, real_mock_communicator: MockCommunicator) -> None:
        """Test nested dictionary mismatch for parameters."""
        # Arrange - expect a nested structure
        real_mock_communicator.expect_request(
            "users-service",
            "create_user",
            {"user": {"profile": {"name": "John", "role": "admin"}}},
            {"user_id": "new_123"},
        )

        # Act & Assert - should fail for mismatched nested value
        with pytest.raises(AssertionError) as excinfo:
            await real_mock_communicator.send_request(
                "users-service",
                "create_user",
                {"user": {"profile": {"name": "John", "role": "user"}}},  # Different value
            )
        assert "Mismatch in nested key" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_linked_communicators(self) -> None:
        """Test linking communicators for direct message passing."""
        # Create two communicators
        comm1 = MockCommunicator(agent_name="agent1")
        comm2 = MockCommunicator(agent_name="agent2")

        # Link them
        comm1.link_communicator(comm2)

        # Register a handler on comm2
        handler_called = False
        handler_params = None

        async def test_handler(message: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal handler_called, handler_params
            handler_called = True
            handler_params = message["content"]
            return {"response": "ok"}

        await comm2.register_handler("test_method", test_handler)

        # Send a notification from comm1 to comm2
        await comm1.send_notification("agent2", "test_method", {"data": "test"})

        # Assert that the handler was called
        assert handler_called
        assert handler_params == {"data": "test"}

        # Clean up
        await comm1.stop()
        await comm2.stop()

    def test_params_matcher(self) -> None:
        """Test the ParamsMatcher utility class."""
        # Test matching None (any parameters)
        match, reason = ParamsMatcher.match(None, {"any": "value"})
        assert match is True
        assert reason is None

        # Test exact dictionary match
        match, reason = ParamsMatcher.match({"key": "value"}, {"key": "value"})
        assert match is True
        assert reason is None

        # Test dictionary mismatch
        match, reason = ParamsMatcher.match({"key": "value"}, {"key": "wrong"})
        assert match is False
        assert reason is not None  # Check that reason is not None instead of string contains
        assert "Value mismatch for key" in str(reason)

        # Test missing key
        match, reason = ParamsMatcher.match({"key": "value"}, {})
        assert match is False
        assert reason is not None  # Check that reason is not None instead of string contains
        assert "Missing expected key" in str(reason)

        # Test regex match
        match, reason = ParamsMatcher.match(re.compile(r"^test_\d+$"), "test_123")
        assert match is True
        assert reason is None

        # Test regex mismatch
        match, reason = ParamsMatcher.match(re.compile(r"^test_\d+$"), "invalid")
        assert match is False
        assert reason is not None  # Check that reason is not None instead of string contains
        assert "does not match pattern" in str(reason)

        # Test custom matcher
        match, reason = ParamsMatcher.match(lambda x: x > 10, 20)
        assert match is True
        assert reason is None

        # Test custom matcher failure
        match, reason = ParamsMatcher.match(lambda x: x > 10, 5)
        assert match is False
        assert reason is not None  # Check that reason is not None instead of string contains
        assert "Failed custom matcher" in str(reason)
