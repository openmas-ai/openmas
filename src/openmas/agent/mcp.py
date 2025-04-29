"""MCP Agent implementation for OpenMAS.

This module provides an MCP-enabled agent implementation that can be used
to expose functionality to MCP clients (like Claude) using FastMCP.
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, TypeVar, cast, get_type_hints, runtime_checkable

from pydantic import BaseModel, Field, create_model

from openmas.agent.base import BaseAgent
from openmas.communication.base import BaseCommunicator
from openmas.logging import get_logger

# Constants for decorator attribute names
MCP_TOOL_ATTR = "__mcp_tool__"
MCP_PROMPT_ATTR = "__mcp_prompt__"
MCP_RESOURCE_ATTR = "__mcp_resource__"

# Configure logging
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


@runtime_checkable
class McpCommunicatorProtocol(Protocol):
    """Protocol for MCP communicators that support sampling prompts."""

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
        """Protocol method for sampling prompts."""
        ...


class McpAgent(BaseAgent):
    """Base class for MCP-enabled agents.

    This agent class provides functionality for registering methods as MCP tools,
    prompts, and resources with an MCP communicator.

    It works together with @mcp_tool, @mcp_prompt, and @mcp_resource decorators
    to expose functionality via MCP.

    It can be used as a standalone MCP-enabled agent or as a base class for more
    specialized agents like McpServerAgent and McpClientAgent.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """Initialize the MCP agent.

        Args:
            name: Optional name for the agent
            config: Optional configuration for the agent
            **kwargs: Additional keyword arguments for the parent class
        """
        super().__init__(name, config, **kwargs)

        # Initialize attributes for discovered MCP methods
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._prompts: Dict[str, Dict[str, Any]] = {}
        self._resources: Dict[str, Dict[str, Any]] = {}

        # Flag for whether this is a server agent
        self._server_mode = False

        # If config has COMMUNICATOR_TYPE, use that to set up communicator
        if self.config:
            communicator_type = None
            if hasattr(self.config, "model_dump"):
                # Handle AgentConfig (Pydantic model)
                config_dict = self.config.model_dump()
                if "COMMUNICATOR_TYPE" in config_dict:
                    communicator_type = config_dict["COMMUNICATOR_TYPE"]
            elif isinstance(self.config, dict) and "COMMUNICATOR_TYPE" in self.config:
                # Handle dict configuration
                communicator_type = self.config["COMMUNICATOR_TYPE"]

            if communicator_type:
                from openmas.communication import create_communicator

                # Add debug logging
                module_name = create_communicator.__module__
                func_name = create_communicator.__name__
                self.logger.debug(
                    f"Creating communicator of type: {communicator_type}, "
                    f"using create_communicator function: {module_name}.{func_name}"
                )

                # Extract parameters based on config type
                service_urls = {}
                server_mode = False
                http_port = 8000
                server_instructions = None

                if hasattr(self.config, "model_dump"):
                    # Handle AgentConfig (Pydantic model)
                    config_dict = self.config.model_dump()
                    service_urls = config_dict.get("SERVICE_URLS", {})
                    server_mode = config_dict.get("SERVER_MODE", False)
                    http_port = config_dict.get("HTTP_PORT", 8000)
                    server_instructions = config_dict.get("SERVER_INSTRUCTIONS", None)
                elif isinstance(self.config, dict):
                    # Handle dict configuration
                    service_urls = self.config.get("SERVICE_URLS", {})
                    server_mode = self.config.get("SERVER_MODE", False)
                    http_port = self.config.get("HTTP_PORT", 8000)
                    server_instructions = self.config.get("SERVER_INSTRUCTIONS", None)

                communicator = create_communicator(
                    communicator_type=communicator_type,
                    agent_name=self.name,
                    service_urls=service_urls,
                    server_mode=server_mode,
                    http_port=http_port,
                    server_instructions=server_instructions,
                )
                self.set_communicator(communicator)

        # Call method discovery on initialization
        self._discover_mcp_methods()

        self.logger.debug(
            f"Initialized MCP agent with {len(self._tools)} tools, "
            f"{len(self._prompts)} prompts, and {len(self._resources)} resources"
        )

    def _discover_mcp_methods(self) -> None:
        """Discover methods decorated with MCP decorators.

        This method inspects the agent class for methods decorated with @mcp_tool,
        @mcp_prompt, and @mcp_resource and prepares them for registration with
        an MCP server.
        """
        # Reset collections
        self._tools = {}
        self._prompts = {}
        self._resources = {}

        # Get all public methods from the instance
        for name in dir(self):
            if name.startswith("_"):
                continue  # Skip private methods

            attr = getattr(self, name)
            if not callable(attr):
                continue  # Skip non-callables

            # Check for tool decorator
            if hasattr(attr, MCP_TOOL_ATTR):
                metadata = getattr(attr, MCP_TOOL_ATTR)
                self.logger.debug(f"Discovered MCP tool: {metadata['name']}")
                self._tools[metadata["name"]] = {"metadata": metadata, "function": attr}

            # Check for prompt decorator
            if hasattr(attr, MCP_PROMPT_ATTR):
                metadata = getattr(attr, MCP_PROMPT_ATTR)
                self.logger.debug(f"Discovered MCP prompt: {metadata['name']}")
                self._prompts[metadata["name"]] = {"metadata": metadata, "function": attr}

            # Check for resource decorator
            if hasattr(attr, MCP_RESOURCE_ATTR):
                metadata = getattr(attr, MCP_RESOURCE_ATTR)
                self.logger.debug(f"Discovered MCP resource at URI: {metadata['uri']}")
                self._resources[metadata["uri"]] = {"metadata": metadata, "function": attr}

    def set_communicator(self, communicator: BaseCommunicator) -> None:
        """Set the communicator for this agent.

        This method configures the communicator for the agent and prepares for
        MCP registration if the communicator supports it.

        Args:
            communicator: The communicator to use
        """
        # Check if this is an MCP communicator with server mode
        self._server_mode = hasattr(communicator, "server_mode") and getattr(communicator, "server_mode")

        # Set a reference to this agent in the communicator for server registration
        if self._server_mode:
            setattr(communicator, "agent", self)

            # Ensure the communicator has methods needed for registration
            self._verify_server_mode_compatibility(communicator)

        # Call parent method to set the communicator
        super().set_communicator(communicator)

        self.logger.debug(f"Set communicator: {communicator.__class__.__name__}, " f"server_mode: {self._server_mode}")

    def _verify_server_mode_compatibility(self, communicator: BaseCommunicator) -> None:
        """Verify that the communicator supports the necessary methods for server mode.

        Args:
            communicator: The communicator to verify
        """
        # Check for necessary registration methods
        required_methods = ["register_tool", "register_prompt", "register_resource"]

        missing_methods = []
        for method in required_methods:
            if not hasattr(communicator, method):
                missing_methods.append(method)

        if missing_methods:
            class_name = communicator.__class__.__name__
            methods_str = ", ".join(missing_methods)
            self.logger.warning(
                f"Communicator {class_name} is missing required methods "
                f"for server mode: {methods_str}. "
                f"MCP registration may not work properly."
            )

    async def setup(self) -> None:
        """Set up the agent.

        This method is called when the agent is started.
        If the agent has an MCP communicator in server mode, it registers
        its decorated methods as MCP tools, prompts, and resources.
        """
        # Refresh MCP method discovery
        self._discover_mcp_methods()

        # If we have an MCP communicator, register decorated methods
        if self.communicator:
            if hasattr(self.communicator, "prepare_registration"):
                # If the communicator supports preparation, send all registrations at once
                self.logger.debug("Preparing MCP registrations with communicator")
                await self.communicator.prepare_registration(
                    tools=self._tools, prompts=self._prompts, resources=self._resources
                )
            else:
                # Register tools
                for tool_name, tool_data in self._tools.items():
                    metadata = tool_data["metadata"]
                    function = tool_data["function"]
                    await self._register_tool_with_communicator(
                        name=metadata.get("name", tool_name),
                        description=metadata.get("description", ""),
                        function=function,
                    )

                # Register prompts
                for prompt_name, prompt_data in self._prompts.items():
                    metadata = prompt_data["metadata"]
                    function = prompt_data["function"]
                    await self._register_prompt_with_communicator(
                        name=metadata.get("name", prompt_name),
                        description=metadata.get("description", ""),
                        function=function,
                    )

                # Register resources
                for resource_uri, resource_data in self._resources.items():
                    metadata = resource_data["metadata"]
                    function = resource_data["function"]
                    await self._register_resource_with_communicator(
                        uri=metadata.get("uri", resource_uri),
                        name=metadata.get("name", ""),
                        description=metadata.get("description", ""),
                        function=function,
                        mime_type=metadata.get("mime_type", "text/plain"),
                    )

    async def _register_tool_with_communicator(self, name: str, description: str, function: Callable) -> None:
        """Register a tool with the communicator.

        Args:
            name: Tool name
            description: Tool description
            function: Tool function
        """
        if not self.communicator:
            return

        try:
            self.logger.debug(f"Registering MCP tool: {name}")

            if hasattr(self.communicator, "register_tool"):
                await self.communicator.register_tool(name, description, function)
            else:
                self.logger.warning(f"Communicator does not support registering tools, can't register: {name}")
        except Exception as e:
            self.logger.error(f"Failed to register MCP tool {name}: {e}")
            # Don't raise - we want to continue with other registrations

    async def _register_prompt_with_communicator(self, name: str, description: str, function: Callable) -> None:
        """Register a prompt with the communicator.

        Args:
            name: Prompt name
            description: Prompt description
            function: Prompt function
        """
        if not self.communicator:
            return

        try:
            self.logger.debug(f"Registering MCP prompt: {name}")

            if hasattr(self.communicator, "register_prompt"):
                await self.communicator.register_prompt(name, description, function)
            else:
                self.logger.warning(f"Communicator does not support registering prompts, can't register: {name}")
        except Exception as e:
            self.logger.error(f"Failed to register MCP prompt {name}: {e}")
            # Don't raise - we want to continue with other registrations

    async def _register_resource_with_communicator(
        self, uri: str, name: str, description: str, function: Callable, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource with the communicator.

        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            function: Resource function
            mime_type: Resource MIME type
        """
        if not self.communicator:
            return

        try:
            self.logger.debug(f"Registering MCP resource at URI: {uri}")

            if hasattr(self.communicator, "register_resource"):
                await self.communicator.register_resource(name, description, function, mime_type)
            else:
                self.logger.warning(f"Communicator does not support registering resources, can't register: {uri}")
        except Exception as e:
            self.logger.error(f"Failed to register MCP resource {uri}: {e}")
            # Don't raise - we want to continue with other registrations

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
        """Sample a prompt from a service.

        This method sends a request to sample a prompt from the target service.
        It's used for conversational interactions with LLMs via MCP.

        Args:
            target_service: The service to sample from
            messages: List of message objects in the format {"role": "...", "content": "..."}
            system_prompt: Optional system prompt
            temperature: Optional temperature parameter
            max_tokens: Optional maximum tokens parameter
            include_context: Optional include_context parameter
            model_preferences: Optional model preferences
            stop_sequences: Optional stop sequences
            timeout: Optional timeout in seconds

        Returns:
            The sampling result with at least a "content" field

        Raises:
            AttributeError: If the communicator doesn't support sample_prompt
            CommunicationError: If there's a communication problem
        """
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        # Check if the communicator implements the protocol
        if not isinstance(self.communicator, McpCommunicatorProtocol):
            raise AttributeError("Communicator does not support sample_prompt method")

        try:
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
            # Ensure we return a dictionary with at least a content field
            if not isinstance(result, dict):
                return {"content": str(result)}
            return result
        except Exception as e:
            self.logger.error(f"Error sampling prompt from {target_service}: {e}")
            raise

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a remote MCP service.

        This method delegates to the communicator's call_tool method,
        allowing agents to call tools exposed by other MCP services.

        Args:
            target_service: The service containing the tool to call.
            tool_name: The name of the tool to call.
            arguments: Optional arguments to pass to the tool.
            timeout: Optional timeout in seconds.

        Returns:
            The result returned by the tool.

        Raises:
            AttributeError: If the communicator doesn't support call_tool.
            CommunicationError: If there's a problem with the communication.
        """
        if not hasattr(self.communicator, "call_tool"):
            raise AttributeError("Communicator does not support call_tool method")

        return await self.communicator.call_tool(
            target_service=target_service,
            tool_name=tool_name,
            arguments=arguments,
            timeout=timeout,
        )

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Get a rendered prompt from a remote MCP service.

        This method delegates to the communicator's get_prompt method,
        allowing agents to request prompts from other MCP services.

        Args:
            target_service: The service containing the prompt to get.
            prompt_name: The name of the prompt to get.
            arguments: Optional arguments to pass to the prompt renderer.
            timeout: Optional timeout in seconds.

        Returns:
            The rendered prompt text.

        Raises:
            AttributeError: If the communicator doesn't support get_prompt.
            CommunicationError: If there's a problem with the communication.
        """
        if not hasattr(self.communicator, "get_prompt"):
            raise AttributeError("Communicator does not support get_prompt method")

        return await self.communicator.get_prompt(
            target_service=target_service,
            prompt_name=prompt_name,
            arguments=arguments,
            timeout=timeout,
        )

    async def read_resource(
        self,
        target_service: str,
        resource_uri: str,
        timeout: Optional[float] = None,
    ) -> bytes:
        """Read a resource from a remote MCP service.

        This method delegates to the communicator's read_resource method,
        allowing agents to request resources from other MCP services.

        Args:
            target_service: The service containing the resource to read.
            resource_uri: The URI of the resource to read.
            timeout: Optional timeout in seconds.

        Returns:
            The resource content as bytes.

        Raises:
            AttributeError: If the communicator doesn't support read_resource.
            CommunicationError: If there's a problem with the communication.
        """
        if not hasattr(self.communicator, "read_resource"):
            raise AttributeError("Communicator does not support read_resource method")

        result = await self.communicator.read_resource(
            target_service=target_service,
            resource_uri=resource_uri,
            timeout=timeout,
        )
        return cast(bytes, result)

    async def list_tools(
        self,
        target_service: str,
    ) -> List[Dict[str, Any]]:
        """List available tools on a remote MCP service.

        This method delegates to the communicator's list_tools method,
        allowing agents to discover tools exposed by other MCP services.

        Args:
            target_service: The service to list tools from.

        Returns:
            A list of dictionaries containing tool information.

        Raises:
            AttributeError: If the communicator doesn't support list_tools.
            CommunicationError: If there's a problem with the communication.
        """
        if not hasattr(self.communicator, "list_tools"):
            raise AttributeError("Communicator does not support list_tools method")

        result = await self.communicator.list_tools(target_service=target_service)
        return cast(List[Dict[str, Any]], result)

    async def add_tool(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> None:
        """Add a tool function to the agent.

        This method allows dynamically adding tool functions to the agent after initialization.
        The function will be registered with the MCP communicator if available.

        Args:
            func: The function to add as a tool
            name: Optional name for the tool (defaults to function name)
            description: Optional description for the tool (defaults to function docstring)

        Raises:
            RuntimeError: If the function cannot be registered
        """
        tool_name = name or func.__name__
        tool_desc = description or inspect.getdoc(func) or f"Tool: {tool_name}"

        # Create parameter model from function signature
        param_model = _create_pydantic_model_from_signature(func, f"{tool_name}Input")

        # Add to tools dictionary
        self._tools[tool_name] = {
            "metadata": {
                "name": tool_name,
                "description": tool_desc,
                "input_model": param_model,
                "output_model": None,
            },
            "function": func,
        }

        self.logger.debug(f"Added tool: {tool_name}")

        # If we have a communicator, register the tool with it
        if self.communicator:
            try:
                await self._register_tool_with_communicator(
                    name=tool_name,
                    description=tool_desc,
                    function=func,
                )
            except Exception as e:
                self.logger.error(f"Failed to register tool {tool_name} with communicator: {e}")
                raise RuntimeError(f"Failed to register tool {tool_name}: {e}") from e
