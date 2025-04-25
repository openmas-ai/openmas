"""MCP communicator implementations for OpenMAS."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Union

# For type checking only
if TYPE_CHECKING:
    from fastapi import FastAPI

    from openmas.communication.base import BaseCommunicator

# First check if MCP is installed
try:
    import mcp

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Then try to import the real classes if MCP is available
if HAS_MCP:
    try:
        from openmas.communication.mcp.sse_communicator import McpSseCommunicator
        from openmas.communication.mcp.stdio_communicator import McpStdioCommunicator

        __all__ = ["McpStdioCommunicator", "McpSseCommunicator"]
    except ImportError as e:
        # This is an unexpected error since MCP is available
        # Re-raise with more context
        raise ImportError(f"MCP is installed but failed to import MCP modules: {e}") from e
else:

    class McpStdioCommunicator:
        """Dummy class that raises ImportError when MCP is not installed."""

        def __init__(
            self,
            agent_name: str,
            service_urls: Dict[str, str],
            server_mode: bool = False,
            server_instructions: Optional[str] = None,
        ) -> None:
            """Raise ImportError when initialized.

            Args:
                agent_name: The name of the agent
                service_urls: Dictionary of service URLs
                server_mode: Whether to run in server mode
                server_instructions: Optional instructions for the server

            Raises:
                ImportError: Always raised since MCP is not installed
            """
            raise ImportError("MCP package is not installed. Install it with: pip install 'openmas[mcp]'")

    class McpSseCommunicator:
        """Dummy class that raises ImportError when MCP is not installed."""

        def __init__(
            self,
            agent_name: str,
            service_urls: Dict[str, str],
            server_mode: bool = False,
            http_port: int = 8000,
            server_instructions: Optional[str] = None,
            app: Optional["FastAPI"] = None,
        ) -> None:
            """Raise ImportError when initialized.

            Args:
                agent_name: The name of the agent
                service_urls: Dictionary of service URLs
                server_mode: Whether to run in server mode
                http_port: Port for the HTTP server
                server_instructions: Optional instructions for the server
                app: Optional FastAPI app to use

            Raises:
                ImportError: Always raised since MCP is not installed
            """
            raise ImportError("MCP package is not installed. Install it with: pip install 'openmas[mcp]'")

    __all__ = ["McpStdioCommunicator", "McpSseCommunicator"]
