"""Unit tests for McpServerAgent."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.agent.mcp_server import McpServerAgent
from openmas.config import AgentConfig
from openmas.exceptions import ConfigurationError


class TestMcpServerAgent:
    """Test suite for McpServerAgent."""

    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    def test_init_default_values(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test initialization with default values."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_config.extension_paths = []
        mock_config.shared_paths = []
        mock_config.prompts = None
        mock_config.prompts_dir = None
        mock_config.sampling = None
        mock_config.required_assets = []
        mock_load_config.return_value = mock_config

        # Create agent with mocked config
        agent = McpServerAgent(name="test_server")

        assert agent.name == "test_server"
        assert agent.server_type == "sse"
        assert agent.host == "0.0.0.0"
        assert agent.port == 8000
        assert agent._server_mode is True

    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    def test_init_custom_values(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test initialization with custom values."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "custom_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_config.extension_paths = []
        mock_config.shared_paths = []
        mock_config.prompts = None
        mock_config.prompts_dir = None
        mock_config.sampling = None
        mock_config.required_assets = []
        mock_load_config.return_value = mock_config

        # Create agent with mocked config and custom values
        agent = McpServerAgent(name="custom_server", server_type="stdio", host="127.0.0.1", port=9000)

        assert agent.name == "custom_server"
        assert agent.server_type == "stdio"
        assert agent.host == "127.0.0.1"
        assert agent.port == 9000
        assert agent._server_mode is True

    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    @patch("openmas.communication.mcp.McpSseCommunicator")
    def test_setup_communicator_sse(self, mock_sse_comm, mock_cwd, mock_configure_logging, mock_load_config):
        """Test setup_communicator with SSE server type."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "sse_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create the communicator instance to be returned by the mock
        mock_comm_instance = MagicMock()
        mock_sse_comm.return_value = mock_comm_instance

        # Create agent
        agent = McpServerAgent(name="sse_server", server_type="sse", port=8888)

        # Call setup_communicator
        agent.setup_communicator(instructions="Test instructions")

        # Verify the SSE communicator was created with the right parameters
        mock_sse_comm.assert_called_once_with(
            agent_name="sse_server",
            service_urls={},
            server_mode=True,
            http_port=8888,
            server_instructions="Test instructions",
        )

        # Verify set_communicator was called
        assert agent.communicator == mock_comm_instance

    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    @patch("openmas.communication.mcp.McpStdioCommunicator")
    def test_setup_communicator_stdio(self, mock_stdio_comm, mock_cwd, mock_configure_logging, mock_load_config):
        """Test setup_communicator with stdio server type."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "stdio_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create the communicator instance to be returned by the mock
        mock_comm_instance = MagicMock()
        mock_stdio_comm.return_value = mock_comm_instance

        # Create agent
        agent = McpServerAgent(name="stdio_server", server_type="stdio")

        # Call setup_communicator
        agent.setup_communicator(instructions="Test instructions")

        # Verify the stdio communicator was created with the right parameters
        mock_stdio_comm.assert_called_once_with(
            agent_name="stdio_server", service_urls={}, server_mode=True, server_instructions="Test instructions"
        )

        # Verify set_communicator was called
        assert agent.communicator == mock_comm_instance

    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    def test_setup_communicator_invalid_type(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test setup_communicator with an invalid server type."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "invalid_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent with invalid server type
        agent = McpServerAgent(name="invalid_server", server_type="invalid")

        # Verify that the correct exception is raised
        with pytest.raises(ConfigurationError, match="Unsupported server type: invalid"):
            agent.setup_communicator()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_start_server_success(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test start_server when successfully starting the server."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent
        agent = McpServerAgent(name="test_server")

        # Set communicator to None to ensure setup_communicator gets called
        agent.communicator = None

        # Mock setup_communicator and _discover_mcp_methods
        agent.setup_communicator = MagicMock()
        agent._discover_mcp_methods = MagicMock()

        # Create mock communicator
        mock_communicator = AsyncMock()

        # Make setup_communicator set the communicator
        def mock_setup(instructions=None, **kwargs):
            agent.communicator = mock_communicator

        agent.setup_communicator.side_effect = mock_setup

        # Call start_server
        await agent.start_server(instructions="Test instructions")

        # Verify setup_communicator was called if communicator wasn't set
        agent.setup_communicator.assert_called_once_with("Test instructions")

        # Verify methods were called in the right order
        agent._discover_mcp_methods.assert_called_once()
        mock_communicator.start.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_start_server_setup_failure(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test start_server when setup_communicator fails."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent without communicator
        agent = McpServerAgent(name="test_server")
        agent.communicator = None

        # Setup mock for setup_communicator that raises an exception
        agent.setup_communicator = MagicMock(side_effect=ImportError("Test import error"))

        # Verify the correct exception is raised
        with pytest.raises(RuntimeError, match="Failed to setup MCP server: Test import error"):
            await agent.start_server()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_start_server_start_failure(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test start_server when communicator.start() fails."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent
        agent = McpServerAgent(name="test_server")

        # Mock setup_communicator and _discover_mcp_methods
        agent.setup_communicator = MagicMock()
        agent._discover_mcp_methods = MagicMock()

        # Create mock communicator that raises an exception on start
        mock_communicator = AsyncMock()
        mock_communicator.start.side_effect = Exception("Failed to start")
        agent.communicator = mock_communicator

        # Verify the correct exception is raised
        with pytest.raises(RuntimeError, match="Failed to start MCP server: Failed to start"):
            await agent.start_server()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_stop_server(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test stop_server method."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent with mock communicator
        agent = McpServerAgent(name="test_server")
        mock_communicator = AsyncMock()
        agent.communicator = mock_communicator

        # Call stop_server
        await agent.stop_server()

        # Verify communicator.stop was called
        mock_communicator.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_stop_server_error(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test stop_server when an error occurs."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent with mock communicator that raises an exception
        agent = McpServerAgent(name="test_server")
        mock_communicator = AsyncMock()
        mock_communicator.stop.side_effect = Exception("Failed to stop")
        agent.communicator = mock_communicator

        # Call stop_server - should not raise exception despite the error
        await agent.stop_server()

        # Verify communicator.stop was called
        mock_communicator.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_shutdown(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test shutdown method."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent with mocked methods
        agent = McpServerAgent(name="test_server")
        agent.stop_server = AsyncMock()

        # Mock super().shutdown() as well
        with patch("openmas.agent.mcp.McpAgent.shutdown", new_callable=AsyncMock) as mock_super_shutdown:
            # Call shutdown
            await agent.shutdown()

            # Verify stop_server and parent's shutdown were called
            agent.stop_server.assert_called_once()
            mock_super_shutdown.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    @patch("asyncio.get_event_loop")
    async def test_wait_until_ready_success(self, mock_get_loop, mock_cwd, mock_configure_logging, mock_load_config):
        """Test wait_until_ready when server is ready."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent
        agent = McpServerAgent(name="test_server")

        # Create mock communicator with _server_task and _server attributes
        mock_communicator = MagicMock()
        mock_communicator._server_task = AsyncMock()
        mock_communicator._server = MagicMock()  # Server is ready
        agent.communicator = mock_communicator

        # Setup mock for asyncio.get_event_loop().time()
        mock_loop = MagicMock()
        mock_loop.time.return_value = 100.0  # Start time
        mock_get_loop.return_value = mock_loop

        # Call wait_until_ready
        result = await agent.wait_until_ready(timeout=1.0)

        # Verify result is True (server is ready)
        assert result is True

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    @patch("asyncio.get_event_loop")
    @patch("asyncio.sleep")
    async def test_wait_until_ready_timeout(
        self, mock_sleep, mock_get_loop, mock_cwd, mock_configure_logging, mock_load_config
    ):
        """Test wait_until_ready when timeout occurs."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent
        agent = McpServerAgent(name="test_server")

        # Create mock communicator with _server_task but _server is None (not ready)
        mock_communicator = MagicMock()
        mock_communicator._server_task = AsyncMock()
        mock_communicator._server = None
        agent.communicator = mock_communicator

        # Setup mock for asyncio.get_event_loop().time()
        mock_loop = MagicMock()
        start_time = 100.0
        mock_loop.time.side_effect = [
            start_time,
            start_time + 0.5,
            start_time + 1.5,
        ]  # Start, first check, second check (timeout)
        mock_get_loop.return_value = mock_loop

        # Call wait_until_ready with timeout
        result = await agent.wait_until_ready(timeout=1.0)

        # Verify result is False (server not ready before timeout)
        assert result is False

        # Verify sleep was called
        mock_sleep.assert_called_with(0.1)

    @pytest.mark.asyncio
    @patch("openmas.agent.base.load_config")
    @patch("openmas.agent.base.configure_logging")
    @patch("pathlib.Path.cwd")
    async def test_wait_until_ready_no_server_task(self, mock_cwd, mock_configure_logging, mock_load_config):
        """Test wait_until_ready when _server_task doesn't exist."""
        # Mock Path.cwd() to return a fixed path
        mock_cwd.return_value = Path("/fake/project/path")

        # Mock the config that would be loaded
        mock_config = MagicMock(spec=AgentConfig)
        mock_config.name = "test_server"
        mock_config.log_level = "INFO"
        mock_config.service_urls = {}
        mock_config.communicator_type = "http"
        mock_config.communicator_options = {}
        mock_load_config.return_value = mock_config

        # Create agent
        agent = McpServerAgent(name="test_server")

        # Use Python's builtin hasattr to control the check in wait_until_ready
        with patch("builtins.hasattr", lambda obj, attr: False if attr == "_server_task" else True):
            # Call wait_until_ready
            result = await agent.wait_until_ready(timeout=1.0)

            # Verify result is False (no server task)
            assert result is False
