"""MCP Agent implementation for the SimpleMAS framework.

This module provides a Model Context Protocol (MCP) agent implementation that allows
for easy integration with Claude and other AI assistants that support the MCP protocol.
It includes decorators for defining tools, prompts, and resources that can be exposed
through an MCP-compatible API.
"""

import asyncio
import functools
import inspect
from typing import Any, Callable, Optional, Type, get_type_hints

from pydantic import BaseModel, create_model

from simple_mas.agent.base import BaseAgent
from simple_mas.communication.base import BaseCommunicator
from simple_mas.logging import get_logger

logger = get_logger(__name__)


def _create_pydantic_model_from_signature(func: Callable, model_name: str = None) -> Type[BaseModel]:
    """Create a Pydantic model from a function's signature.

    Args:
        func: The function to create a model from
        model_name: Optional name for the model

    Returns:
        A Pydantic model class
    """
    if model_name is None:
        model_name = f"{func.__name__}Model"

    signature = inspect.signature(func)
    type_hints = get_type_hints(func)

    # Skip self/cls parameter for methods
    fields = {}
    for name, param in signature.parameters.items():
        if name in ("self", "cls"):
            continue

        field_type = type_hints.get(name, Any)
        default = ... if param.default is param.empty else param.default
        fields[name] = (field_type, default)

    return create_model(model_name, **fields)


def mcp_tool(
    name: str = None,
    description: str = None,
    input_model: Type[BaseModel] = None,
    output_model: Optional[Type[BaseModel]] = ...,
) -> Callable:
    """Decorator to mark a method as an MCP tool.

    Args:
        name: Optional name for the tool (defaults to method name)
        description: Description of the tool
        input_model: Optional Pydantic model for input validation
        output_model: Optional Pydantic model for output validation

    Returns:
        Decorated method
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Create input model from signature if not provided
            nonlocal input_model
            if input_model is None:
                input_model = _create_pydantic_model_from_signature(func, f"{func.__name__}Input")

            # Validate input if we have positional args
            if args:
                # Convert positional args to kwargs based on signature
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())[1:]  # Skip 'self'
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        kwargs[param_names[i]] = arg

            # Validate kwargs with input model
            validated_input = input_model(**kwargs)
            validated_kwargs = validated_input.model_dump()

            # Call the original function
            result = await func(self, **validated_kwargs)

            # Validate output if output_model is provided and not None
            if output_model is not ... and output_model is not None:
                if isinstance(result, dict):
                    result = output_model(**result)
                    return result.model_dump()
                else:
                    # Try to convert result to dict if it's not already
                    result = output_model(result).model_dump()

            return result

        # Store metadata for MCP registration
        wrapper._mcp_type = "tool"
        wrapper._mcp_name = name if name else func.__name__
        wrapper._mcp_description = description if description else func.__doc__
        wrapper._mcp_input_model = input_model

        # Only set _mcp_output_model if it was explicitly provided
        if output_model is not ...:
            wrapper._mcp_output_model = output_model

        return wrapper

    return decorator


def mcp_prompt(
    name: str = None,
    description: str = None,
    input_model: Type[BaseModel] = None,
) -> Callable:
    """Decorator to mark a method as an MCP prompt.

    Args:
        name: Optional name for the prompt (defaults to method name)
        description: Description of the prompt
        input_model: Optional Pydantic model for input validation

    Returns:
        Decorated method
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Create input model from signature if not provided
            nonlocal input_model
            if input_model is None:
                input_model = _create_pydantic_model_from_signature(func, f"{func.__name__}Input")

            # Validate input if we have positional args
            if args:
                # Convert positional args to kwargs based on signature
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())[1:]  # Skip 'self'
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        kwargs[param_names[i]] = arg

            # Validate kwargs with input model
            validated_input = input_model(**kwargs)
            validated_kwargs = validated_input.model_dump()

            # Call the original function
            result = await func(self, **validated_kwargs)
            return result

        # Store metadata for MCP registration
        wrapper._mcp_type = "prompt"
        wrapper._mcp_name = name if name else func.__name__
        wrapper._mcp_description = description if description else func.__doc__
        wrapper._mcp_input_model = input_model

        return wrapper

    return decorator


