"""MCP Agent implementation for SimpleMAS.

This module provides an MCP-enabled agent implementation that can be used
to expose functionality to MCP clients (like Claude) using FastMCP.
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, cast, get_type_hints

from pydantic import BaseModel, Field, create_model

from simple_mas.agent.base import BaseAgent
from simple_mas.communication import BaseCommunicator
from simple_mas.logging import get_logger

logger = get_logger(__name__)

# Check if MCP is installed
try:
    from mcp.server.prompts import Prompt
    from mcp.server.resources import Resource

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

    # Define dummy classes for type checking
    class DummyPrompt:
        def __init__(self, fn: Any = None, name: str = "", description: str = ""):
            pass

    class DummyResource:
        def __init__(self, uri: str = "", fn: Any = None, name: str = "", description: str = "", mime_type: str = ""):
            pass

    # Alias the dummy classes to the expected names for type checking
    Prompt = DummyPrompt
    Resource = DummyResource


T = TypeVar("T", bound=BaseModel)
F = TypeVar("F", bound=Callable[..., Any])

# Decorator attribute names for storing metadata
MCP_TOOL_ATTR = "_mcp_tool_metadata"
MCP_PROMPT_ATTR = "_mcp_prompt_metadata"
MCP_RESOURCE_ATTR = "_mcp_resource_metadata"


def _create_pydantic_model_from_signature(func: Callable, model_name: Optional[str] = None) -> Type[BaseModel]:
    """Create a Pydantic model from a function signature.

    Args:
        func: The function to create a model from
        model_name: Optional name for the model

    Returns:
        A Pydantic model class
    """
    sig = inspect.signature(func)
    type_hints_dict = get_type_hints(func)

    # Skip 'self' parameter if it's a method
    params = list(sig.parameters.items())
    if params and params[0][0] == "self":
        params = params[1:]

    fields: Dict[str, Any] = {}
    for name, param in params:
        # Get type hint if available, otherwise use Any
        param_type = type_hints_dict.get(name, Any)

        # Check if parameter has a default value
        if param.default is not param.empty:
            fields[name] = (param_type, Field(default=param.default))
        else:
            fields[name] = (param_type, Field(...))

    # Generate model name if not provided
    if not model_name:
        model_name = f"{func.__name__}Model"

    # Create and return the model with proper type casting
    model_cls = create_model(model_name, **fields)  # type: ignore
    return cast(Type[BaseModel], model_cls)


def mcp_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    input_model: Optional[Type[BaseModel]] = None,
    output_model: Optional[Type[BaseModel]] = None,
) -> Callable[[F], F]:
    """Decorator to mark a method as an MCP tool.

    This decorator can be applied to methods in a BaseAgent subclass to expose them
    as MCP tools. The decorated methods will be automatically discovered and
    registered with the MCP server when using an MCP communicator.

    Args:
        name: Optional name for the tool (defaults to method name)
        description: Optional description (defaults to method docstring)
        input_model: Optional Pydantic model for input validation
        output_model: Optional Pydantic model for output validation

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        # Get function metadata
        func_name = name or func.__name__
        func_desc = description or inspect.getdoc(func) or f"Tool: {func_name}"

        # Create parameter model if not provided
        param_model = input_model or _create_pydantic_model_from_signature(func, f"{func_name}Input")

        # Store MCP tool metadata on the function
        setattr(
            func,
            MCP_TOOL_ATTR,
            {
                "name": func_name,
                "description": func_desc,
                "input_model": param_model,
                "output_model": output_model,
            },
        )

        return func

    return decorator


