"""Communication package for OpenMAS."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from openmas.communication.base import (
    _COMMUNICATOR_REGISTRY,
    BaseCommunicator,
    discover_communicator_extensions,
    discover_local_communicators,
    get_available_communicator_types,
    get_communicator_class,
    load_local_communicator,
    register_communicator,
)

# Import the guaranteed-available communicator
from openmas.communication.http import HttpCommunicator
from openmas.exceptions import DependencyError

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
        from openmas.communication.grpc.communicator import GrpcCommunicator

        # Register it if not already registered
        if "grpc" not in COMMUNICATOR_TYPES:
            register_communicator("grpc", GrpcCommunicator)
            COMMUNICATOR_TYPES["grpc"] = GrpcCommunicator

        return GrpcCommunicator
    except ImportError as e:
        # Provide a helpful error message about the missing dependency
        raise DependencyError(
            "The gRPC communicator requires the 'grpcio' and 'grpcio-tools' packages. "
            "Please install them using: pip install openmas[grpc]",
            dependency="grpcio",
            extras="grpc",
        ) from e


def _load_mqtt_communicator() -> Type[BaseCommunicator]:
    """Lazily load the MQTT communicator only when needed."""
    try:
        from openmas.communication.mqtt import MqttCommunicator

        # Register it if not already registered
        if "mqtt" not in COMMUNICATOR_TYPES:
            register_communicator("mqtt", MqttCommunicator)
            COMMUNICATOR_TYPES["mqtt"] = MqttCommunicator

        return MqttCommunicator
    except ImportError as e:
        # Provide a helpful error message about the missing dependency
        raise DependencyError(
            "The MQTT communicator requires the 'paho-mqtt' package. "
            "Please install it using: pip install openmas[mqtt]",
            dependency="paho-mqtt",
            extras="mqtt",
        ) from e


def _load_mcp_sse_communicator() -> Type[BaseCommunicator]:
    """Lazily load the MCP SSE communicator only when needed."""
    try:
        from openmas.communication.mcp.sse_communicator import McpSseCommunicator

        # Register it if not already registered
        if "mcp-sse" not in COMMUNICATOR_TYPES:
            register_communicator("mcp-sse", McpSseCommunicator)
            COMMUNICATOR_TYPES["mcp-sse"] = McpSseCommunicator

        return McpSseCommunicator
    except ImportError as e:
        # Check if it's specifically the mcp package that's missing
        if "mcp" in str(e):
            raise DependencyError(
                "The MCP SSE communicator requires the 'mcp' package. "
                "Please install it using: pip install openmas[mcp]",
                dependency="mcp",
                extras="mcp",
            ) from e
        # Otherwise, re-raise the original error
        raise DependencyError(
            f"Failed to load MCP SSE communicator: {e}. "
            f"Make sure you have the required dependencies installed: pip install openmas[mcp]",
            dependency="mcp",
            extras="mcp",
        ) from e


def _load_mcp_stdio_communicator() -> Type[BaseCommunicator]:
    """Lazily load the MCP STDIO communicator only when needed."""
    try:
        from openmas.communication.mcp.stdio_communicator import McpStdioCommunicator

        # Register it if not already registered
        if "mcp-stdio" not in COMMUNICATOR_TYPES:
            register_communicator("mcp-stdio", McpStdioCommunicator)
            COMMUNICATOR_TYPES["mcp-stdio"] = McpStdioCommunicator

        return McpStdioCommunicator
    except ImportError as e:
        # Check if it's specifically the mcp package that's missing
        if "mcp" in str(e):
            raise DependencyError(
                "The MCP STDIO communicator requires the 'mcp' package. "
                "Please install it using: pip install openmas[mcp]",
                dependency="mcp",
                extras="mcp",
            ) from e
        # Otherwise, re-raise the original error
        raise DependencyError(
            f"Failed to load MCP STDIO communicator: {e}. "
            f"Make sure you have the required dependencies installed: pip install openmas[mcp]",
            dependency="mcp",
            extras="mcp",
        ) from e


# Define lazy loaders for each communicator type
COMMUNICATOR_LOADERS = {
    "grpc": _load_grpc_communicator,
    "mqtt": _load_mqtt_communicator,
    "mcp-sse": _load_mcp_sse_communicator,
    "mcp-stdio": _load_mcp_stdio_communicator,
}


def create_communicator(
    communicator_type: str,
    agent_name: str,
    service_urls: Optional[Dict[str, str]] = None,
    server_mode: bool = False,
    http_port: int = 8000,
    server_instructions: Optional[str] = None,
    service_args: Optional[Dict[str, List[str]]] = None,
    **kwargs: Any,
) -> BaseCommunicator:
    """Create a communicator instance based on the specified type.

    This function creates and initializes a communicator of the specified type with
    the given configuration parameters.

    Args:
        communicator_type: The type of communicator to create
        agent_name: The name of the agent using the communicator
        service_urls: A mapping of service names to their URLs
        server_mode: Whether to operate in server mode
        http_port: The HTTP port to use (for HTTP-based communicators)
        server_instructions: Instructions for the server (for MCP communicators)
        service_args: Additional arguments for each service command (for stdio communicators)
        **kwargs: Additional keyword arguments to pass to the communicator

    Returns:
        An initialized communicator instance

    Raises:
        ValueError: If the communicator type is not found
        DependencyError: If the communicator requires dependencies that are not installed
    """
    service_urls = service_urls or {}
    service_args = service_args or {}

    # Get the communicator class
    communicator_class = get_communicator_by_type(communicator_type)

    # Initialize the appropriate communicator based on its type
    if communicator_type.startswith("mcp-"):
        # MCP communicators have a special init signature
        return communicator_class(
            agent_name=agent_name,
            service_urls=service_urls,
            server_mode=server_mode,
            server_instructions=server_instructions,
            service_args=service_args,
            **kwargs,
        )
    elif communicator_type == "http":
        # HTTP communicator doesn't accept these additional parameters
        return communicator_class(
            agent_name=agent_name,
            service_urls=service_urls,
            **kwargs,
        )
    else:
        # Default case for other communicator types
        return communicator_class(
            agent_name=agent_name,
            service_urls=service_urls,
            **kwargs,
        )


def get_communicator_by_type(communicator_type: str) -> Type[BaseCommunicator]:
    """Get a communicator class by type with lazy loading.

    This function follows a specific precedence order when searching for communicators:
    1. Built-in types (COMMUNICATOR_TYPES)
    2. Lazy-loaded built-in types (COMMUNICATOR_LOADERS)
    3. Local extensions (registered in _COMMUNICATOR_REGISTRY)
    4. Package entry points (discovered via entry points and added to _COMMUNICATOR_REGISTRY)

    Args:
        communicator_type: The type of communicator to get

    Returns:
        The communicator class

    Raises:
        ValueError: If the communicator type is not found
        DependencyError: If the communicator requires an optional dependency that is not installed
    """
    # Step 1: Check built-in types (highest precedence)
    if communicator_type in COMMUNICATOR_TYPES:
        return COMMUNICATOR_TYPES[communicator_type]

    # Step 2: Check if we have a lazy loader for built-in types
    if communicator_type in COMMUNICATOR_LOADERS:
        # Lazily load it - may raise DependencyError if dependencies are missing
        return COMMUNICATOR_LOADERS[communicator_type]()

    # Step 3: Check the registry (which includes extensions already discovered)
    if communicator_type in _COMMUNICATOR_REGISTRY:
        return _COMMUNICATOR_REGISTRY[communicator_type]

    # Step 4: Not found yet, try to discover communicator extensions from packages
    discover_communicator_extensions()
    # Check if the communicator is now in the registry after extension discovery
    if communicator_type in _COMMUNICATOR_REGISTRY:
        return _COMMUNICATOR_REGISTRY[communicator_type]

    # If we get here, the communicator type is really not found anywhere
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
    "discover_communicator_extensions",
    "discover_local_communicators",
    "load_local_communicator",
    "COMMUNICATOR_TYPES",
    "get_communicator_by_type",
    "create_communicator",
]

# Discover and register communicator extensions from installed packages
discover_communicator_extensions()
