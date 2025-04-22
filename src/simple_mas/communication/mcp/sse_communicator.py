"""MCP SSE communicator for SimpleMAS.

This module provides a communicator that uses the MCP protocol over HTTP using
Server-Sent Events (SSE). It can be used as both a client (connecting to an HTTP
endpoint) and a server (integrated with a web framework like FastAPI/Starlette).
"""

import asyncio
from typing import Any, AsyncContextManager, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar

from fastapi import FastAPI
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel

from simple_mas.communication.base import BaseCommunicator
from simple_mas.exceptions import CommunicationError, ServiceNotFoundError
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class McpSseCommunicator(BaseCommunicator):
    """Communicator that uses MCP protocol over HTTP with Server-Sent Events.

    This communicator can function in both client mode (connecting to an HTTP endpoint)
    and server mode (integrated with a web framework like FastAPI/Starlette).

    Attributes:
        agent_name: The name of the agent using this communicator.
        service_urls: Mapping of service names to SSE URLs.
        server_mode: Whether the communicator is running in server mode.
        http_port: The port to use for the HTTP server in server mode.
        clients: Dictionary of SSE client objects for each service.
        sessions: Dictionary of ClientSession instances for each service.
        connected_services: Set of services that have been connected to.
        handlers: Dictionary of handler functions for each method.
        app: FastAPI app instance when running in server mode.
        server: FastMCP server instance when running in server mode.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        http_port: int = 8000,
        server_instructions: Optional[str] = None,
        app: Optional[FastAPI] = None,
    ):
        """Initialize the MCP SSE communicator.

        Args:
            agent_name: The name of the agent using this communicator.
            service_urls: Mapping of service names to SSE URLs.
                In client mode, each URL should point to an SSE endpoint.
                In server mode, this parameter is ignored.
            server_mode: Whether to run in server mode (True) or client mode (False).
            http_port: The port to use for the HTTP server in server mode.
            server_instructions: Optional instructions for the server when in server mode.
            app: Optional FastAPI app to use in server mode. If not provided, one will be created.
        """
        super().__init__(agent_name, service_urls)
        self.server_mode = server_mode
        self.http_port = http_port
        self.server_instructions = server_instructions
        self.clients: Dict[str, Tuple[Any, Any]] = {}  # Dictionary of SSE client objects
        self.sessions: Dict[str, ClientSession] = {}  # Dictionary of ClientSession instances
        self.connected_services: Set[str] = set()
        self.handlers: Dict[str, Callable] = {}
        self.app = app or FastAPI(title=f"{agent_name} MCP Server")
        self.server = None  # FastMCP server instance
        self._server_task: Optional[asyncio.Task] = None
        self._client_managers: Dict[str, AsyncContextManager] = {}  # Context managers for SSE clients

    async def _connect_to_service(self, service_name: str) -> None:
        """Connect to a MCP service using SSE.

        Args:
            service_name: The name of the service to connect to.

        Raises:
            ServiceNotFoundError: If the service is not found in service_urls.
            CommunicationError: If there's a problem connecting to the service.
        """
        if service_name in self.connected_services:
            return

        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

        url = self.service_urls[service_name]
        logger.info(f"Connecting to MCP service: {service_name} at URL: {url}")

        try:
            # Create the SSE client context manager
            client_manager = sse_client(url)
            self._client_managers[service_name] = client_manager

            # Enter the context manager to get the client
            read_stream, write_stream = await client_manager.__aenter__()
            self.clients[service_name] = (read_stream, write_stream)

            # Create a session for the client
            session = ClientSession(read_stream, write_stream)
            await session.initialize(name=self.agent_name)
            self.sessions[service_name] = session

            self.connected_services.add(service_name)
            logger.info(f"Connected to MCP service: {service_name}")
        except Exception as e:
            logger.exception(f"Failed to connect to MCP service: {service_name}", error=str(e))
            raise CommunicationError(
                f"Failed to connect to service '{service_name}': {e}",
                target=service_name,
            )

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a target service and wait for a response.

        MCP doesn't directly support the JSON-RPC protocol used by SimpleMAS,
        so this method maps common method patterns to MCP SDK calls.

        Args:
            target_service: The name of the service to send the request to.
            method: The method to call on the service.
            params: The parameters to pass to the method.
            response_model: Optional Pydantic model to validate the response.
            timeout: Optional timeout in seconds.

        Returns:
            The response from the service.

        Raises:
            ServiceNotFoundError: If the target service is not found.
            CommunicationError: If there's a problem with the communication.
        """
        if self.server_mode:
            logger.warning("send_request called in server mode, which is not fully supported")
            return None

        # Connect to the service if needed
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        # Map the method to MCP SDK calls
        try:
            if method.startswith("tool/"):
                if method == "tool/list":
                    tools = await session.list_tools()
                    return {"tools": [tool.model_dump() for tool in tools]}
                elif method == "tool/call":
                    params_dict = params or {}
                    tool_name = params_dict.get("name", "")
                    arguments = params_dict.get("arguments", {})
                    result = await session.call_tool(tool_name, arguments, timeout=timeout)
                    return {"result": result}
            elif method.startswith("prompt/"):
                if method == "prompt/list":
                    prompts = await session.list_prompts()
                    return {"prompts": [prompt.model_dump() for prompt in prompts]}
                elif method == "prompt/get":
                    params_dict = params or {}
                    prompt_name = params_dict.get("name", "")
                    arguments = params_dict.get("arguments", {})
                    result = await session.get_prompt(prompt_name, arguments, timeout=timeout)
                    return result
            elif method.startswith("resource/"):
                if method == "resource/list":
                    resources = await session.list_resources()
                    return {"resources": [resource.model_dump() for resource in resources]}
                elif method == "resource/read":
                    params_dict = params or {}
                    uri = params_dict.get("uri", "")
                    content = await session.read_resource(uri)
                    return {"content": content}

            # Handle custom methods by directly calling tools
            result = await session.call_tool(method, params or {}, timeout=timeout)
            return result

        except Exception as e:
            logger.exception(
                f"Error sending request to {target_service}.{method}",
                error=str(e),
            )
            raise CommunicationError(
                f"Failed to send request to {target_service}.{method}: {e}",
                target=target_service,
            )

    async def send_notification(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a notification to a target service.

        MCP doesn't have a direct equivalent to notifications in JSON-RPC,
        so this is implemented as a request without waiting for a response.

        Args:
            target_service: The name of the service to send the notification to.
            method: The method to call on the service.
            params: The parameters to pass to the method.

        Raises:
            ServiceNotFoundError: If the target service is not found.
            CommunicationError: If there's a problem with the communication.
        """
        if self.server_mode:
            logger.warning("send_notification called in server mode, which is not fully supported")
            return

        # Connect to the service if needed
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        # Map the method to MCP SDK calls, but don't wait for response
        try:
            if method.startswith("notify/"):
                # Use call_tool, but don't wait for the result
                asyncio.create_task(session.call_tool(method, params or {}))
            else:
                # Just use the method as a tool name
                asyncio.create_task(session.call_tool(method, params or {}))
        except Exception as e:
            logger.exception(
                f"Error sending notification to {target_service}.{method}",
                error=str(e),
            )
            raise CommunicationError(
                f"Failed to send notification to {target_service}.{method}: {e}",
                target=target_service,
            )

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        In server mode, this registers the handler as an MCP tool.
        In client mode, this is stored but not used directly.

        Args:
            method: The method name to handle.
            handler: The handler function.
        """
        self.handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")

        # If server is already running, add the tool to it
        if self.server_mode and self.server:
            self.server.add_tool(
                handler,
                name=method,
                description=f"Handler for {method}",
            )

    async def start(self) -> None:
        """Start the communicator.

        In server mode, this starts the FastMCP server with FastAPI and registers all MCP tools,
        prompts, and resources from the associated agent.
        In client mode, this is a no-op as connections are established as needed.
        """
        if self.server_mode:
            logger.info("Starting MCP SSE server")

            # Import here to ensure MCP is available
            from mcp.server.fastmcp import create_fastmcp
            from mcp.server.prompts import Prompt
            from mcp.server.resources import Resource

            # Create and start the server
            fastmcp_cm = create_fastmcp(
                name=self.agent_name,
                instructions=self.server_instructions,
            )
            self.server = await fastmcp_cm.__aenter__()

            # Register tools, prompts, and resources from the associated agent if available
            if hasattr(self, "agent") and self.agent is not None:
                # Register tools
                for tool_name, tool_data in self.agent._tools.items():
                    metadata = tool_data["metadata"]
                    function = tool_data["function"]
                    self.server.add_tool(
                        function,
                        name=metadata.get("name"),
                        description=metadata.get("description"),
                    )
                    logger.debug(f"Registered MCP tool: {tool_name}")

                # Register prompts
                for prompt_name, prompt_data in self.agent._prompts.items():
                    metadata = prompt_data["metadata"]
                    function = prompt_data["function"]
                    prompt = Prompt(
                        fn=function,
                        name=metadata.get("name"),
                        description=metadata.get("description"),
                    )
                    self.server.add_prompt(prompt)
                    logger.debug(f"Registered MCP prompt: {prompt_name}")

                # Register resources
                for resource_uri, resource_data in self.agent._resources.items():
                    metadata = resource_data["metadata"]
                    function = resource_data["function"]
                    resource = Resource(
                        uri=metadata.get("uri"),
                        fn=function,
                        name=metadata.get("name"),
                        description=metadata.get("description"),
                        mime_type=metadata.get("mime_type"),
                    )
                    self.server.add_resource(resource)
                    logger.debug(f"Registered MCP resource: {resource_uri}")

            # Register all handlers as tools
            for method, handler in self.handlers.items():
                self.server.add_tool(
                    handler,
                    name=method,
                    description=f"Handler for {method}",
                )

            # Register the MCP app with FastAPI
            self.server.register_with_app(self.app, path="/mcp")

            # Start the server (non-blocking) with Uvicorn
            import uvicorn

            # Define the server function to run in a task
            async def run_server():
                config = uvicorn.Config(
                    app=self.app,
                    host="0.0.0.0",
                    port=self.http_port,
                    log_level="info",
                )
                server = uvicorn.Server(config)
                await server.serve()

            # Start the server in a task
            self._server_task = asyncio.create_task(run_server())
            logger.info(f"MCP SSE server started on port {self.http_port}")
        else:
            logger.debug("Not in server mode, no server to start")

    async def stop(self) -> None:
        """Stop the communicator.

        In server mode, this stops the FastMCP server and cancels the server task.
        In client mode, this closes any active sessions.
        """
        logger.info(f"Stopping MCP SSE communicator in {'server' if self.server_mode else 'client'} mode")

        if self.server_mode:
            if self._server_task:
                logger.debug("Cancelling server task")
                self._server_task.cancel()
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    pass
                self._server_task = None

            if self.server:
                logger.debug("Closing server")
                await self.server.__aexit__(None, None, None)
                self.server = None
        else:
            # Close any active sessions in client mode
            if self._client_managers:
                logger.debug("Closing client managers")
                for service_name, client_manager in self._client_managers.items():
                    logger.debug(f"Closing client for service: {service_name}")
                    try:
                        await client_manager.__aexit__(None, None, None)
                    except Exception as e:
                        logger.warning(f"Error closing client for {service_name}: {e}")

        self.clients.clear()
        self._client_managers.clear()
        self.connected_services.clear()

        logger.info("MCP SSE communicator stopped")

    # Helper methods for MCP-specific functionality

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available tools from a service.

        Args:
            target_service: The service to get tools from.

        Returns:
            A list of tool definitions.

        Raises:
            ServiceNotFoundError: If the target service is not found.
            CommunicationError: If there's a problem with the communication.
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            tools = await session.list_tools()
            return [tool.model_dump() for tool in tools]
        except Exception as e:
            logger.exception(f"Failed to list tools from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to list tools from service '{target_service}': {e}",
                target=target_service,
            )

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

        This method allows MCP servers to request generation from LLMs through the MCP client,
        which is especially useful for implementing agentic capabilities in MCP servers.

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
            ServiceNotFoundError: If the target service is not found.
            CommunicationError: If there's a problem with the communication.
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        # Prepare sampling parameters
        params: Dict[str, Any] = {
            "messages": messages,
        }

        # Add optional parameters if provided
        if system_prompt is not None:
            params["systemPrompt"] = system_prompt
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["maxTokens"] = max_tokens
        if include_context is not None:
            params["includeContext"] = include_context
        if model_preferences is not None:
            params["modelPreferences"] = model_preferences
        if stop_sequences is not None:
            params["stopSequences"] = stop_sequences

        try:
            # Use the sampling/createMessage method to request sampling
            result = await session._call_method("sampling/createMessage", params=params, timeout=timeout)
            return result
        except Exception as e:
            logger.exception(
                f"Failed to sample prompt from service: {target_service}",
                error=str(e),
            )
            raise CommunicationError(
                f"Failed to sample prompt from service '{target_service}': {e}",
                target=target_service,
            )

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a service.

        Args:
            target_service: The service to call the tool on.
            tool_name: The name of the tool to call.
            arguments: The arguments to pass to the tool.
            timeout: Optional timeout in seconds.

        Returns:
            The result of the tool call.

        Raises:
            ServiceNotFoundError: If the target service is not found.
            CommunicationError: If there's a problem with the communication.
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            result = await session.call_tool(tool_name, arguments or {}, timeout=timeout)
            return result
        except Exception as e:
            logger.exception(
                f"Failed to call tool {tool_name} on service: {target_service}",
                error=str(e),
            )
            raise CommunicationError(
                f"Failed to call tool {tool_name} on service '{target_service}': {e}",
                target=target_service,
            )

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Get a prompt from a service.

        Args:
            target_service: The service to get the prompt from.
            prompt_name: The name of the prompt to get.
            arguments: The arguments to pass to the prompt.
            timeout: Optional timeout in seconds.

        Returns:
            The result of the prompt.

        Raises:
            ServiceNotFoundError: If the target service is not found.
            CommunicationError: If there's a problem with the communication.
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            result = await session.get_prompt(prompt_name, arguments or {}, timeout=timeout)
            return result
        except Exception as e:
            logger.exception(
                f"Failed to get prompt {prompt_name} from service: {target_service}",
                error=str(e),
            )
            raise CommunicationError(
                f"Failed to get prompt {prompt_name} from service '{target_service}': {e}",
                target=target_service,
            )

    async def _handle_mcp_request(
        self, method: str, params: Optional[Dict[str, Any]] = None, target_service: Optional[str] = None
    ) -> None:
        """Handle an MCP request by dispatching to the appropriate handler.

        Args:
            method: The method to call.
            params: The parameters to pass to the method.
            target_service: The target service to forward the request to.

        Raises:
            NotImplementedError: If the method is not supported in server mode.
        """
        logger.debug(f"Handling MCP request: {method} with params: {params}")
        if not self.server_mode:
            raise NotImplementedError("Method handling is only available in server mode")

        if target_service:
            # Forward the request to the target service
            return await self.send_request(target_service, method, params)

        if method in self.handlers:
            # Call the registered handler
            handler = self.handlers[method]
            if params:
                return await handler(**params)
            else:
                return await handler()
        else:
            # Method not found
            raise NotImplementedError(f"Method {method} not registered in server handlers")

    async def register_tool(self, name: str, description: str, function: Callable) -> None:
        """Register a tool with the server.

        In server mode, this adds the tool to the FastMCP server.
        In client mode, this is a no-op.

        Args:
            name: The name of the tool.
            description: A description of the tool.
            function: The function that implements the tool.
        """
        logger.debug(f"Registering tool: {name} - {description}")

        if self.server_mode and self.server:
            self.server.add_tool(function, name=name, description=description)
            logger.info(f"Registered tool '{name}': {description} with FastMCP server")
        else:
            # In client mode or if server not started yet, register as a handler
            self.handlers[name] = function
            logger.debug(f"Stored tool '{name}' as handler for later registration with server")

    async def register_prompt(self, name: str, description: str, function: Callable) -> None:
        """Register a prompt with the server.

        In server mode, this adds the prompt to the FastMCP server.
        In client mode, this is a no-op.

        Args:
            name: The name of the prompt.
            description: A description of the prompt.
            function: The function that implements the prompt.
        """
        logger.debug(f"Registering prompt: {name} - {description}")

        if self.server_mode and self.server:
            self.server.add_prompt(function, name=name, description=description)
            logger.info(f"Registered prompt '{name}': {description} with FastMCP server")
        else:
            # In client mode or if server not started yet, store for later
            logger.debug(f"Client mode or server not started, cannot register prompt '{name}' yet")

    async def register_resource(
        self, name: str, description: str, function: Callable, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource with the server.

        In server mode, this adds the resource to the FastMCP server.
        In client mode, this is a no-op.

        Args:
            name: The name of the resource (URI path).
            description: A description of the resource.
            function: The function that implements the resource.
            mime_type: The MIME type of the resource.
        """
        logger.debug(f"Registering resource: {name} - {description}")

        if self.server_mode and self.server:
            self.server.add_resource(function, uri=name, description=description, mime_type=mime_type)
            logger.info(f"Registered resource '{name}': {description} with FastMCP server")
        else:
            # In client mode or if server not started yet, store for later
            logger.debug(f"Client mode or server not started, cannot register resource '{name}' yet")
