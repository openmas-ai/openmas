"""MCP adapter for SimpleMAS.

This module provides adapters to use the Anthropic MCP SDK with SimpleMAS.
It includes both client and server adapters.
"""

from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union, cast

from mcp.client.session import ClientSession
from mcp.client.sse import SseClient
from mcp.client.stdio import StdioClient
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from simple_mas.communication.base import BaseCommunicator
from simple_mas.exceptions import CommunicationError, ServiceNotFoundError
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)
F = TypeVar("F", bound=Callable[..., Any])


class McpClientAdapter(BaseCommunicator):
    """Adapter to use MCP client with SimpleMAS.

    This adapter allows SimpleMAS agents to connect to MCP services.
    It provides a bridge between SimpleMAS and the MCP client SDK.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        use_sse: bool = False,
    ):
        """Initialize the MCP client adapter.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs or commands
            use_sse: Whether to use SSE (True) or stdio (False) for communication
        """
        super().__init__(agent_name, service_urls)
        self.use_sse = use_sse
        self.clients: Dict[str, Union[SseClient, StdioClient]] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.connected_services: Set[str] = set()

    async def _connect_to_service(self, service_name: str) -> None:
        """Connect to a MCP service.

        Args:
            service_name: The name of the service to connect to

        Raises:
            ServiceNotFoundError: If the service is not found
            CommunicationError: If there's a problem connecting to the service
        """
        if service_name in self.connected_services:
            return

        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

        url_or_command = self.service_urls[service_name]
        logger.info(f"Connecting to MCP service: {service_name}")

        try:
            # Create the appropriate client type
            if self.use_sse:
                # Create SSE client
                client = SseClient(url_or_command)
                self.clients[service_name] = client
            else:
                # Create stdio client with the command
                client = StdioClient(url_or_command)
                self.clients[service_name] = client

            # Create a session for the client
            session = await client.create_session(name=self.agent_name)
            self.sessions[service_name] = session

            self.connected_services.add(service_name)
            logger.info(f"Connected to MCP service: {service_name}")

        except Exception as e:
            logger.exception(f"Failed to connect to MCP service: {service_name}", error=str(e))
            raise CommunicationError(f"Failed to connect to service '{service_name}': {e}", target=service_name)

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a MCP service.

        This method is not used directly with MCP SDK, but is provided
        for compatibility with the SimpleMAS BaseCommunicator interface.

        Args:
            target_service: The name of the service to send the request to
            method: The method to call on the service
            params: The parameters to pass to the method
            response_model: Optional Pydantic model to validate the response
            timeout: Optional timeout in seconds

        Returns:
            The response from the service

        Raises:
            ServiceNotFoundError: If the target service is not found
            MethodNotFoundError: If the method is not found on the service
            CommunicationError: If there's a problem with the communication
        """
        # The MCP SDK doesn't use the JSON-RPC protocol directly,
        # so this method is implemented for compatibility but delegates
        # to the specific methods like list_tools, call_tool, etc.
        logger.warning(
            f"McpClientAdapter.send_request called with method: {method}. "
            "This method is provided for compatibility but may not work as expected. "
            "Use specific methods like list_tools, call_tool, etc. instead."
        )

        if method.startswith("tool/"):
            if method == "tool/list":
                return {"tools": await self.list_tools(target_service)}
            elif method == "tool/call":
                params_dict = params or {}
                tool_name = cast(str, params_dict.get("name", ""))
                arguments = cast(Dict[str, Any], params_dict.get("arguments", {}))
                result = await self.call_tool(target_service, tool_name, arguments)
                return {"result": result}
        elif method.startswith("prompt/"):
            if method == "prompt/list":
                return {"prompts": await self.list_prompts(target_service)}
            elif method == "prompt/get":
                params_dict = params or {}
                prompt_name = cast(str, params_dict.get("name", ""))
                arguments = cast(Dict[str, Any], params_dict.get("arguments", {}))
                return await self.get_prompt(target_service, prompt_name, arguments)
        elif method.startswith("resource/"):
            if method == "resource/list":
                return {"resources": await self.list_resources(target_service)}
            elif method == "resource/listTemplates":
                return {"templates": await self.list_resource_templates(target_service)}
            elif method == "resource/read":
                params_dict = params or {}
                uri = cast(str, params_dict.get("uri", ""))
                return {"contents": await self.read_resource(target_service, uri)}

        raise CommunicationError(f"Unsupported method: {method}", target=target_service)

    async def send_notification(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a notification to a MCP service.

        This method is not used directly with MCP SDK, but is provided
        for compatibility with the SimpleMAS BaseCommunicator interface.

        Args:
            target_service: The name of the service to send the notification to
            method: The method to call on the service
            params: The parameters to pass to the method

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        # MCP doesn't use notifications in the same way as JSON-RPC
        logger.warning(
            f"McpClientAdapter.send_notification called with method: {method}. "
            "MCP doesn't use notifications in the same way as JSON-RPC. "
            "This method is a no-op."
        )

    async def start(self) -> None:
        """Start the adapter.

        This is a no-op for MCP clients, as connections are established
        as needed when methods are called.
        """
        logger.info("Starting MCP client adapter")

    async def stop(self) -> None:
        """Stop the adapter.

        This closes all sessions and clients.
        """
        logger.info("Stopping MCP client adapter")

        # Close all sessions
        for service_name, session in self.sessions.items():
            logger.debug(f"Closing session for service: {service_name}")
            await session.close()

        # Close all clients
        for service_name, client in self.clients.items():
            logger.debug(f"Closing client for service: {service_name}")
            await client.close()

        self.sessions.clear()
        self.clients.clear()
        self.connected_services.clear()

    # MCP-specific methods

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available tools from a service.

        Args:
            target_service: The service to get tools from

        Returns:
            A list of tool definitions

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            tools = await session.list_tools()
            return [tool.model_dump() for tool in tools]
        except Exception as e:
            logger.exception(f"Failed to list tools from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to list tools from service '{target_service}': {e}", target=target_service
            )

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Call a tool on a service.

        Args:
            target_service: The service to call the tool on
            tool_name: The name of the tool to call
            arguments: Optional arguments to pass to the tool

        Returns:
            The result of the tool call

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            args = arguments or {}
            result = await session.call_tool(tool_name, **args)
            return result
        except Exception as e:
            logger.exception(f"Failed to call tool '{tool_name}' on service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to call tool '{tool_name}' on service '{target_service}': {e}", target=target_service
            )

    async def list_prompts(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available prompts from a service.

        Args:
            target_service: The service to get prompts from

        Returns:
            A list of prompt definitions

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            prompts = await session.list_prompts()
            return [prompt.model_dump() for prompt in prompts]
        except Exception as e:
            logger.exception(f"Failed to list prompts from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to list prompts from service '{target_service}': {e}", target=target_service
            )

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Get a prompt from a service.

        Args:
            target_service: The service to get the prompt from
            prompt_name: The name of the prompt to get
            arguments: Optional arguments to pass to the prompt

        Returns:
            The prompt messages

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            args = arguments or {}
            result = await session.get_prompt(prompt_name, **args)
            return result.model_dump()
        except Exception as e:
            logger.exception(f"Failed to get prompt '{prompt_name}' from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to get prompt '{prompt_name}' from service '{target_service}': {e}", target=target_service
            )

    async def list_resources(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available resources from a service.

        Args:
            target_service: The service to get resources from

        Returns:
            A list of resource definitions

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            resources = await session.list_resources()
            return [resource.model_dump() for resource in resources]
        except Exception as e:
            logger.exception(f"Failed to list resources from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to list resources from service '{target_service}': {e}", target=target_service
            )

    async def list_resource_templates(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available resource templates from a service.

        Args:
            target_service: The service to get resource templates from

        Returns:
            A list of resource template definitions

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            templates = await session.list_resource_templates()
            return [template.model_dump() for template in templates]
        except Exception as e:
            logger.exception(f"Failed to list resource templates from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to list resource templates from service '{target_service}': {e}", target=target_service
            )

    async def read_resource(
        self,
        target_service: str,
        uri: str,
    ) -> Any:
        """Read a resource from a service.

        Args:
            target_service: The service to read the resource from
            uri: The URI of the resource to read

        Returns:
            The resource data

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there's a problem with the communication
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            contents = await session.read_resource(uri)
            return [content.model_dump() for content in contents]
        except Exception as e:
            logger.exception(f"Failed to read resource '{uri}' from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to read resource '{uri}' from service '{target_service}': {e}", target=target_service
            )


class McpServerWrapper:
    """Wrapper for MCP server in SimpleMAS.

    This wrapper makes it easy to use the MCP SDK FastMCP server in SimpleMAS.
    It provides a thin wrapper around FastMCP with additional functionality.
    """

    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
    ):
        """Initialize the MCP server wrapper.

        Args:
            name: The name of the server
            instructions: Optional instructions for the server
        """
        self.mcp_server = FastMCP(name=name, instructions=instructions)

    def add_tool(
        self,
        fn: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a tool to the server.

        Args:
            fn: The function to register as a tool
            name: Optional name for the tool (defaults to function name)
            description: Optional description of what the tool does
        """
        self.mcp_server.add_tool(fn, name, description)

    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator to register a tool.

        Args:
            name: Optional name for the tool (defaults to function name)
            description: Optional description of what the tool does

        Returns:
            A decorator for registering a function as a tool
        """
        return cast(Callable[[F], F], self.mcp_server.tool(name, description))

    def add_resource(self, resource: Any) -> None:
        """Add a resource to the server.

        Args:
            resource: A Resource instance to add
        """
        self.mcp_server.add_resource(resource)

    def resource(
        self,
        uri: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator to register a resource.

        Args:
            uri: URI for the resource
            name: Optional name for the resource
            description: Optional description of the resource
            mime_type: Optional MIME type for the resource

        Returns:
            A decorator for registering a function as a resource
        """
        return cast(
            Callable[[F], F],
            self.mcp_server.resource(
                uri,
                name=name,
                description=description,
                mime_type=mime_type,
            ),
        )

    def add_prompt(self, prompt: Any) -> None:
        """Add a prompt to the server.

        Args:
            prompt: A Prompt instance to add
        """
        self.mcp_server.add_prompt(prompt)

    def prompt(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator to register a prompt.

        Args:
            name: Optional name for the prompt (defaults to function name)
            description: Optional description of what the prompt does

        Returns:
            A decorator for registering a function as a prompt
        """
        return cast(Callable[[F], F], self.mcp_server.prompt(name, description))

    def run(self, transport: str = "stdio") -> None:
        """Run the MCP server.

        Args:
            transport: Transport protocol to use ("stdio" or "sse")
        """
        self.mcp_server.run(transport)

    async def run_stdio_async(self) -> None:
        """Run the server asynchronously using stdio transport."""
        await self.mcp_server.run_stdio_async()

    async def run_sse_async(self) -> None:
        """Run the server asynchronously using SSE transport."""
        await self.mcp_server.run_sse_async()