def mcp_prompt(
    name: Optional[str] = None,
    description: Optional[str] = None,
    template: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator to mark a method as an MCP prompt.

    This decorator can be applied to methods in a BaseAgent subclass to expose them
    as MCP prompts. The decorated methods will be automatically discovered and
    registered with the MCP server when using an MCP communicator.

    Args:
        name: Optional name for the prompt (defaults to method name)
        description: Optional description (defaults to method docstring)
        template: Optional template for the prompt

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        # Get function metadata
        func_name = name or func.__name__
        func_desc = description or inspect.getdoc(func) or f"Prompt: {func_name}"

        # Extract template from docstring if not provided
        prompt_template = template
        if prompt_template is None and func_desc:
            # Use the docstring as the template
            prompt_template = func_desc

        # Store MCP prompt metadata on the function
        setattr(
            func,
            MCP_PROMPT_ATTR,
            {
                "name": func_name,
                "description": func_desc,
                "template": prompt_template,
            },
        )

        return func

    return decorator


def mcp_resource(
    uri: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    mime_type: str = "application/octet-stream",
) -> Callable[[F], F]:
    """Decorator to mark a method as an MCP resource.

    This decorator can be applied to methods in a BaseAgent subclass to expose them
    as MCP resources. The decorated methods will be automatically discovered and
    registered with the MCP server when using an MCP communicator.

    Args:
        uri: URI path for the resource
        name: Optional name for the resource (defaults to method name)
        description: Optional description (defaults to method docstring)
        mime_type: MIME type for the resource

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        # Get function metadata
        func_name = name or func.__name__
        func_desc = description or inspect.getdoc(func) or f"Resource: {func_name}"

        # Store MCP resource metadata on the function
        setattr(
            func,
            MCP_RESOURCE_ATTR,
            {
                "uri": uri,
                "name": func_name,
                "description": func_desc,
                "mime_type": mime_type,
            },
        )

        return func

    return decorator


class McpAgent(BaseAgent):
    """Base class for MCP-enabled agents.

    This agent class provides functionality for registering methods as MCP tools,
    prompts, and resources, and exposing them through an MCP-compatible API.

    The agent automatically discovers methods decorated with @mcp_tool, @mcp_prompt,
    and @mcp_resource and registers them with the appropriate MCP server when
    an MCP communicator is used in server mode.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """Initialize the MCP agent.

        Args:
            name: The name of the agent (overrides config)
            config: The agent configuration
            **kwargs: Additional arguments to pass to the parent class
        """
        if not HAS_MCP:
            logger.warning("MCP package is not installed. MCP functionality will be limited.")

        super().__init__(name=name, config=config, **kwargs)

        # Initialize collections for MCP methods
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._prompts: Dict[str, Dict[str, Any]] = {}
        self._resources: Dict[str, Dict[str, Any]] = {}

        # Flag indicating if this agent is running in server mode
        self._server_mode = False

        # Discover decorated methods
        self._discover_mcp_methods()

        self.logger.debug(
            f"Initialized MCP agent with {len(self._tools)} tools, "
            f"{len(self._prompts)} prompts, and {len(self._resources)} resources"
        )

    def _discover_mcp_methods(self) -> None:
        """Discover all methods decorated with MCP decorators in this class."""
        self.logger.debug(f"Discovering MCP methods in {self.__class__.__name__}")

        # Get all methods defined in this class (including inherited methods)
        methods = inspect.getmembers(self, predicate=inspect.ismethod)

        # Process each method
        for name, method in methods:
            # Skip special methods
            if name.startswith("_"):
                continue

            # Check for MCP tool metadata
            if hasattr(method, MCP_TOOL_ATTR):
                metadata = getattr(method, MCP_TOOL_ATTR)
                tool_name = metadata.get("name", name)
                self._tools[tool_name] = {
                    "metadata": metadata,
                    "function": method,
                }
                self.logger.debug(f"Found MCP tool: {tool_name}")

            # Check for MCP prompt metadata
            if hasattr(method, MCP_PROMPT_ATTR):
                metadata = getattr(method, MCP_PROMPT_ATTR)
                prompt_name = metadata.get("name", name)
                self._prompts[prompt_name] = {
                    "metadata": metadata,
                    "function": method,
                }
                self.logger.debug(f"Found MCP prompt: {prompt_name}")

            # Check for MCP resource metadata
            if hasattr(method, MCP_RESOURCE_ATTR):
                metadata = getattr(method, MCP_RESOURCE_ATTR)
                resource_uri = metadata.get("uri")
                self._resources[resource_uri] = {
                    "metadata": metadata,
                    "function": method,
                }
                self.logger.debug(f"Found MCP resource: {resource_uri}")

    def set_communicator(self, communicator: BaseCommunicator) -> None:
        """Set the communicator for this agent.

        Args:
            communicator: The communicator to use
        """
        # Check if this is an MCP communicator with server mode
        self._server_mode = hasattr(communicator, "server_mode") and getattr(communicator, "server_mode")

        # Call parent method to set the communicator
        super().set_communicator(communicator)

        self.logger.debug(f"Set communicator: {communicator.__class__.__name__}, " f"server_mode: {self._server_mode}")

    async def _register_with_mcp_server(self) -> None:
        """Register all MCP methods with the MCP server in the communicator."""
        if not HAS_MCP:
            self.logger.warning("MCP package is not installed. Cannot register MCP methods.")
            return

        if not hasattr(self.communicator, "mcp_server"):
            self.logger.warning("Communicator does not have an MCP server, cannot register MCP methods")
            return

        mcp_server: Any = getattr(self.communicator, "mcp_server")

        # Register tools
        for tool_name, tool_data in self._tools.items():
            metadata = tool_data["metadata"]
            function = tool_data["function"]

            # Register with the MCP server
            if hasattr(mcp_server, "add_tool"):
                mcp_server.add_tool(
                    function,
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                )
                self.logger.debug(f"Registered MCP tool: {tool_name}")

        # Register prompts
        for prompt_name, prompt_data in self._prompts.items():
            metadata = prompt_data["metadata"]
            function = prompt_data["function"]

            # Create Prompt object
            prompt = Prompt(
                fn=function,
                name=metadata.get("name"),
                description=metadata.get("description"),
            )

            # Register with the MCP server
            if hasattr(mcp_server, "add_prompt"):
                mcp_server.add_prompt(prompt)
                self.logger.debug(f"Registered MCP prompt: {prompt_name}")

        # Register resources
        for resource_uri, resource_data in self._resources.items():
            metadata = resource_data["metadata"]
            function = resource_data["function"]

            # Create Resource object
            resource = Resource(
                uri=metadata.get("uri"),
                fn=function,
                name=metadata.get("name"),
                description=metadata.get("description"),
                mime_type=metadata.get("mime_type"),
            )

            # Register with the MCP server
            if hasattr(mcp_server, "add_resource"):
                mcp_server.add_resource(resource)
                self.logger.debug(f"Registered MCP resource: {resource_uri}")

    async def setup(self) -> None:
        """Set up the agent.

        In server mode, this registers all MCP methods with the MCP server.
        """
        # If in server mode, register MCP methods with the server
        if self._server_mode:
            await self._register_with_mcp_server()

    async def run(self) -> None:
        """Run the agent.

        This method keeps the agent running until stopped or cancelled.
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

        This method can be overridden by subclasses to provide
        agent-specific cleanup.
        """
        pass

    async def sample_prompt(
        self,
        target_service: str,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_context: Optional[str] = None,
        model_preferences: Optional[Dict[str, Any]] = None,
        stop_sequences: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Request an LLM sampling from the MCP client for a given prompt.

        This method delegates to the communicator's sample_prompt method,
        allowing agents to request generation from LLMs through the MCP protocol.

        Args:
            target_service: The service to request sampling from.
            messages: List of messages to include in the sampling request,
                     each with 'role' and 'content' fields.
            system_prompt: Optional system prompt to use.
            temperature: Optional temperature for sampling (0.0 to 1.0).
            max_tokens: Optional maximum number of tokens to generate.
            include_context: Optional context inclusion mode ("none", "thisServer", "allServers").
            model_preferences: Optional dictionary of model preferences (hints, priorities).
            stop_sequences: Optional list of sequences that should stop generation.
            timeout: Optional timeout in seconds.

        Returns:
            The sampling result, including generated content.

        Raises:
            AttributeError: If the communicator doesn't support sample_prompt.
            CommunicationError: If there's a problem with the communication.
        """
        if not hasattr(self.communicator, "sample_prompt"):
            raise AttributeError("Communicator does not support sample_prompt method")

        result = await self.communicator.sample_prompt(
            target_service=target_service,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            include_context=include_context,
            model_preferences=model_preferences,
            stop_sequences=stop_sequences,
            timeout=timeout,
        )
        return cast(Dict[str, Any], result)
