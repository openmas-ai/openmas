"""MCP Server Agent implementation for SimpleMAS.

This module provides a server-side MCP agent implementation that can be used
to expose functionality to MCP clients (like Claude) using FastMCP.
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, get_type_hints

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ChatMessage, TextContent, Tool
from pydantic import BaseModel, Field, create_model

from simple_mas.agent.base import BaseAgent
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Tool decorator attribute name for storing metadata
MCP_TOOL_ATTR = "_mcp_tool_metadata"

# Prompt decorator attribute name for storing metadata
MCP_PROMPT_ATTR = "_mcp_prompt_metadata"

# Resource decorator attribute name for storing metadata
MCP_RESOURCE_ATTR = "_mcp_resource_metadata"


def _create_pydantic_model_from_signature(
    func: Callable, model_name: Optional[str] = None, exclude_first_arg: bool = True
) -> Type[BaseModel]:
    """Create a Pydantic model based on the function signature.

    Args:
        func: The function to create a model for
        model_name: Optional name for the model
        exclude_first_arg: Whether to exclude the first argument (e.g., self)

    Returns:
        A Pydantic model class representing the function parameters
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    # Fields for the model
    fields = {}

    # Process parameters
    for i, (name, param) in enumerate(sig.parameters.items()):
        # Skip the first argument if it's 'self' or 'cls'
        if exclude_first_arg and i == 0 and name in ("self", "cls"):
            continue

        # Get type hint for this parameter
        param_type = type_hints.get(name, Any)

        # Default value
        has_default = param.default is not inspect.Parameter.empty
        default_value = param.default if has_default else ...

        # Create field
        fields[name] = (param_type, Field(default=default_value))

    # Create model name based on function name if not provided
    if model_name is None:
        model_name = f"{func.__name__.title()}Params"

    # Create and return the model
    return create_model(model_name, **fields)


def mcp_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    schema_override: Optional[Dict[str, Any]] = None,
    return_model: Optional[Type[BaseModel]] = None,
) -> Callable[[Callable], Callable]:
    """Decorator to mark a function as an MCP tool.

    Args:
        name: Optional name for the tool, defaults to the function name
        description: Optional description for the tool
        schema_override: Optional custom schema for the tool
        return_model: Optional Pydantic model for the return value

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        # Get function metadata
        func_name = name or func.__name__
        func_doc = description or inspect.getdoc(func) or ""

        # Create parameter model if not provided
        param_model = _create_pydantic_model_from_signature(func)

        # Store MCP tool metadata on the function
        setattr(
            func,
            MCP_TOOL_ATTR,
            {
                "name": func_name,
                "description": func_doc,
                "parameter_model": param_model,
                "return_model": return_model,
                "schema_override": schema_override,
            },
        )

        return func

    return decorator


def mcp_prompt(
    name: Optional[str] = None,
    description: Optional[str] = None,
    template: Optional[str] = None,
) -> Callable[[Callable], Callable]:
    """Decorator to mark a function as an MCP prompt.

    Args:
        name: Optional name for the prompt, defaults to the function name
        description: Optional description for the prompt
        template: Optional template for the prompt

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        # Get function metadata
        func_name = name or func.__name__
        func_doc = description or inspect.getdoc(func) or ""

        # Extract template from docstring if not provided
        prompt_template = template
        if prompt_template is None and func_doc:
            # Use the docstring as the template
            prompt_template = func_doc

        # Store MCP prompt metadata on the function
        setattr(func, MCP_PROMPT_ATTR, {"name": func_name, "description": func_doc, "template": prompt_template})

        return func

    return decorator


