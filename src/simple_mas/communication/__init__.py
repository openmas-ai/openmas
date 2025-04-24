"""Communication module for SimpleMAS."""

from simple_mas.communication.base import (
    BaseCommunicator,
    discover_communicator_plugins,
    discover_local_communicators,
    get_available_communicator_types,
    get_communicator_class,
    load_local_communicator,
    register_communicator,
)

# Import communicators conditionally to handle missing dependencies
try:
    from simple_mas.communication.grpc import GrpcCommunicator
except ImportError:
    GrpcCommunicator = None

try:
    from simple_mas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
except ImportError:
    McpSseCommunicator = None
    McpStdioCommunicator = None

from simple_mas.communication.http import HttpCommunicator

# Register built-in communicator types
register_communicator("http", HttpCommunicator)

__all__ = [
    "BaseCommunicator",
    "GrpcCommunicator",
    "HttpCommunicator",
    "McpSseCommunicator",
    "McpStdioCommunicator",
    "register_communicator",
    "get_communicator_class",
    "get_available_communicator_types",
    "discover_communicator_plugins",
    "discover_local_communicators",
    "load_local_communicator",
]

# Discover and register communicator plugins from installed packages
discover_communicator_plugins()
