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
    from simple_mas.communication.mcp import McpSseCommunicator, McpStdioCommunicator

    # Register MCP communicator types if available
    register_communicator("mcp_sse", McpSseCommunicator)
    register_communicator("mcp_stdio", McpStdioCommunicator)

    mcp_available = True
except ImportError:
    mcp_available = False

# Try to import gRPC components, but don't fail if gRPC packages aren't installed
try:
    from simple_mas.communication.grpc import GrpcCommunicator

    # Register gRPC communicator type if available
    register_communicator("grpc", GrpcCommunicator)

    grpc_available = True
except ImportError:
    grpc_available = False

# Define __all__ based on available modules
all_list = [
    "BaseCommunicator",
    "HttpCommunicator",
    "register_communicator",
    "get_communicator_class",
    "get_available_communicator_types",
    "discover_communicator_plugins",
]

if mcp_available:
    all_list.extend(["McpStdioCommunicator", "McpSseCommunicator"])

if grpc_available:
    all_list.append("GrpcCommunicator")

__all__ = all_list

# Discover and register communicator plugins from installed packages
discover_communicator_plugins()