def mcp_resource(
    name: Optional[str] = None,
    description: Optional[str] = None,
    mime_type: str = "application/octet-stream",
) -> Callable[[Callable], Callable]:
    """Decorator to mark a function as an MCP resource provider.

    Args:
        name: Optional name for the resource, defaults to the function name
        description: Optional description for the resource
        mime_type: MIME type of the resource

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        # Get function metadata
        func_name = name or func.__name__
        func_doc = description or inspect.getdoc(func) or ""

        # Store MCP resource metadata on the function
        setattr(func, MCP_RESOURCE_ATTR, {"name": func_name, "description": func_doc, "mime_type": mime_type})

        return func

    return decorator


class McpServerAgent(BaseAgent):
    """Server agent that exposes MCP tools, prompts, and resources.

    This agent creates an MCP server that can be connected to by client agents.
    It discovers methods decorated with @mcp_tool, @mcp_prompt, and @mcp_resource
    and makes them available to clients.
    """

    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: int = 8000,
        tools: Optional[List[Callable]] = None,
        prompts: Optional[Dict[str, str]] = None,
        resources: Optional[Dict[str, bytes]] = None,
    ):
        """Initialize the MCP server agent.

        Args:
            name: The name of the agent
            host: The host for the MCP server
            port: The port for the MCP server
            tools: Optional additional tool functions to register
            prompts: Optional additional prompts to register
            resources: Optional additional resources to register
        """
        super().__init__(name)
        self.host = host
        self.port = port
        self.logger = get_logger(f"mcp_server.{name}")

        # MCP server and task
        self.server: Optional[FastMCP] = None
        self.server_task: Optional[asyncio.Task] = None

        # Track registered items
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: Dict[str, Dict[str, Any]] = {}
        self._prompts: Dict[str, str] = prompts or {}
        self._resources: Dict[str, bytes] = resources or {}

        # Register additional tools if provided
        if tools:
            for tool_func in tools:
                self._register_tool(tool_func)

    def _discover_decorated_methods(self) -> None:
        """Discover and register methods decorated with MCP decorators."""
        self.logger.debug(f"Discovering decorated methods in {self.__class__.__name__}")

        # Get all methods defined in this class (including inherited methods)
        methods = inspect.getmembers(self, predicate=inspect.ismethod)

        # Process each method
        for name, method in methods:
            # Skip special methods
            if name.startswith("_"):
                continue

            # Check for MCP tool metadata
            if hasattr(method, MCP_TOOL_ATTR):
                self.logger.debug(f"Found MCP tool: {name}")
                self._register_tool(method)

            # Check for MCP prompt metadata
            if hasattr(method, MCP_PROMPT_ATTR):
                metadata = getattr(method, MCP_PROMPT_ATTR)
                prompt_name = metadata.get("name", name)
                template = metadata.get("template", "")

                self.logger.debug(f"Found MCP prompt: {prompt_name}")
                self._prompts[prompt_name] = template

            # Check for MCP resource metadata
            if hasattr(method, MCP_RESOURCE_ATTR):
                metadata = getattr(method, MCP_RESOURCE_ATTR)
                resource_name = metadata.get("name", name)

                self.logger.debug(f"Found MCP resource: {resource_name}")
                # Resources are registered during runtime when requested

    def _register_tool(self, tool_func: Callable) -> None:
        """Register a tool function.

        Args:
            tool_func: The tool function to register
        """
        # Get tool metadata
        if not hasattr(tool_func, MCP_TOOL_ATTR):
            self.logger.warning(f"Function {tool_func.__name__} is not decorated with @mcp_tool")
            return

        metadata = getattr(tool_func, MCP_TOOL_ATTR)
        tool_name = metadata["name"]

        # Register the tool
        self._tools[tool_name] = tool_func

        # Create tool schema
        if metadata.get("schema_override"):
            # Use provided schema override
            self._tool_schemas[tool_name] = metadata["schema_override"]
        else:
            # Create schema from parameter model
            param_model = metadata["parameter_model"]
            schema = param_model.schema()

            # Convert to MCP tool schema format
            tool_schema = {"name": tool_name, "description": metadata["description"], "parameters": schema}

            self._tool_schemas[tool_name] = tool_schema

    async def _handle_tool_call(self, tool_name: str, parameters: Dict[str, Any], context: Context) -> Any:
        """Handle a tool call from a client.

        Args:
            tool_name: The name of the tool to call
            parameters: The parameters for the tool call
            context: The MCP context

        Returns:
            The result of the tool call
        """
        self.logger.debug(f"Tool call: {tool_name} with params {parameters}")

        # Get the tool function
        tool_func = self._tools.get(tool_name)
        if not tool_func:
            raise ValueError(f"Tool not found: {tool_name}")

        # Get tool metadata
        metadata = getattr(tool_func, MCP_TOOL_ATTR)

        # Create a Pydantic model instance from parameters
        param_model = metadata["parameter_model"]
        validated_params = param_model(**parameters)

        # Convert to dict for passing to the function
        parsed_params = validated_params.dict()

        # Check if the function is a method
        if inspect.ismethod(tool_func):
            # Method - 'self' is already bound
            result = await tool_func(**parsed_params)
        else:
            # Function - pass self as first argument if needed
            sig = inspect.signature(tool_func)
            if list(sig.parameters.keys())[0] in ("self", "cls"):
                result = await tool_func(self, **parsed_params)
            else:
                result = await tool_func(**parsed_params)

        # Validate return value if a return model is specified
        return_model = metadata.get("return_model")
        if return_model and result is not None:
            if isinstance(result, return_model):
                # Already a model instance, convert to dict
                return result.dict()
            else:
                # Create model instance and convert to dict
                return return_model(**result).dict()

        return result

    async def _handle_message(self, content: TextContent, context: Context) -> None:
        """Handle a message from a client.

        Args:
            content: The message content
            context: The MCP context
        """
        self.logger.debug(f"Received message: {content.text}")

        # Simple echo response by default
        response = ChatMessage(role="assistant", content=f"Echo: {content.text}")

        await context.send_message(response)

    async def _handle_resource(self, uri: str, context: Context) -> bytes:
        """Handle a resource request from a client.

        Args:
            uri: The resource URI
            context: The MCP context

        Returns:
            The resource content as bytes
        """
        self.logger.debug(f"Resource request: {uri}")

        # Check if resource is in the static resources
        if uri in self._resources:
            return self._resources[uri]

        # Check if there's a resource provider method for this URI
        methods = inspect.getmembers(self, predicate=inspect.ismethod)

        for name, method in methods:
            if hasattr(method, MCP_RESOURCE_ATTR):
                metadata = getattr(method, MCP_RESOURCE_ATTR)
                resource_name = metadata.get("name", name)

                if resource_name == uri:
                    # Call the resource provider method
                    return await method()

        # Resource not found
        raise ValueError(f"Resource not found: {uri}")

    async def start(self) -> None:
        """Start the agent and MCP server."""
        self.logger.info(f"Starting MCP server agent {self.name}")

        # Discover decorated methods
        self._discover_decorated_methods()

        # Create MCP server
        from mcp.server.fastmcp import create_fastmcp, uvicorn

        # Create tool list from schemas
        tools = [Tool(**schema) for schema in self._tool_schemas.values()]

        # Create the FastMCP server
        self.server = await create_fastmcp(
            tools=tools,
            prompts=self._prompts,
            tool_handler=self._handle_tool_call,
            message_handler=self._handle_message,
            resource_handler=self._handle_resource,
        )

        # Start the server
        config = uvicorn.Config(
            app=self.server.app,
            host=self.host,
            port=self.port,
        )
        server = uvicorn.Server(config)

        # Run in a separate task
        self.server_task = asyncio.create_task(server.serve())
        self.logger.info(f"MCP server started on {self.host}:{self.port}")

        # Call setup for agent-specific initialization
        await self.setup()

    async def setup(self) -> None:
        """Set up the agent.

        This method should be overridden by subclasses to provide
        agent-specific initialization.
        """
        pass

    async def run(self) -> None:
        """Run the agent.

        This method keeps the agent running until stopped or cancelled.
        """
        try:
            if self.server_task:
                # Wait for the server task
                await self.server_task
            else:
                # Keep the agent running
                while True:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info(f"MCP server agent {self.name} run cancelled")
            raise

    async def stop(self) -> None:
        """Stop the agent and the MCP server."""
        self.logger.info(f"Stopping MCP server agent {self.name}")

        # Call shutdown for agent-specific cleanup
        await self.shutdown()

        # Cancel server task if it exists
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
            self.server_task = None

        # Clean up server
        self.server = None

    async def shutdown(self) -> None:
        """Shut down the agent.

        This method should be overridden by subclasses to provide
        agent-specific cleanup.
        """
        pass
