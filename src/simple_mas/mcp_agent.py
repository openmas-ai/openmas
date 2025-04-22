"""MCP Agent implementation for SimpleMAS.

This module provides agent classes for working with the Model Context Protocol (MCP).
It includes decorators for defining tools, prompts, and resources.
"""

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

from pydantic import BaseModel, create_model

from simple_mas.agent import BaseAgent
from simple_mas.communication.mcp.sse_communicator import McpSseCommunicator
from simple_mas.config import AgentConfig
from simple_mas.logging import get_logger

# Type aliases
ToolFunction = Callable[..., Any]
PromptFunction = Callable[..., str]
ResourceFunction = Callable[..., bytes]
T = TypeVar("T")

# Metadata collections
_MCP_TOOLS: Dict[str, Dict[str, Any]] = {}
_MCP_PROMPTS: Dict[str, Dict[str, Any]] = {}
_MCP_RESOURCES: Dict[str, Dict[str, Any]] = {}


@dataclass
class McpMetadata:
    """Metadata for MCP objects (tools, prompts, resources)."""

    name: str
    description: str
    param_model: Optional[type] = None
    function: Optional[Callable] = None


def _create_param_model(func: Callable, name: str) -> Optional[Type[BaseModel]]:
    """Create a Pydantic model from a function's type annotations.

    Args:
        func: The function to extract parameters from
        name: The base name for the model

    Returns:
        A Pydantic model class or None if no parameters exist
    """
    sig = inspect.signature(func)
    fields = {}

    # Skip self parameter for methods
    params = list(sig.parameters.items())
    if params and params[0][0] == "self":
        params = params[1:]

    for param_name, param in params:
        # Get type annotation or default to Any
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else Any

        # Get default value or use ... for required fields
        default = param.default if param.default is not inspect.Parameter.empty else ...

        fields[param_name] = (annotation, default)

    if not fields:
        return None

    # Create and return the model
    model_name = f"{name.capitalize()}Params"
    return create_model(model_name, **fields)  # type: ignore


def mcp_tool(name: Optional[str] = None, description: Optional[str] = None) -> Callable[[ToolFunction], ToolFunction]:
    """Decorator to register a function as an MCP tool.

    Args:
        name: Optional name for the tool (defaults to function name)
        description: Optional description (defaults to function docstring)

    Returns:
        Decorated function
    """

    def decorator(func: ToolFunction) -> ToolFunction:
        nonlocal name, description

        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Tool: {tool_name}"

        # Create parameter model
        param_model = _create_param_model(func, tool_name)

        # Register the tool
        _MCP_TOOLS[tool_name] = {
            "name": tool_name,
            "description": tool_description,
            "param_model": param_model,
            "function": func,
        }

        return func

    return decorator


def mcp_prompt(
    name: Optional[str] = None, description: Optional[str] = None
) -> Callable[[PromptFunction], PromptFunction]:
    """Decorator to register a function as an MCP prompt.

    Args:
        name: Optional name for the prompt (defaults to function name)
        description: Optional description (defaults to function docstring)

    Returns:
        Decorated function
    """

    def decorator(func: PromptFunction) -> PromptFunction:
        nonlocal name, description

        prompt_name = name or func.__name__
        prompt_description = description or func.__doc__ or f"Prompt: {prompt_name}"

        # Create parameter model
        param_model = _create_param_model(func, prompt_name)

        # Register the prompt
        _MCP_PROMPTS[prompt_name] = {
            "name": prompt_name,
            "description": prompt_description,
            "param_model": param_model,
            "function": func,
        }

        return func

    return decorator


def mcp_resource(
    name: Optional[str] = None, description: Optional[str] = None
) -> Callable[[ResourceFunction], ResourceFunction]:
    """Decorator to register a function as an MCP resource.

    Args:
        name: Optional name for the resource (defaults to function name)
        description: Optional description (defaults to function docstring)

    Returns:
        Decorated function
    """

    def decorator(func: ResourceFunction) -> ResourceFunction:
        nonlocal name, description

        resource_name = name or func.__name__
        resource_description = description or func.__doc__ or f"Resource: {resource_name}"

        # Create parameter model
        param_model = _create_param_model(func, resource_name)

        # Register the resource
        _MCP_RESOURCES[resource_name] = {
            "name": resource_name,
            "description": resource_description,
            "param_model": param_model,
            "function": func,
        }

        return func

    return decorator


