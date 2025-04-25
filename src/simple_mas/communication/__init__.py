"""Communication module for SimpleMAS."""

from __future__ import annotations

import importlib
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


# Lazy loading functions for other communicator types
def _load_grpc_communicator() -> Type[BaseCommunicator]:
    """Lazily load the gRPC communicator only when needed."""
    try:
        from simple_mas.communication.grpc.communicator import GrpcCommunicator

        # Register it if not already registered
        if "grpc" not in COMMUNICATOR_TYPES:
            register_communicator("grpc", GrpcCommunicator)
            COMMUNICATOR_TYPES["grpc"] = GrpcCommunicator

        return GrpcCommunicator
    except ImportError as e:
        raise ImportError(f"Could not import gRPC communicator: {e}") from e


def _load_mcp_sse_communicator() -> Type[BaseCommunicator]:
    """Lazily load the MCP SSE communicator only when needed."""
    try:
        from simple_mas.communication.mcp.sse_communicator import McpSseCommunicator

        # Register it if not already registered
        if "mcp-sse" not in COMMUNICATOR_TYPES:
            register_communicator("mcp-sse", McpSseCommunicator)
            COMMUNICATOR_TYPES["mcp-sse"] = McpSseCommunicator

        return McpSseCommunicator
    except ImportError as e:
        raise ImportError(f"Could not import MCP SSE communicator: {e}") from e


def _load_mcp_stdio_communicator() -> Type[BaseCommunicator]:
    """Lazily load the MCP STDIO communicator only when needed."""
    try:
        from simple_mas.communication.mcp.stdio_communicator import McpStdioCommunicator

        # Register it if not already registered
        if "mcp-stdio" not in COMMUNICATOR_TYPES:
            register_communicator("mcp-stdio", McpStdioCommunicator)
            COMMUNICATOR_TYPES["mcp-stdio"] = McpStdioCommunicator

        return McpStdioCommunicator
    except ImportError as e:
        raise ImportError(f"Could not import MCP STDIO communicator: {e}") from e


# Define lazy loaders for each communicator type
COMMUNICATOR_LOADERS = {
    "grpc": _load_grpc_communicator,
    "mcp-sse": _load_mcp_sse_communicator,
    "mcp-stdio": _load_mcp_stdio_communicator,
}


def get_communicator_by_type(communicator_type: str) -> Type[BaseCommunicator]:
    """Get a communicator class by type with lazy loading.

    Args:
        communicator_type: The type of communicator to get

    Returns:
        The communicator class

    Raises:
        ValueError: If the communicator type is not found
    """
    # Check if already loaded
    if communicator_type in COMMUNICATOR_TYPES:
        return COMMUNICATOR_TYPES[communicator_type]

    # Check if we have a loader for it
    if communicator_type in COMMUNICATOR_LOADERS:
        # Lazily load it
        return COMMUNICATOR_LOADERS[communicator_type]()

    # Not found and no loader, try standard registry
    try:
        return get_communicator_class(communicator_type)
    except ValueError:
        # One last attempt - try to discover communicator plugins
        discover_communicator_plugins()
        try:
            return get_communicator_class(communicator_type)
        except ValueError:
            # If we get here, the communicator type is really not found
            from simple_mas.communication.base import _COMMUNICATOR_REGISTRY

            available_types = ", ".join(sorted(list(_COMMUNICATOR_REGISTRY.keys())))
            available = available_types or "none"
            message = (
                f"Communicator type '{communicator_type}' not found. "
                f"Available types: {available}. "
                f"Check your configuration or provide a valid communicator_class."
            )
            raise ValueError(message)


# Export all available communicator types
__all__ = [
    "BaseCommunicator",
    "HttpCommunicator",
    "register_communicator",
    "get_communicator_class",
    "get_available_communicator_types",
    "discover_communicator_plugins",
    "discover_local_communicators",
    "load_local_communicator",
    "COMMUNICATOR_TYPES",
    "get_communicator_by_type",
]

# Discover and register communicator plugins from installed packages
discover_communicator_plugins()
