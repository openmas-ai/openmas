"""MCP Server Agent implementation for OpenMAS.

This module provides a server-side Model Context Protocol (MCP) agent implementation that can be used
to expose functionality to MCP clients (like Claude) using FastMCP.
"""

import asyncio
from typing import Any, Dict, Optional

from openmas.agent.mcp import McpAgent
from openmas.exceptions import ConfigurationError


class McpServerAgent(McpAgent):
    """Server agent that exposes MCP tools, prompts, and resources.

    This specialized agent is designed to run as an MCP server, exposing functionality
    through tools, prompts, and resources that can be accessed by MCP clients.

    It leverages the base McpAgent functionality for discovering decorated methods
    and works with McpSseCommunicator or McpStdioCommunicator in server mode to handle
    the actual server setup and communication.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        server_type: str = "sse",
        host: str = "0.0.0.0",
        port: int = 8000,
        **kwargs: Any,
    ):
        """Initialize the MCP server agent.

        Args:
            name: Optional name for the agent
            config: Optional configuration for the agent
            server_type: The type of server to create ('sse' or 'stdio')
            host: The host to bind to (for 'sse' server type)
            port: The port to bind to (for 'sse' server type)
            **kwargs: Additional keyword arguments for the parent class
        """
        super().__init__(name=name, config=config, **kwargs)

        self.server_type = server_type
        self.host = host
        self.port = port

        # Set server mode flag to help the communicator know it should act as a server
        self._server_mode = True

    def setup_communicator(self, instructions: Optional[str] = None) -> None:
        """Set up the appropriate communicator based on server_type.

        Args:
            instructions: Optional instructions for the MCP server

        Raises:
            ImportError: If required dependencies are not installed
            ConfigurationError: If server_type is not supported
        """
        try:
            from openmas.communication import BaseCommunicator
            from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
        except ImportError as e:
            raise ImportError(
                f"Failed to import MCP communicator dependencies: {e}. "
                "Make sure 'mcp' is installed: `poetry add mcp`"
            ) from e

        # Variable to store the created communicator
        comm: BaseCommunicator

        if self.server_type.lower() == "sse":
            try:
                # We need to verify FastAPI is installed but don't need to use it directly
                import fastapi  # noqa: F401
            except ImportError as e:
                raise ImportError(
                    f"FastAPI is required for SSE server mode but not installed: {e}. "
                    "Install it with: `poetry add fastapi uvicorn`"
                ) from e

            # Create SSE communicator in server mode
            comm = McpSseCommunicator(
                agent_name=self.name,
                service_urls={},  # Empty as we're a server
                server_mode=True,
                http_port=self.port,
                server_instructions=instructions,
            )

        elif self.server_type.lower() == "stdio":
            # Create stdio communicator in server mode
            comm = McpStdioCommunicator(
                agent_name=self.name,
                service_urls={},  # Empty as we're a server
                server_mode=True,
                server_instructions=instructions,
            )

        else:
            raise ConfigurationError(f"Unsupported server type: {self.server_type}")

        # Set the communicator for this agent
        self.set_communicator(comm)

    async def start_server(self, instructions: Optional[str] = None) -> None:
        """Start the MCP server.

        This is a convenience method that sets up the communicator if needed
        and starts it.

        Args:
            instructions: Optional instructions for the MCP server

        Raises:
            RuntimeError: If server fails to start
        """
        # Set up communicator if not done already
        if not self.communicator:
            try:
                self.setup_communicator(instructions)
            except Exception as e:
                self.logger.error(f"Failed to setup MCP server communicator: {e}")
                raise RuntimeError(f"Failed to setup MCP server: {e}") from e

        # Ensure we've discovered and prepared MCP methods
        self._discover_mcp_methods()

        try:
            # Start the communicator (which starts the server)
            await self.communicator.start()
            self.logger.info(
                f"MCP {self.server_type} server started for agent {self.name}"
                + (f" on port {self.port}" if self.server_type.lower() == "sse" else "")
            )
        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            raise RuntimeError(f"Failed to start MCP server: {e}") from e

    async def stop_server(self) -> None:
        """Stop the MCP server.

        This is a convenience method that stops the communicator,
        which in turn stops the server.
        """
        if self.communicator:
            try:
                await self.communicator.stop()
                self.logger.info(f"MCP {self.server_type} server stopped for agent {self.name}")
            except Exception as e:
                self.logger.error(f"Error while stopping MCP server: {e}")
                # Continue with shutdown even if there was an error

    async def shutdown(self) -> None:
        """Shutdown the agent, including stopping the server if running."""
        # Stop the server if it's running
        await self.stop_server()

        # Call the parent shutdown
        await super().shutdown()

    async def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Wait until the server is ready to accept connections.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if the server is ready, False if timed out
        """
        if not hasattr(self.communicator, "_server_task"):
            return False

        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if getattr(self.communicator, "_server") is not None:
                return True
            await asyncio.sleep(0.1)

        return False
