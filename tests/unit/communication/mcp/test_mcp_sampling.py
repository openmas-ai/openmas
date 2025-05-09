"""Tests for MCP sampling functionality."""

import asyncio
from unittest import mock

import pytest

from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
from openmas.exceptions import CommunicationError


# Create a simple class to use for mocking TextContent
class MockTextContent:
    """Mock for TextContent class from MCP package."""

    def __init__(self, type="text", text=""):
        self.type = type
        self.text = text


# DO NOT apply global mocks - manage per test
# from tests.unit.communication.mcp.mcp_mocks import apply_mcp_mocks
# apply_mcp_mocks()

# @pytest.fixture
# def mock_session():
#     pass # Fixture not needed if mocks are per-test


class TestMcpSampling:
    """Test MCP sampling integration."""

    @pytest.mark.asyncio
    async def test_sample_prompt_sse(self):
        """Test sample_prompt method in McpSseCommunicator."""
        communicator = McpSseCommunicator(
            agent_name="test_agent", service_urls={"test_service": "http://localhost:8000"}
        )
        mock_result = mock.MagicMock()
        mock_result.isError = False
        mock_text_block = mock.MagicMock()
        mock_text_block.text = "This is a test response"
        mock_result.content = [mock_text_block]

        # Explicitly patch dependencies for this test
        with (
            mock.patch.object(communicator, "clients", {"test_service": mock.MagicMock()}),
            mock.patch.object(communicator, "sessions", {"test_service": mock.AsyncMock()}),
        ):
            # Configure mock session
            mock_session = communicator.sessions["test_service"]
            mock_session.sample.return_value = mock_result

            # Test the sample_prompt method
            messages = [{"role": "user", "content": "Hello, how are you?"}]
            result = await communicator.sample_prompt(target_service="test_service", messages=messages, temperature=0.7)

            # Check mocks and result
            mock_session.sample.assert_awaited_once()
            assert result == {"content": "This is a test response"}

    @pytest.mark.asyncio
    async def test_sample_prompt_stdio(self):
        """Test sample_prompt method in McpStdioCommunicator."""
        communicator = McpStdioCommunicator(agent_name="test_agent", service_urls={"test_service": "stdio:app"})
        mock_result = mock.MagicMock()
        mock_result.isError = False
        mock_text_block = mock.MagicMock()
        mock_text_block.text = "This is a test response"
        mock_result.content = [mock_text_block]

        # Explicitly patch dependencies for this test
        with (
            mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client") as mock_stdio_client_func,
            mock.patch(
                "openmas.communication.mcp.stdio_communicator.ClientSession", new_callable=mock.MagicMock
            ) as mock_session_class,
            mock.patch("openmas.communication.mcp.stdio_communicator.TextContent", new=MockTextContent),
            mock.patch("shutil.which") as mock_shutil_which,
        ):
            mock_shutil_which.return_value = "/usr/bin/stdio_app_dummy"

            # Configure stdio_client mock
            mock_stdio_manager = mock.AsyncMock()
            mock_read_stream = mock.AsyncMock()
            mock_write_stream = mock.AsyncMock()
            mock_stdio_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)
            mock_stdio_client_func.return_value = mock_stdio_manager

            # Configure ClientSession instance
            mock_session_instance = mock.AsyncMock()
            mock_session_instance.sample.return_value = mock_result
            mock_session_instance.__aenter__.return_value = mock_session_instance
            mock_session_instance.__aexit__ = mock.AsyncMock()
            mock_session_class.return_value = mock_session_instance

            # Test the sample_prompt method
            messages = [{"role": "user", "content": "Hi there"}]
            result = await communicator.sample_prompt(target_service="test_service", messages=messages)

            # Check mocks and result
            mock_stdio_client_func.assert_called_once()
            mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
            mock_session_instance.initialize.assert_awaited_once()
            mock_session_instance.sample.assert_awaited_once()
            assert result == {"content": "This is a test response"}
            mock_session_instance.__aexit__.assert_awaited_once()
            mock_stdio_manager.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sample_prompt_textcontent(self):
        """Test sample_prompt method with TextContent objects."""
        communicator = McpSseCommunicator(
            agent_name="test_agent", service_urls={"test_service": "http://localhost:8000"}
        )
        mock_result = mock.MagicMock()
        mock_result.isError = False
        mock_text_block = mock.MagicMock()
        mock_text_block.text = "This is a test response"
        mock_result.content = [mock_text_block]

        # Create a mock TextContent object for input
        mock_text_content = MockTextContent(text="Hello, how are you?")

        # Explicitly patch dependencies
        with (
            mock.patch.object(communicator, "clients", {"test_service": mock.MagicMock()}),
            mock.patch.object(communicator, "sessions", {"test_service": mock.AsyncMock()}),
            mock.patch("openmas.communication.mcp.sse_communicator.TextContent", new=MockTextContent),
        ):
            # Configure mock session
            mock_session = communicator.sessions["test_service"]
            mock_session.sample.return_value = mock_result

            # Test with mocked TextContent input
            messages = [{"role": "user", "content": mock_text_content}]
            result = await communicator.sample_prompt(target_service="test_service", messages=messages, temperature=0.7)

            # Check sample was called
            mock_session.sample.assert_awaited_once()
            # Check result
            assert result == {"content": "This is a test response"}

    @pytest.mark.asyncio
    async def test_sample_prompt_error_connect(self):
        """Test connection error during client session usage."""
        communicator = McpSseCommunicator(
            agent_name="test_agent", service_urls={"test_service": "http://localhost:8000"}
        )
        messages = [{"role": "user", "content": "hi"}]

        # Mock client and session with error
        with (
            mock.patch.object(communicator, "clients", {"test_service": mock.MagicMock()}),
            mock.patch.object(communicator, "sessions", {"test_service": mock.AsyncMock()}),
        ):
            # Configure mock session to raise an error
            mock_session = communicator.sessions["test_service"]
            mock_session.sample.side_effect = ConnectionError("Test connection error")

            with pytest.raises(CommunicationError, match="Error during MCP sampling.*Test connection error"):
                await communicator.sample_prompt(target_service="test_service", messages=messages)

    @pytest.mark.asyncio
    async def test_sample_prompt_error_initialize(self):
        """Test timeout error during sample call."""
        communicator = McpSseCommunicator(
            agent_name="test_agent", service_urls={"test_service": "http://localhost:8000"}
        )
        messages = [{"role": "user", "content": "hi"}]

        # Mock client and session with error
        with (
            mock.patch.object(communicator, "clients", {"test_service": mock.MagicMock()}),
            mock.patch.object(communicator, "sessions", {"test_service": mock.AsyncMock()}),
        ):
            # Configure mock session to raise timeout error
            mock_session = communicator.sessions["test_service"]
            mock_session.sample.side_effect = asyncio.TimeoutError("Session sample timeout")

            # Expect CommunicationError wrapping the TimeoutError
            with pytest.raises(CommunicationError, match="Timeout during MCP sampling"):
                await communicator.sample_prompt(target_service="test_service", messages=messages)

    @pytest.mark.asyncio
    async def test_sample_prompt_error_sample(self):
        """Test error during session sample."""
        communicator = McpSseCommunicator(
            agent_name="test_agent", service_urls={"test_service": "http://localhost:8000"}
        )
        messages = [{"role": "user", "content": "hi"}]

        # Instead of mocking the async context managers directly,
        # we'll patch the _send_mcp_request method which is called by sample_prompt
        with mock.patch.object(communicator, "_send_mcp_request") as mock_send_request:
            # Configure the mock to raise a RuntimeError
            mock_send_request.side_effect = RuntimeError("Sampling failed")

            # Test that the exception is properly caught and wrapped
            with pytest.raises(
                CommunicationError, match="Failed MCP request to service 'test_service' method 'prompt/sample'"
            ):
                await communicator.sample_prompt(target_service="test_service", messages=messages)

            # Verify the mock was called with expected parameters
            mock_send_request.assert_called_once()
            # Verify first argument (target_service)
            assert mock_send_request.call_args[0][0] == "test_service"
            # Verify second argument (method) is "prompt/sample"
            assert mock_send_request.call_args[0][1] == "prompt/sample"
            # Verify messages are in the parameters
            assert "messages" in mock_send_request.call_args[0][2]
