"""MCP communicator implementations for SimpleMAS."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Union

# For type checking only
if TYPE_CHECKING:
    from simple_mas.communication.base import BaseCommunicator

# Try to import the real classes
try:
    from simple_mas.communication.mcp.mcp_adapter import McpClientAdapter, McpServerWrapper

    __all__ = ["McpClientAdapter", "McpServerWrapper"]
except ImportError:
    # Define dummy classes that raise ImportError when used
    class McpClientAdapter:
        """Dummy class that raises ImportError when MCP is not installed."""

        def __init__(self, agent_name: str, service_urls: Dict[str, str], use_sse: bool = False) -> None:
            """Raise ImportError when initialized.

            Args:
                agent_name: The name of the agent
                service_urls: Dictionary of service URLs
                use_sse: Whether to use SSE

            Raises:
                ImportError: Always raised since MCP is not installed
            """
            raise ImportError("MCP package is not installed")

    class McpServerWrapper:
        """Dummy class that raises ImportError when MCP is not installed."""

        def __init__(self, name: str, instructions: Optional[str] = None) -> None:
            """Raise ImportError when initialized.

            Args:
                name: The name of the server
                instructions: Optional instructions for the server

            Raises:
                ImportError: Always raised since MCP is not installed
            """
            raise ImportError("MCP package is not installed")

    __all__ = ["McpClientAdapter", "McpServerWrapper"]
