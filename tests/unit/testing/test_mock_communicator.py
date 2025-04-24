"""Tests for the MockCommunicator.

This file contains tests for the MockCommunicator class and demonstrates how to use it
for testing agents without real network dependencies.
"""

from typing import Any, Dict

import pytest

from simple_mas.config import AgentConfig
from simple_mas.exceptions import ServiceNotFoundError
from simple_mas.testing.mock_communicator import MockCommunicator

# Import SimpleAgent from the new location
from tests.unit.agent.test_agent import SimpleAgent


class TestMockCommunicator:
    """Tests for the MockCommunicator class."""

    @pytest.fixture
    def mock_communicator(self):
        """Create a MockCommunicator for testing."""
        return MockCommunicator("test-agent", {})

    @pytest.fixture
    async def agent_with_mock(self, mock_communicator):
        """Create a SimpleAgent with a MockCommunicator."""
        agent = SimpleAgent(
            name="test-agent",
            config=AgentConfig(name="test-agent", service_urls={}),
        )
        agent.communicator = mock_communicator
        return agent

    @pytest.mark.asyncio
    async def test_send_request(self, mock_communicator):
        """Test sending a request with a predefined response."""
        # Arrange
        mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act
        result = await mock_communicator.send_request("test-service", "test-method", {"param": "value"})

        # Assert
        assert result == {"result": "success"}
        mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_send_notification(self, mock_communicator):
        """Test sending a notification."""
        # Arrange
        mock_communicator.expect_notification("test-service", "test-method", {"param": "value"})

        # Act
        await mock_communicator.send_notification("test-service", "test-method", {"param": "value"})

        # Assert
        mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_exception_for_unexpected_request(self, mock_communicator):
        """Test that an exception is raised for an unexpected request."""
        # Act & Assert
        with pytest.raises(AssertionError):
            await mock_communicator.send_request("test-service", "test-method", {"param": "value"})

    @pytest.mark.asyncio
    async def test_exception_for_parameter_mismatch(self, mock_communicator):
        """Test that an exception is raised for a parameter mismatch."""
        # Arrange
        mock_communicator.expect_request("test-service", "test-method", {"param": "expected"}, {"result": "success"})

        # Act & Assert
        with pytest.raises(AssertionError):
            await mock_communicator.send_request("test-service", "test-method", {"param": "actual"})

    @pytest.mark.asyncio
    async def test_predefined_exception(self, mock_communicator):
        """Test that a predefined exception is raised."""
        # Arrange
        exception = ServiceNotFoundError("test-service not found")
        mock_communicator.expect_request_exception("test-service", "test-method", {"param": "value"}, exception)

        # Act & Assert
        with pytest.raises(ServiceNotFoundError) as excinfo:
            await mock_communicator.send_request("test-service", "test-method", {"param": "value"})
        assert str(excinfo.value) == "test-service not found"
        mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_register_and_trigger_handler(self, mock_communicator):
        """Test registering and triggering a handler."""
        # Arrange
        handler_called = False
        received_params = None

        async def test_handler(params: Dict[str, Any]) -> None:
            nonlocal handler_called, received_params
            handler_called = True
            received_params = params

        await mock_communicator.register_handler("test-method", test_handler)

        # Act
        await mock_communicator.trigger_handler("test-method", {"param": "value"})

        # Assert
        assert handler_called
        assert received_params == {"param": "value"}

    @pytest.mark.asyncio
    async def test_reset(self, mock_communicator):
        """Test resetting the mock communicator."""
        # Arrange
        mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act
        mock_communicator.reset()

        # Assert
        with pytest.raises(AssertionError):
            await mock_communicator.send_request("test-service", "test-method", {"param": "value"})

    @pytest.mark.asyncio
    async def test_with_agent(self, agent_with_mock, mock_communicator):
        """Test using the mock communicator with an agent."""
        # Arrange
        agent = await agent_with_mock
        mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act
        result = await agent.communicator.send_request("test-service", "test-method", {"param": "value"})

        # Assert
        assert result == {"result": "success"}
        mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_multiple_expectations(self, mock_communicator):
        """Test handling multiple expectations in sequence."""
        # Arrange
        mock_communicator.expect_request("service1", "method1", {"param": "value1"}, {"result": "success1"})
        mock_communicator.expect_request("service2", "method2", {"param": "value2"}, {"result": "success2"})

        # Act
        result1 = await mock_communicator.send_request("service1", "method1", {"param": "value1"})
        result2 = await mock_communicator.send_request("service2", "method2", {"param": "value2"})

        # Assert
        assert result1 == {"result": "success1"}
        assert result2 == {"result": "success2"}
        mock_communicator.verify()

    @pytest.mark.asyncio
    async def test_verify_unmet_expectations(self, mock_communicator):
        """Test that verify raises an exception if expectations are not met."""
        # Arrange
        mock_communicator.expect_request("test-service", "test-method", {"param": "value"}, {"result": "success"})

        # Act & Assert
        with pytest.raises(AssertionError):
            mock_communicator.verify()