class McpAgent(BaseAgent):
    """Agent that provides a high-level interface for MCP communication.

    This agent handles both client and server modes for MCP communication,
    providing a simplified API for registering and using tools, prompts,
    and resources.

    Attributes:
        config: The agent configuration
        communicator: The MCP SSE communicator instance
        services: Dictionary of connected services (in client mode)
        server_mode: Whether the agent is running in server mode
        tools: Dictionary of registered tools
        prompts: Dictionary of registered prompts
        resources: Dictionary of registered resources
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Union[AgentConfig, Dict[str, Any]]] = None,
    ):
        """Initialize the MCP agent.

        Args:
            name: The agent name (overrides config)
            config: The agent configuration
        """
        # Convert AgentConfig to dict if needed for BaseAgent
        agent_config: Optional[Dict[str, Any]] = None
        if isinstance(config, AgentConfig):
            agent_config = config.model_dump()
        else:
            agent_config = config

        super().__init__(name=name, config=agent_config)
        self.logger = get_logger(f"McpAgent({self.config.name})")

        # Setup the MCP communicator
        self.service_urls: Dict[str, str] = {}  # Will be populated in connect_to_service
        self.server_mode: bool = False
        self.http_port: int = 8000  # Default

        # Extract config values
        if isinstance(self.config, dict):
            self.server_mode = self.config.get("server_mode", False)
            self.http_port = self.config.get("http_port", 8000)
            server_instructions = self.config.get("server_instructions", None)
        else:
            # Handle when config is a AgentConfig object
            self.server_mode = getattr(self.config, "server_mode", False)
            self.http_port = getattr(self.config, "http_port", 8000)
            server_instructions = getattr(self.config, "server_instructions", None)

        self.communicator = McpSseCommunicator(
            agent_name=self.config.name,
            service_urls=self.service_urls,
            server_mode=self.server_mode,
            http_port=self.http_port,
            server_instructions=server_instructions,
        )

        # Store registered objects
        self.tools: Dict[str, McpMetadata] = {}
        self.prompts: Dict[str, McpMetadata] = {}
        self.resources: Dict[str, McpMetadata] = {}
        self.handlers: Dict[str, Callable] = {}  # Method handlers for the communicator

        # Collect decorated methods and attributes
        self._collect_decorated_methods()

        # Tracking connected services
        self.services: Set[str] = set()

    def _collect_decorated_methods(self) -> None:
        """Collect methods decorated with MCP decorators from this class.

        This allows class methods to be used as tools, prompts, or resources.
        """
        # Process class-level tools
        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue

            attr = getattr(self, attr_name)
            if not callable(attr):
                continue

            # Check if this method is decorated as a tool
            method_name = attr.__name__
            if method_name in _MCP_TOOLS:
                metadata = _MCP_TOOLS[method_name]
                self.tools[metadata["name"]] = McpMetadata(
                    name=metadata["name"],
                    description=metadata["description"],
                    param_model=metadata["param_model"],
                    function=attr,
                )

            # Check if this method is decorated as a prompt
            if method_name in _MCP_PROMPTS:
                metadata = _MCP_PROMPTS[method_name]
                self.prompts[metadata["name"]] = McpMetadata(
                    name=metadata["name"],
                    description=metadata["description"],
                    param_model=metadata["param_model"],
                    function=attr,
                )

            # Check if this method is decorated as a resource
            if method_name in _MCP_RESOURCES:
                metadata = _MCP_RESOURCES[method_name]
                self.resources[metadata["name"]] = McpMetadata(
                    name=metadata["name"],
                    description=metadata["description"],
                    param_model=metadata["param_model"],
                    function=attr,
                )

    async def _handle_tool_request(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a tool request.

        Args:
            tool_name: The name of the tool to call
            parameters: The parameters to pass to the tool

        Returns:
            The result of the tool call

        Raises:
            ValueError: If the tool is not found
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")

        tool = self.tools[tool_name]
        func = tool.function

        if func is None:
            raise ValueError(f"Tool function is None for {tool_name}")

        # Prepare parameters
        if tool.param_model:
            validated_params = tool.param_model(**parameters)
            result = (
                await func(**validated_params.model_dump())
                if asyncio.iscoroutinefunction(func)
                else func(**validated_params.model_dump())
            )
        else:
            result = await func() if asyncio.iscoroutinefunction(func) else func()

        # Convert result to dict if it's not already
        if isinstance(result, dict):
            return result
        else:
            return {"result": result}

    async def _handle_prompt_request(self, prompt_name: str, parameters: Dict[str, Any]) -> str:
        """Handle a prompt request.

        Args:
            prompt_name: The name of the prompt to get
            parameters: The parameters to pass to the prompt

        Returns:
            The prompt text

        Raises:
            ValueError: If the prompt is not found
        """
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt not found: {prompt_name}")

        prompt = self.prompts[prompt_name]
        func = prompt.function

        if func is None:
            raise ValueError(f"Prompt function is None for {prompt_name}")

        # Prepare parameters
        if prompt.param_model:
            validated_params = prompt.param_model(**parameters)
            result = (
                await func(**validated_params.model_dump())
                if asyncio.iscoroutinefunction(func)
                else func(**validated_params.model_dump())
            )
        else:
            result = await func() if asyncio.iscoroutinefunction(func) else func()

        return str(result)

    async def _handle_resource_request(self, resource_name: str, parameters: Dict[str, Any]) -> bytes:
        """Handle a resource request.

        Args:
            resource_name: The name of the resource to get
            parameters: The parameters to pass to the resource

        Returns:
            The resource content as bytes

        Raises:
            ValueError: If the resource is not found
        """
        if resource_name not in self.resources:
            raise ValueError(f"Resource not found: {resource_name}")

        resource = self.resources[resource_name]
        func = resource.function

        if func is None:
            raise ValueError(f"Resource function is None for {resource_name}")

        # Prepare parameters
        if resource.param_model:
            validated_params = resource.param_model(**parameters)
            result = (
                await func(**validated_params.model_dump())
                if asyncio.iscoroutinefunction(func)
                else func(**validated_params.model_dump())
            )
        else:
            result = await func() if asyncio.iscoroutinefunction(func) else func()

        # Convert result to bytes if it's not already
        if isinstance(result, bytes):
            return result
        else:
            return str(result).encode("utf-8")

    async def _register_handlers(self) -> None:
        """Register handlers for tools, prompts, and resources."""
        if not self.server_mode:
            return

        # Register handlers at the communicator level
        for method, handler in self.handlers.items():
            await self.communicator.register_handler(method, handler)

        # Register MCP-specific handlers
        for tool_name, tool in self.tools.items():
            # Create a closure to capture the tool name
            async def tool_handler(params: Dict[str, Any], tn: str = tool_name) -> Dict[str, Any]:
                return await self._handle_tool_request(tn, params or {})

            # Register the tool handler
            method = f"tool/{tool_name}"
            await self.communicator.register_handler(method, tool_handler)

        for prompt_name, prompt in self.prompts.items():
            # Create a closure to capture the prompt name
            async def prompt_handler(params: Dict[str, Any], pn: str = prompt_name) -> str:
                return await self._handle_prompt_request(pn, params or {})

            # Register the prompt handler
            method = f"prompt/{prompt_name}"
            await self.communicator.register_handler(method, prompt_handler)

        for resource_name, resource in self.resources.items():
            # Create a closure to capture the resource name
            async def resource_handler(params: Dict[str, Any], rn: str = resource_name) -> bytes:
                return await self._handle_resource_request(rn, params or {})

            # Register the resource handler
            method = f"resource/{resource_name}"
            await self.communicator.register_handler(method, resource_handler)

    async def setup(self) -> None:
        """Set up the agent.

        This method is called during agent start and registers handlers.
        """
        if self.server_mode:
            await self._register_handlers()

    async def run(self) -> None:
        """Run the agent.

        For MCP agents, this just keeps the agent alive.
        """
        # Just keep the agent running
        while True:
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        """Shut down the agent.

        This method disconnects from all services in client mode.
        """
        if not self.server_mode:
            for service in list(self.services):
                await self.disconnect_from_service(service)

    async def start(self) -> None:
        """Start the agent.

        In server mode, this starts an MCP server.
        In client mode, this initializes the communicator.
        """
        self.logger.info(f"Starting MCP agent {self.config.name}")

        # Call parent start method which will run setup, etc.
        await super().start()

        if self.server_mode:
            self.logger.info(f"MCP server started on port {self.http_port}")
        else:
            self.logger.info("MCP agent started in client mode")

    async def connect_to_service(self, service_name: str, url: str) -> None:
        """Connect to an MCP service.

        Args:
            service_name: The name of the service to connect to
            url: The URL of the service
        """
        if self.server_mode:
            self.logger.warning("Cannot connect to services in server mode")
            return

        self.service_urls[service_name] = url

        # Use the communicator's method to connect (by name)
        await self.communicator.send_request(target_service=service_name, method="connect", params={"url": url})

        self.services.add(service_name)
        self.logger.info(f"Connected to MCP service: {service_name}")

    async def disconnect_from_service(self, service_name: str) -> None:
        """Disconnect from an MCP service.

        Args:
            service_name: The name of the service to disconnect from
        """
        if self.server_mode:
            self.logger.warning("Cannot disconnect from services in server mode")
            return

        if service_name in self.services:
            # Just remove from our tracking - SSE client does not have explicit disconnect
            self.services.remove(service_name)
            self.logger.info(f"Disconnected from MCP service: {service_name}")

    async def list_tools(self, service_name: str) -> List[Dict[str, str]]:
        """List tools available on a service.

        Args:
            service_name: The name of the service

        Returns:
            List of tool metadata dictionaries
        """
        if self.server_mode:
            # In server mode, return locally registered tools
            return [{"name": name, "description": tool.description} for name, tool in self.tools.items()]
        else:
            # In client mode, query the remote service
            response = await self.communicator.send_request(target_service=service_name, method="tool/list")
            if isinstance(response, dict) and "tools" in response:
                tools = response["tools"]
                if isinstance(tools, list):
                    # Ensure each element is a dict with string keys/values
                    return [
                        {"name": str(tool.get("name", "")), "description": str(tool.get("description", ""))}
                        for tool in tools
                        if isinstance(tool, dict)
                    ]
            return []

    async def list_prompts(self, service_name: str) -> List[Dict[str, str]]:
        """List prompts available on a service.

        Args:
            service_name: The name of the service

        Returns:
            List of prompt metadata dictionaries
        """
        if self.server_mode:
            # In server mode, return locally registered prompts
            return [{"name": name, "description": prompt.description} for name, prompt in self.prompts.items()]
        else:
            # In client mode, get from remote service
            result = await self.communicator.send_request(
                target_service=service_name,
                method="prompt/list",
            )
            if isinstance(result, dict) and "prompts" in result:
                prompts = result["prompts"]
                if isinstance(prompts, list):
                    # Ensure each element is a dict with string keys/values
                    return [
                        {"name": str(prompt.get("name", "")), "description": str(prompt.get("description", ""))}
                        for prompt in prompts
                        if isinstance(prompt, dict)
                    ]
            return []

    async def list_resources(self, service_name: str) -> List[Dict[str, str]]:
        """List resources available on a service.

        Args:
            service_name: The name of the service

        Returns:
            List of resource metadata dictionaries
        """
        if self.server_mode:
            # In server mode, return locally registered resources
            return [{"name": name, "description": resource.description} for name, resource in self.resources.items()]
        else:
            # In client mode, get from remote service
            result = await self.communicator.send_request(
                target_service=service_name,
                method="resource/list",
            )
            if isinstance(result, dict) and "resources" in result:
                resources = result["resources"]
                if isinstance(resources, list):
                    # Ensure each element is a dict with string keys/values
                    return [
                        {"name": str(resource.get("name", "")), "description": str(resource.get("description", ""))}
                        for resource in resources
                        if isinstance(resource, dict)
                    ]
            return []

    async def call_tool(self, service_name: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a service.

        Args:
            service_name: The name of the service
            tool_name: The name of the tool to call
            parameters: The parameters to pass to the tool

        Returns:
            The result of the tool call
        """
        if self.server_mode:
            # In server mode, call locally registered tool
            return await self._handle_tool_request(tool_name, parameters)
        else:
            # In client mode, call remote tool
            result = await self.communicator.send_request(
                target_service=service_name, method="tool/call", params={"name": tool_name, "arguments": parameters}
            )
            if isinstance(result, dict):
                return result
            else:
                return {"result": result}

    async def get_prompt(self, service_name: str, prompt_name: str, parameters: Dict[str, Any]) -> str:
        """Get a prompt from a service.

        Args:
            service_name: The name of the service
            prompt_name: The name of the prompt to get
            parameters: The parameters to pass to the prompt

        Returns:
            The prompt text
        """
        if self.server_mode:
            # In server mode, get locally registered prompt
            return await self._handle_prompt_request(prompt_name, parameters)
        else:
            # In client mode, get remote prompt
            result = await self.communicator.send_request(
                target_service=service_name, method="prompt/get", params={"name": prompt_name, "arguments": parameters}
            )
            return str(result)

    async def get_resource(
        self, service_name: str, resource_name: str, parameters: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Get a resource from a service.

        Args:
            service_name: The name of the service
            resource_name: The name of the resource to get
            parameters: The parameters to pass to the resource

        Returns:
            The resource content as bytes
        """
        params = parameters or {}
        if self.server_mode:
            # In server mode, get locally registered resource
            return await self._handle_resource_request(resource_name, params)
        else:
            # In client mode, get remote resource
            result = await self.communicator.send_request(
                target_service=service_name,
                method="resource/read",
                params={"uri": resource_name},
            )
            content = result.get("content", b"")
            return content if isinstance(content, bytes) else str(content).encode("utf-8")


class McpServerAgent(McpAgent):
    """MCP agent that runs in server mode."""

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Union[AgentConfig, Dict[str, Any]]] = None,
    ):
        """Initialize the MCP server agent.

        Args:
            name: The agent name (overrides config)
            config: The agent configuration
        """
        super().__init__(name=name, config=config)
        self.server_mode = True

    async def start_server(self) -> None:
        """Start the MCP server.

        This is a convenience method that calls start().
        """
        await self.start()
