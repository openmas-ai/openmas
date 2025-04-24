"""Communication module for SimpleMAS."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Type

from simple_mas.communication.base import (
    BaseCommunicator,
    discover_communicator_plugins,
    discover_local_communicators,
    get_available_communicator_types,
    get_communicator_class,
    load_local_communicator,
    register_communicator,
)

# Import the guaranteed-available communicator
from simple_mas.communication.http import HttpCommunicator

# Define available communicator types
COMMUNICATOR_TYPES: Dict[str, Type[BaseCommunicator]] = {
    "http": HttpCommunicator,
}

# Register the HTTP communicator
register_communicator("http", HttpCommunicator)

# Try to import gRPC communicator
try:
    from simple_mas.communication.grpc.communicator import GrpcCommunicator  # noqa: F401

    # Register gRPC communicator
    register_communicator("grpc", GrpcCommunicator)
    COMMUNICATOR_TYPES["grpc"] = GrpcCommunicator
except ImportError:
    # Define a stub for type checking
    if TYPE_CHECKING:

        class GrpcCommunicator(BaseCommunicator):  # type: ignore
            pass


# Try to import MCP communicators
try:
    from simple_mas.communication.mcp.sse_communicator import McpSseCommunicator  # noqa: F401
    from simple_mas.communication.mcp.stdio_communicator import McpStdioCommunicator  # noqa: F401

    # Add to available types
    COMMUNICATOR_TYPES["mcp-sse"] = McpSseCommunicator
    COMMUNICATOR_TYPES["mcp-stdio"] = McpStdioCommunicator
except ImportError:
    # Define stubs for type checking
    if TYPE_CHECKING:

        class McpSseCommunicator(BaseCommunicator):  # type: ignore
            pass

        class McpStdioCommunicator(BaseCommunicator):  # type: ignore
            pass


# Export all available communicator types
__all__ = [
    "BaseCommunicator",
    "HttpCommunicator",
    "GrpcCommunicator",
    "McpSseCommunicator",
    "McpStdioCommunicator",
    "register_communicator",
    "get_communicator_class",
    "get_available_communicator_types",
    "discover_communicator_plugins",
    "discover_local_communicators",
    "load_local_communicator",
    "COMMUNICATOR_TYPES",
]

# Discover and register communicator plugins from installed packages
discover_communicator_plugins()
