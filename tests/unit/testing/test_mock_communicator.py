"""Tests for the MockCommunicator.

This file contains tests for the MockCommunicator class and demonstrates how to use it
for testing agents without real network dependencies.
"""

from typing import Any, Dict

import pytest

from simple_mas.exceptions import ServiceNotFoundError
from simple_mas.testing.mock_communicator import MockCommunicator
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
        with pytest.raises(AssertionError):
            await real_mock_communicator.send_request("test-service", "test-method", {"param": "value"})

    @pytest.mark.asyncio
    async def test_exception_for_parameter_mismatch(self, real_mock_communicator: MockCommunicator) -> None:
        """Test that an exception is raised for a parameter mismatch."""
        # Arrange
        real_mock_communicator.expect_request(
            "test-service", "test-method", {"param": "expected"}, {"result": "success"}
        )

        # Act & Assert
        with pytest.raises(AssertionError):
            await real_mock_communicator.send_request("test-service", "test-method", {"param": "actual"})

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
        received_params = None

        async def test_handler(params: Dict[str, Any]) -> None:
            nonlocal handler_called, received_params
            handler_called = True
            received_params = params

        await real_mock_communicator.register_handler("test-method", test_handler)

        # Act
        await real_mock_communicator.trigger_handler("test-method", {"param": "value"})

        # Assert
        assert handler_called
        assert received_params == {"param": "value"}

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
        with pytest.raises(AssertionError):
            real_mock_communicator.verify()