def mcp_resource(
    uri: str,
    description: str = None,
    mime_type: str = "application/octet-stream",
) -> Callable:
    """Decorator to mark a method as an MCP resource.

    Args:
        uri: URI path for the resource
        description: Description of the resource
        mime_type: MIME type for the resource

    Returns:
        Decorated method
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Call the original function
            result = await func(self, *args, **kwargs)
            return result

        # Store metadata for MCP registration
        wrapper._mcp_type = "resource"
        wrapper._mcp_uri = uri
        wrapper._mcp_description = description if description else func.__doc__
        wrapper._mcp_mime_type = mime_type

        return wrapper

    return decorator


class McpAgent(BaseAgent):
    """Base class for MCP-enabled agents.

    This agent class provides functionality for registering methods as MCP tools,
    prompts, and resources, and exposing them through an MCP-compatible API.
    """

    def __init__(self, name_or_config):
        """Initialize the MCP agent.

        Args:
            name_or_config: Either the name of the agent or an AgentConfig object
        """
        # If name_or_config is a string, it's the agent name
        # Otherwise, it should be an AgentConfig object
        if isinstance(name_or_config, str):
            from simple_mas.config import AgentConfig

            config = AgentConfig(name=name_or_config, log_level="INFO", service_urls={})
            super().__init__(config=config)
        else:
            # It's already a config object
            super().__init__(config=name_or_config)

        self.logger = get_logger(f"mcp_agent.{self.name}")
        self._communicator = None
        self._mcp_methods = {"tools": [], "prompts": [], "resources": []}
        self._discover_mcp_methods()

    def _discover_mcp_methods(self) -> None:
        """Discover all MCP-decorated methods in the agent class."""
        self.logger.debug(f"Discovering MCP methods for {self.name}")

        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue

            attr = getattr(self, attr_name)
            if not callable(attr) or not hasattr(attr, "_mcp_type"):
                continue

            mcp_type = getattr(attr, "_mcp_type")
            if mcp_type == "tool":
                self._mcp_methods["tools"].append(attr)
                self.logger.debug(f"Discovered MCP tool: {attr._mcp_name}")
            elif mcp_type == "prompt":
                self._mcp_methods["prompts"].append(attr)
                self.logger.debug(f"Discovered MCP prompt: {attr._mcp_name}")
            elif mcp_type == "resource":
                self._mcp_methods["resources"].append(attr)
                self.logger.debug(f"Discovered MCP resource: {attr._mcp_uri}")

    def set_communicator(self, communicator: BaseCommunicator) -> None:
        """Set the communicator for the agent.

        Args:
            communicator: The communicator to use
        """
        self._communicator = communicator

    async def _register_mcp_methods(self) -> None:
        """Register MCP methods with the communicator."""
        if not self._communicator:
            self.logger.warning("No communicator set, cannot register MCP methods")
            return

        # Register tools
        for tool in self._mcp_methods["tools"]:
            await self._communicator.register_tool(
                name=tool._mcp_name, function=tool, description=tool._mcp_description
            )

        # Register prompts (if supported by communicator)
        if hasattr(self._communicator, "register_prompt"):
            for prompt in self._mcp_methods["prompts"]:
                await self._communicator.register_prompt(
                    name=prompt._mcp_name, function=prompt, description=prompt._mcp_description
                )

        # Register resources (if supported by communicator)
        if hasattr(self._communicator, "register_resource"):
            for resource in self._mcp_methods["resources"]:
                await self._communicator.register_resource(
                    uri=resource._mcp_uri,
                    function=resource,
                    mime_type=resource._mcp_mime_type,
                    description=resource._mcp_description,
                )

    async def start(self) -> None:
        """Start the agent and set up the MCP server if in server mode."""
        self.logger.info(f"Starting MCP agent {self.name}")

        # Initialize communicator if provided
        if self._communicator:
            await self._communicator.start()
            await self._register_mcp_methods()

        # Call setup to initialize agent-specific resources
        await self.setup()

    async def stop(self) -> None:
        """Stop the agent and shut down the MCP server if running."""
        self.logger.info(f"Stopping MCP agent {self.name}")

        # Call shutdown to clean up agent-specific resources
        await self.shutdown()

        # Stop communicator if provided
        if self._communicator:
            await self._communicator.stop()

    async def setup(self) -> None:
        """Set up the agent.

        This method should be overridden by subclasses to provide
        agent-specific initialization.
        """
        pass

    async def run(self) -> None:
        """Run the agent.

        This method keeps the agent running until stopped or cancelled.
        It can be overridden by subclasses to provide custom behavior.
        """
        try:
            # Keep the agent running until cancelled
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info(f"MCP agent {self.name} run cancelled")
            raise

    async def shutdown(self) -> None:
        """Shut down the agent.

        This method should be overridden by subclasses to provide
        agent-specific cleanup.
        """
        pass
