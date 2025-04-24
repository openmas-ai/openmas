"""MCP Communicator using SSE for communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, cast

import structlog
import uvicorn
from fastapi import FastAPI
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.server.context import Context
from mcp.server.fastmcp import FastMCP

# Import the types if available, otherwise use Any
try:
    from mcp.types import TextContent

    HAS_MCP_TYPES = True
except ImportError:
    HAS_MCP_TYPES = False
    TextContent = Any  # type: ignore

from pydantic import AnyUrl

from simple_mas.communication.base import BaseCommunicator, register_communicator
from simple_mas.exceptions import CommunicationError, ServiceNotFoundError

# Set up logging
logger = structlog.get_logger(__name__)

# Type variable for generic return types
T = TypeVar("T")

# Type annotation for the streams returned by the context manager
StreamPair = Tuple[Any, Any]


class McpSseCommunicator(BaseCommunicator):
    """Communicator that uses MCP protocol over HTTP with Server-Sent Events.

    This communicator can function in both client mode (connecting to an HTTP endpoint)
    and server mode (integrated with a web framework like FastAPI/Starlette).

    In client mode, it connects to services specified in the service_urls parameter.
    The service URLs should be HTTP endpoints that support the MCP protocol over SSE,
    typically in the format "http://hostname:port".

    In server mode, it starts an HTTP server that exposes the agent's functionality
    through the MCP protocol over SSE.

    Attributes:
        agent_name: The name of the agent using this communicator.
        service_urls: Mapping of service names to SSE URLs.
        server_mode: Whether the communicator is running in server mode.
        http_port: The port to use for the HTTP server in server mode.
        server_instructions: Instructions for the server in server mode.
        app: FastAPI app instance when running in server mode.
        clients: Dictionary of SSE client objects for each service.
        sessions: Dictionary of ClientSession instances for each service.
        _client_managers: Dictionary of client manager context managers for each service.
        connected_services: Set of services that have been connected to.
        handlers: Dictionary of handler functions for each method.
        server: FastMCP server instance when running in server mode.
        _server_task: Asyncio task for the server when running in server mode.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        http_port: int = 8000,
        server_instructions: Optional[str] = None,
        app: Optional[FastAPI] = None,
    ) -> None:
        """Initialize the MCP SSE communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs
            server_mode: Whether to start an MCP server (True) or connect to services (False)
            http_port: Port for the HTTP server when in server mode
            server_instructions: Optional instructions for the server in server mode
            app: Optional FastAPI app to use in server mode (will create one if not provided)
        """
        super().__init__(agent_name, service_urls)
        self.server_mode = server_mode
        self.http_port = http_port
        self.server_instructions = server_instructions
        self.app = app or FastAPI(title=f"{agent_name} MCP Server")
        self.clients: Dict[str, Any] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self._client_managers: Dict[str, Any] = {}
        self.connected_services: Set[str] = set()
        self.handlers: Dict[str, Callable] = {}
        # Initialize with None but the correct type for mypy
        self.server: Optional[FastMCP] = None
        self._server_task: Optional[asyncio.Task] = None

    async def _connect_to_service(self, service_name: str) -> None:
        """Connect to an MCP service.

        Args:
            service_name: The name of the service to connect to.

        Raises:
            ServiceNotFoundError: If the service is not found in the service URLs.
            CommunicationError: If there is a problem connecting to the service.
        """
        if service_name in self.connected_services:
            logger.debug(f"Already connected to service: {service_name}")
            return

        # Check if we have a URL for this service
        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found in service URLs", target=service_name)

        service_url = self.service_urls[service_name]
        logger.debug(f"Connecting to MCP SSE service: {service_name} at {service_url}")

        try:
            # If we already have a client/session for this service, reuse it
            if service_name in self.clients and service_name in self.sessions:
                logger.debug(f"Reusing existing connection to service: {service_name}")
                self.connected_services.add(service_name)
                return

            # Create a new client and session
            logger.debug(f"Creating new MCP SSE client for service: {service_name}")

            if service_name not in self._client_managers:
                # Use SSE client for HTTP connections
                logger.debug(f"Creating SSE client manager for service: {service_name}")
                self._client_managers[service_name] = sse_client(service_url)
                logger.debug(f"Created SSE client manager for service: {service_name}")

            client_manager = self._client_managers[service_name]
            # Access the internal __aenter__ method
            stream_ctx = await client_manager.__aenter__()
            # Extract the streams
            read_stream = stream_ctx[0]
            write_stream = stream_ctx[1]

            # Create a session with the client
            session = ClientSession(read_stream, write_stream)

            # Initialize the session with the agent name
            await session.initialize()

            # Store the client and session
            self.clients[service_name] = (read_stream, write_stream)
            self.sessions[service_name] = session
            self.connected_services.add(service_name)

            logger.info(f"Connected to MCP SSE service: {service_name}")
        except Exception as e:
            logger.exception(f"Failed to connect to service: {service_name}", error=str(e))
            # Clean up any partial connections
            if service_name in self._client_managers:
                client_manager = self._client_managers[service_name]
                try:
                    await client_manager.__aexit__(None, None, None)
                except Exception:
                    pass
                del self._client_managers[service_name]

            if service_name in self.clients:
                del self.clients[service_name]

            if service_name in self.sessions:
                del self.sessions[service_name]

            if service_name in self.connected_services:
                self.connected_services.remove(service_name)

            raise CommunicationError(f"Failed to connect to service '{service_name}': {e}", target=service_name) from e

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a target service.

        In MCP mode, this maps methods to MCP concepts:
        - tool/list: List available tools
        - tool/call/NAME: Call a specific tool named NAME
        - prompt/list: List available prompts
        - prompt/get/NAME: Get a prompt response from prompt named NAME
        - resource/list: List available resources
        - resource/read/URI: Read a resource's content at URI
        - Other: Use method name as tool name

        Args:
            target_service: The name of the service to send the request to
            method: The method to call on the service
            params: The parameters to pass to the method
            response_model: Optional Pydantic model to validate and parse the response
            timeout: Optional timeout in seconds

        Returns:
            The response from the service, parsed according to the method pattern

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
            ValidationError: If the response validation fails
        """
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]
        params = params or {}

        try:
            # Handle special method patterns
            if method == "tool/list":
                # List tools
                tools = await session.list_tools()
                # Convert tool objects to dictionaries without using model_dump
                tools_data = []
                for tool in tools:
                    if hasattr(tool, "__dict__"):
                        # If the object has a __dict__, convert it to a regular dic
                        tools_data.append(tool.__dict__)
                    elif isinstance(tool, tuple) and len(tool) == 2:
                        # If it's a key-value tuple, create a dict with the first item as key
                        tools_data.append({tool[0]: tool[1]})
                    else:
                        # Otherwise just append as is
                        tools_data.append(tool)
                return tools_data
            elif method.startswith("tool/call/"):
                # Call a specific tool
                tool_name = method[10:]  # Remove 'tool/call/' prefix
                # Remove the timeout parameter
                result = await session.call_tool(tool_name, arguments=params)
                # Convert result to dict if possible
                if hasattr(result, "__dict__"):
                    return result.__dict__
                return result
            elif method == "prompt/list":
                # List prompts
                prompts = await session.list_prompts()
                # Convert to dictionaries
                prompts_data = []
                for prompt in prompts:
                    if hasattr(prompt, "__dict__"):
                        prompts_data.append(prompt.__dict__)
                    elif isinstance(prompt, tuple) and len(prompt) == 2:
                        # If it's a key-value tuple, create a dict with the first item as key
                        prompts_data.append({prompt[0]: prompt[1]})
                    else:
                        # Otherwise just append as is
                        prompts_data.append(prompt)
                return prompts_data
            elif method.startswith("prompt/get/"):
                # Get a prompt
                prompt_name = method[11:]  # Remove 'prompt/get/' prefix
                # Note: using result_var to avoid mypy error about incompatible types
                result_var = await session.get_prompt(prompt_name, arguments=params)
                # Convert result to dict if possible
                if hasattr(result_var, "__dict__"):
                    return result_var.__dict__
                return result_var
            elif method == "resource/list":
                # List resources
                resources = await session.list_resources()
                # Convert to dictionaries
                resources_data = []
                for resource in resources:
                    if hasattr(resource, "__dict__"):
                        resources_data.append(resource.__dict__)
                    elif isinstance(resource, tuple) and len(resource) == 2:
                        # If it's a key-value tuple, create a dict with the first item as key
                        resources_data.append({resource[0]: resource[1]})
                    else:
                        # Otherwise just append as is
                        resources_data.append(resource)
                return resources_data
            elif method.startswith("resource/read/"):
                # Read a resource
                resource_uri = method[14:]  # Remove 'resource/read/' prefix

                # Cast to AnyUrl for resource read
                uri = cast(AnyUrl, resource_uri)
                content, mime_type = await session.read_resource(uri)
                return {"content": content, "mime_type": mime_type}
            else:
                # Use method as tool name
                result = await session.call_tool(method, arguments=params)
                # Convert result to dict if possible
                if hasattr(result, "__dict__"):
                    return result.__dict__
                return result

        except Exception as e:
            logger.exception(f"Failed to send request to service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to send request to service '{target_service}' method '{method}': {e}",
                target=target_service,
            ) from e

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
            target_service: The name of the service to send the notification to
            method: The method to call on the service
            params: The parameters to pass to the method

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        # Make sure we're connected to the service
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]
        params = params or {}

        try:
            # Create a fire-and-forget task
            async def _send_notification() -> None:
                try:
                    await session.call_tool(method, arguments=params)
                except Exception as e:
                    logger.warning(
                        "Failed to send notification",
                        target_service=target_service,
                        method=method,
                        error=str(e),
                    )

            # Create task and let it run in the background
            asyncio.create_task(_send_notification())
        except Exception as e:
            logger.warning(
                "Failed to create notification task",
                target_service=target_service,
                method=method,
                error=str(e),
            )

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self.handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")

        # If we're in server mode and the server is already running, register the handler with the server
        if self.server_mode and self.server:
            await self._register_tool(method, f"Handler for {method}", handler)

    async def start(self) -> None:
        """Start the communicator.

        In client mode, this is a no-op.
        In server mode, this starts the MCP server on the configured HTTP port.
        """
        if self.server_mode:
            logger.info(f"Starting MCP SSE server for agent {self.agent_name} on port {self.http_port}")

            # Define a function to run the server
            async def run_sse_server() -> None:
                try:
                    # Create a context for the server
                    context: Context = Context()

                    # Create the server with the agent name in the instructions
                    instructions = self.server_instructions or f"Agent: {self.agent_name}"
                    server = FastMCP(
                        instructions=instructions,
                        context=context,
                    )
                    self.server = server

                    # Register handlers with the server context
                    for method_name, handler_func in self.handlers.items():
                        # Register the handler as a tool
                        await self._register_tool(method_name, f"Handler for {method_name}", handler_func)

                    # Mount the server to the FastAPI app if the method exists
                    if hasattr(server, "mount_to_app"):
                        server.mount_to_app(self.app)  # type: ignore

                    # Run the HTTP server with uvicorn
                    config = uvicorn.Config(
                        app=self.app,
                        host="0.0.0.0",
                        port=self.http_port,
                        log_level="info",
                    )
                    uvicorn_server = uvicorn.Server(config)
                    await uvicorn_server.serve()
                except Exception as e:
                    logger.exception("Error running MCP SSE server", error=str(e))
                finally:
                    logger.info("MCP SSE server stopped")
                    self.server = None

            # Start the server in a task
            self._server_task = asyncio.create_task(run_sse_server())
            logger.info("MCP SSE server started")

    async def stop(self) -> None:
        """Stop the communicator.

        In client mode, this closes connections to all services.
        In server mode, this stops the MCP server.
        """
        if self.server_mode:
            # Stop the server task
            if self._server_task:
                logger.info("Stopping MCP SSE server")
                self._server_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(self._server_task), timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                self._server_task = None

            self.server = None
        else:
            # Client mode - close all connections
            logger.info("Closing connections to MCP SSE services")

            # Close client managers
            for service_name, client_manager in list(self._client_managers.items()):
                try:
                    await client_manager.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing client manager for {service_name}: {e}")

            # Clear all collections
            self.clients.clear()
            self.sessions.clear()
            self._client_managers.clear()
            self.connected_services.clear()

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List tools available in a target service.

        Args:
            target_service: The name of the service to list tools from

        Returns:
            List of tools with their descriptions

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        result = await self.send_request(target_service, "tool/list")
        # Ensure we return a list of dictionaries
        if isinstance(result, dict) and "tools" in result:
            return cast(List[Dict[str, Any]], result["tools"])
        elif isinstance(result, list):
            return cast(List[Dict[str, Any]], result)
        else:
            return [{"item": result}] if result else []

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
        """Sample a prompt from a target service.

        Args:
            target_service: The name of the service to sample the prompt from
            messages: The messages to include in the prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature for sampling
            max_tokens: Optional maximum number of tokens to generate
            include_context: Optional context to include
            model_preferences: Optional model preferences
            stop_sequences: Optional stop sequences
            timeout: Optional timeout in seconds

        Returns:
            The sampled prompt result

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        # Convert messages to ContentBlock objects if MCP types are available
        content_blocks = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if HAS_MCP_TYPES:
                # Create TextContent with proper arguments
                text_content = TextContent(text=content, type="text")
                content_blocks.append({"role": role, "content": text_content})
            else:
                # Just use the original message format
                content_blocks.append({"role": role, "content": content})

        # Build the arguments
        arguments: Dict[str, Any] = {
            "messages": content_blocks,
        }

        # Add optional arguments
        if system_prompt is not None:
            arguments["system_prompt"] = system_prompt
        if temperature is not None:
            arguments["temperature"] = temperature
        if max_tokens is not None:
            arguments["max_tokens"] = max_tokens
        if include_context is not None:
            arguments["include_context"] = include_context
        if model_preferences is not None:
            arguments["model_preferences"] = model_preferences
        if stop_sequences is not None:
            arguments["stop_sequences"] = stop_sequences

        # Call the sample_prompt tool
        result = await self.call_tool(target_service, "sample_prompt", arguments, timeout=timeout)

        # Ensure we return a dictionary
        if hasattr(result, "__dict__"):
            return cast(Dict[str, Any], result.__dict__)
        elif isinstance(result, dict):
            return cast(Dict[str, Any], result)
        else:
            return {"result": result}

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a target service.

        Args:
            target_service: The name of the service to call the tool on
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            timeout: Optional timeout in seconds

        Returns:
            The result of the tool call

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        method = f"tool/call/{tool_name}"
        return await self.send_request(target_service, method, arguments, timeout=timeout)

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Get a prompt from a target service.

        Args:
            target_service: The name of the service to get the prompt from
            prompt_name: The name of the prompt to get
            arguments: The arguments to pass to the prompt
            timeout: Optional timeout in seconds

        Returns:
            The prompt result

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        method = f"prompt/get/{prompt_name}"
        return await self.send_request(target_service, method, arguments, timeout=timeout)

    async def _handle_mcp_request(
        self, method: str, params: Optional[Dict[str, Any]] = None, target_service: Optional[str] = None
    ) -> Optional[Any]:
        """Handle an MCP request.

        This is used internally when running in server mode, to handle incoming
        requests from MCP clients.

        Args:
            method: The method to handle
            params: The parameters for the method
            target_service: Optional target service

        Returns:
            The result of handling the request, or None
        """
        if method not in self.handlers:
            raise ValueError(f"Method '{method}' not registered")

        handler = self.handlers[method]
        params = params or {}

        try:
            if target_service:
                # Include target service in params
                result = await handler(target_service=target_service, **params)
            else:
                # Call handler with just the params
                result = await handler(**params)
            return result
        except Exception as e:
            logger.exception(f"Error handling MCP request for method '{method}'", error=str(e))
            raise CommunicationError(f"Error handling MCP request: {e}") from e

    async def _register_tool(self, name: str, description: str, function: Callable) -> None:
        """Internal helper to register a tool with the MCP server.

        This method handles API differences in different MCP versions.

        Args:
            name: The name of the tool
            description: The description of the tool
            function: The function to call when the tool is invoked
        """
        if not self.server_mode or not self.server:
            logger.warning("Cannot register tool in client mode or before server is started")
            return

        try:
            # Try different ways to register tools based on the FastMCP version
            if hasattr(self.server, "register_tool"):
                await self.server.register_tool(  # type: ignore
                    name=name,
                    description=description,
                    fn=function,
                )
            elif hasattr(self.server, "add_tool"):
                self.server.add_tool(name=name, description=description, fn=function)  # type: ignore
            else:
                logger.warning(f"Cannot register tool {name}: No suitable registration method found")

            logger.debug(f"Registered tool: {name}")
        except Exception as e:
            logger.error(f"Failed to register tool '{name}': {e}")
            raise

    async def register_tool(self, name: str, description: str, function: Callable) -> None:
        """Register a tool with the MCP server.

        Args:
            name: The name of the tool
            description: The description of the tool
            function: The function to call when the tool is invoked
        """
        await self._register_tool(name, description, function)

    async def register_prompt(self, name: str, description: str, function: Callable) -> None:
        """Register a prompt with the MCP server.

        Args:
            name: The name of the prompt
            description: The description of the prompt
            function: The function to call when the prompt is invoked
        """
        if not self.server_mode or not self.server:
            logger.warning("Cannot register prompt in client mode or before server is started")
            return

        try:
            # Try different ways to register prompts based on the FastMCP version
            if hasattr(self.server, "register_prompt"):
                await self.server.register_prompt(  # type: ignore
                    name=name,
                    description=description,
                    fn=function,
                )
            elif hasattr(self.server, "add_prompt"):
                self.server.add_prompt(name=name, description=description, fn=function)  # type: ignore
            else:
                logger.warning(f"Cannot register prompt {name}: No suitable registration method found")

            logger.debug(f"Registered prompt: {name}")
        except Exception as e:
            logger.error(f"Failed to register prompt '{name}': {e}")
            raise

    async def register_resource(
        self, name: str, description: str, function: Callable, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource with the MCP server.

        Args:
            name: The name of the resource
            description: The description of the resource
            function: The function to call when the resource is requested
            mime_type: The MIME type of the resource
        """
        if not self.server_mode or not self.server:
            logger.warning("Cannot register resource in client mode or before server is started")
            return

        try:
            # Try different ways to register resources based on the FastMCP version
            if hasattr(self.server, "register_resource"):
                await self.server.register_resource(  # type: ignore
                    uri=name,
                    description=description,
                    fn=function,
                    mime_type=mime_type,
                )
            elif hasattr(self.server, "add_resource"):
                self.server.add_resource(  # type: ignore
                    uri=name,
                    description=description,
                    fn=function,
                    mime_type=mime_type,
                )
            else:
                logger.warning(f"Cannot register resource {name}: No suitable registration method found")

            logger.debug(f"Registered resource: {name}")
        except Exception as e:
            logger.error(f"Failed to register resource '{name}': {e}")
            raise

    async def _mcp_custom_method(self, session: ClientSession, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a custom MCP method call.

        Args:
            session: The MCP client session
            method: The method name
            params: The method parameters

        Returns:
            The result of the method call
        """
        # This is a bridge between MCP tools and our handler methods
        if method not in self.handlers:
            raise ValueError(f"Method '{method}' not registered")

        handler = self.handlers[method]
        try:
            result = await handler(**params)
            # Convert result to dict if possible
            if hasattr(result, "__dict__"):
                return cast(Dict[str, Any], result.__dict__)
            elif isinstance(result, dict):
                return cast(Dict[str, Any], result)
            else:
                return {"result": result}
        except Exception as e:
            logger.exception(f"Error handling MCP custom method '{method}'", error=str(e))
            raise ValueError(f"Error handling custom method: {e}") from e


# Register the communicator
register_communicator("mcp-sse", McpSseCommunicator)
