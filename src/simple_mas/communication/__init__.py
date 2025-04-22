"""Communication module for SimpleMAS."""

from simple_mas.communication.base import (
    BaseCommunicator,
    discover_communicator_plugins,
    get_available_communicator_types,
    get_communicator_class,
    register_communicator,
)
from simple_mas.communication.http import HttpCommunicator

# Register built-in communicator types
register_communicator("http", HttpCommunicator)

# Try to import MCP components, but don't fail if the MCP package isn't installed
try:
    from simple_mas.communication.mcp import McpServerWrapper, McpSseCommunicator, McpStdioCommunicator

    # Register MCP communicator types if available
    register_communicator("mcp_sse", McpSseCommunicator)
    register_communicator("mcp_stdio", McpStdioCommunicator)

    __all__ = [
        "BaseCommunicator",
        "HttpCommunicator",
        "McpServerWrapper",
        "McpStdioCommunicator",
        "McpSseCommunicator",
        "register_communicator",
        "get_communicator_class",
        "get_available_communicator_types",
        "discover_communicator_plugins",
    ]
except ImportError:
    __all__ = [
        "BaseCommunicator",
        "HttpCommunicator",
        "register_communicator",
        "get_communicator_class",
        "get_available_communicator_types",
        "discover_communicator_plugins",
    ]

# Discover and register communicator plugins from installed packages
discover_communicator_plugins()
