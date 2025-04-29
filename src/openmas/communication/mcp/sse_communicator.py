"""MCP Communicator using SSE for communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, cast

import structlog
import uvicorn
from fastapi import FastAPI
from mcp.client import sse
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP

# Import the types if available, otherwise use Any
try:
    from mcp.types import TextContent

    HAS_MCP_TYPES = True
except ImportError:
    HAS_MCP_TYPES = False
    TextContent = Any  # type: ignore

from pydantic import AnyUrl

from openmas.communication.base import BaseCommunicator, register_communicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError

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

    def _ensure_trailing_slash(self, url: str) -> str:
        """Ensure that a URL has a trailing slash to avoid redirects.

        Args:
            url: The URL to check

        Returns:
            URL with trailing slash if needed
        """
        if not url.endswith("/"):
            return f"{url}/"
        return url

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

        # Ensure service URL has a trailing slash to avoid redirects
        service_url = self._ensure_trailing_slash(self.service_urls[service_name])
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
                try:
                    self._client_managers[service_name] = sse.sse_client(service_url)
                    logger.debug(f"Created SSE client manager for service: {service_name}")
                except Exception as e:
                    logger.exception(f"Failed to create SSE client for service: {service_name}", error=str(e))
                    raise CommunicationError(
                        f"Failed to create SSE client for service '{service_name}': {e}", target=service_name
                    ) from e

            client_manager = self._client_managers[service_name]
            try:
                # The sse_client returns an async context manager, not an async generator
                # We need to use __aenter__ to get the streams
                stream_ctx = await client_manager.__aenter__()
                # Extract the streams
                read_stream = stream_ctx[0]
                write_stream = stream_ctx[1]
            except Exception as e:
                logger.exception(f"Failed to get streams for service: {service_name}", error=str(e))
                await self._cleanup_client_manager(service_name)
                raise CommunicationError(
                    f"Failed to establish connection with service '{service_name}': {e}", target=service_name
                ) from e

            # Create a session with the client
            try:
                session = ClientSession(read_stream, write_stream)
                # Initialize the session with the agent name
                await session.initialize()
            except Exception as e:
                logger.exception(f"Failed to initialize MCP session for service: {service_name}", error=str(e))
                await self._cleanup_client_manager(service_name)
                raise CommunicationError(
                    f"Failed to initialize MCP session with service '{service_name}': {e}", target=service_name
                ) from e

            # Store the client and session
            self.clients[service_name] = (read_stream, write_stream)
            self.sessions[service_name] = session
            self.connected_services.add(service_name)

            logger.info(f"Connected to MCP SSE service: {service_name}")
        except Exception as e:
            if not isinstance(e, CommunicationError):
                logger.exception(f"Failed to connect to service: {service_name}", error=str(e))
                # Clean up any partial connections
                await self._cleanup_client_manager(service_name)
                raise CommunicationError(
                    f"Failed to connect to service '{service_name}': {e}", target=service_name
                ) from e
            raise

    async def _cleanup_client_manager(self, service_name: str) -> None:
        """Clean up client manager and related resources.

        Args:
            service_name: The name of the service to clean up
        """
        if service_name in self._client_managers:
            try:
                # We no longer need to call __aexit__ since we're using __aenter__
                # Just remove the entry from the dictionary
                pass
            except Exception as e:
                logger.warning(f"Error while cleaning up client manager for {service_name}: {e}")
            del self._client_managers[service_name]

        if service_name in self.clients:
            del self.clients[service_name]

        if service_name in self.sessions:
            del self.sessions[service_name]

        if service_name in self.connected_services:
            self.connected_services.remove(service_name)

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

    def _debug_mcp_server(self, server: Any) -> None:
        """Print debug information about the MCP server.

        Args:
            server: The MCP server instance
        """
        # Log available methods and attributes
        server_methods = [m for m in dir(server) if not m.startswith("_")]
        logger.debug(f"MCP Server methods: {server_methods}")

        # Check for key methods
        mount_info = "Available" if hasattr(server, "mount_to_app") else "Not available"
        logger.debug(f"mount_to_app: {mount_info}")

        router_info = "Available" if hasattr(server, "router") else "Not available"
        logger.debug(f"router: {router_info}")

        run_sse_info = "Available" if hasattr(server, "run_sse_async") else "Not available"
        logger.debug(f"run_sse_async: {run_sse_info}")

        # Try to get more details about sse_app if it exists
        if hasattr(server, "sse_app"):
            try:
                if callable(server.sse_app):
                    import inspect

                    sig = inspect.signature(server.sse_app)
                    logger.debug(f"sse_app is callable with signature: {sig}")
                else:
                    logger.debug(f"sse_app is not callable: {type(server.sse_app)}")
            except Exception as e:
                logger.debug(f"Error inspecting sse_app: {e}")

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
                    # Create the server with the agent name in the instructions
                    instructions = self.server_instructions or f"Agent: {self.agent_name}"
                    server = FastMCP(
                        name=self.agent_name,
                        instructions=instructions,
                    )
                    self.server = server

                    # Print debug information about the server
                    self._debug_mcp_server(server)

                    # Register handlers with the server context
                    for method_name, handler_func in self.handlers.items():
                        # Register the handler as a tool
                        await self._register_tool(method_name, f"Handler for {method_name}", handler_func)

                    # Mount the server to the FastAPI app
                    # In MCP 1.6, the SSE server is mounted using server.app at the specified path
                    if hasattr(server, "router"):
                        self.app.mount("/mcp", server.router)
                        logger.info("Mounted MCP server using server.router")
                    else:
                        logger.error("Failed to mount MCP server: No router attribute found")
                        raise RuntimeError("Failed to mount MCP server: No router attribute found")

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
        """Sample a prompt from the target service.

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
            The response from the service with at least a "content" field

        Raises:
            CommunicationError: If there's a communication problem
            ValueError: If the messages parameter is invalid
        """
        if not messages:
            raise ValueError("Messages cannot be empty")

        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        # Prepare the messages in the format expected by the MCP SDK
        prepared_messages = []
        for msg in messages:
            if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                raise ValueError(f"Invalid message format: {msg}")

            role = msg["role"]
            content = msg["content"]

            # Convert to TextContent if MCP types are available
            if HAS_MCP_TYPES:
                content = TextContent(type="text", text=content) if isinstance(content, str) else content

            prepared_messages.append({"role": role, "content": content})

        # Sample parameters
        sampling_params: Dict[str, Any] = {}
        if temperature is not None:
            sampling_params["temperature"] = temperature
        if max_tokens is not None:
            sampling_params["max_tokens"] = max_tokens
        if stop_sequences is not None:
            sampling_params["stop_sequences"] = stop_sequences
        if model_preferences is not None:
            sampling_params["model_preferences"] = model_preferences

        try:
            # Use cast for the session.sample method
            result = await cast(Any, session).sample(
                messages=prepared_messages,
                system=system_prompt,
                include_context=include_context,
                **sampling_params,
            )

            # Convert result to a dictionary with at least a "content" field
            result_dict: Dict[str, Any] = {}
            if hasattr(result, "__dict__"):
                result_dict = cast(Dict[str, Any], result.__dict__)
            elif isinstance(result, dict):
                result_dict = cast(Dict[str, Any], result)
            else:
                # If result is neither a dict nor has __dict__, create a new dict
                content = str(result) if result is not None else ""
                result_dict = {"content": content}

            # Ensure content field exists and is a string
            if "content" not in result_dict:
                if "text" in result_dict:
                    result_dict["content"] = result_dict["text"]
                else:
                    result_dict["content"] = str(result)

            return result_dict
        except Exception as e:
            logger.exception(f"Error sampling prompt from {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to sample prompt from service '{target_service}': {e}", target=target_service
            ) from e

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a service.

        Args:
            target_service: The service to call the tool on
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            timeout: Optional timeout in seconds

        Returns:
            The result of the tool call

        Raises:
            CommunicationError: If there's a communication problem
            ValueError: If the tool name is invalid
        """
        if not tool_name:
            raise ValueError("Tool name cannot be empty")

        arguments = arguments or {}
        await self._connect_to_service(target_service)
        session = self.sessions[target_service]

        try:
            result = await session.call_tool(tool_name, arguments=arguments)

            # Convert result to a dictionary if possible
            if hasattr(result, "__dict__"):
                return result.__dict__
            return result
        except Exception as e:
            logger.exception(f"Error calling tool {tool_name} on {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to call tool '{tool_name}' on service '{target_service}': {e}", target=target_service
            ) from e

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
            # In MCP 1.6, tools are registered using the add_tool method
            if hasattr(self.server, "add_tool"):
                self.server.add_tool(name=name, description=description, fn=function)
                logger.debug(f"Registered tool using server.add_tool: {name}")
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
            # In MCP 1.6, we should use the prompt decorator instead of direct registration
            if hasattr(self.server, "prompt"):
                # Decorate the function
                self.server.prompt()(function)
                # No need to call add_prompt explicitly - the decorator handles it
                logger.debug(f"Registered prompt using server.prompt decorator: {name}")
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
            # In MCP 1.6, we should use the resource decorator instead of direct registration
            if hasattr(self.server, "resource"):
                # Decorate the function
                self.server.resource(name)(function)
                # No need to call add_resource explicitly - the decorator handles it
                logger.debug(f"Registered resource using server.resource decorator: {name}")
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
