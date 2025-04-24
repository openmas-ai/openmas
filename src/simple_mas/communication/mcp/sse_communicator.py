"""MCP Communicator using SSE for communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar

import structlog
from fastapi import FastAPI
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.server.context import Context
from mcp.server.fastmcp import FastMCP

from simple_mas.communication.base import BaseCommunicator
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
            raise ServiceNotFoundError(f"Service '{service_name}' not found in service URLs")

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
            # Access the internal __aenter__ method but avoid typing issues
            stream_ctx = await client_manager.__aenter__()
            # Manually extract the streams using indexing to avoid typing errors
            read_stream = stream_ctx[0]
            write_stream = stream_ctx[1]

            # Create a session with the client
            session = ClientSession(read_stream, write_stream)

            # Initialize the session (removed 'name' parameter)
            await session.initialize()

            # Store the client and session
            self.clients[service_name] = client_manager
            self.sessions[service_name] = session
            self.connected_services.add(service_name)

            logger.info(f"Connected to MCP SSE service: {service_name}")
        except Exception as e:
            logger.exception(f"Failed to connect to service: {service_name}", error=str(e))
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
        - tool/call: Call a specific tool
        - prompt/list: List available prompts
        - prompt/get: Get a prompt response
        - resource/list: List available resources
        - resource/read: Read a resource's content
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
                # Get a promp
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
                from typing import cast

                from pydantic import AnyUrl

                # Convert string to AnyUrl using a type workaround for mypy
                uri = cast(AnyUrl, resource_uri)
                content, mime_type = await session.read_resource(uri)
                return {"content": content, "mime_type": mime_type}
            elif method not in ["tool/list", "prompt/list", "resource/list"] and not any(
                method.startswith(prefix) for prefix in ["tool/call/", "prompt/get/", "resource/read/"]
            ):
                # Assume we're calling a custom method directly
                # This is useful for clients that implement special methods
                method = method.replace("/", ".")  # Convert RPC-style paths to method names
                logger.debug(f"Calling custom method: {method}")
                result = await session.call_tool(method, arguments=params)
                # Convert result to dict if possible
                if hasattr(result, "__dict__"):
                    return result.__dict__
                return result
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
                # Use call_tool, but don't wait for the resul
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

        # If server is already running, add the tool to i
        if self.server_mode and self.server:
            self.server.add_tool(
                handler,
                name=method,
                description=f"Handler for {method}",
            )

    async def start(self) -> None:
        """Start the communicator.

        In server mode, this starts the SSE server.
        In client mode, this is a no-op.
        """
        if self.server_mode:
            # Server mode - start an HTTP server with SSE endpoint
            logger.info(f"Starting MCP SSE server on port {self.http_port}")

            # Import server-related modules only when needed
            from mcp.server.fastmcp import FastMCP

            # Create a new FastMCP instance (with provided app if any)
            context = Context(instructions=self.server_instructions) if self.server_instructions else Context()
            self.server = FastMCP(context=context)

            # Initialize the server
            if hasattr(self.server, "start"):
                await self.server.start()
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
                # Add type ignore to solve attribute error
                await self.server.__aexit__(None, None, None)  # type: ignore
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
        """List the tools available on the target service.

        Args:
            target_service: The name of the service to list tools from

        Returns:
            A list of tool definitions

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        try:
            result = await self.send_request(target_service, "tool/list")
            # Ensure we return a list of dictionaries
            if isinstance(result, list):
                # Convert all items to dictionaries if they're not already
                return [item if isinstance(item, dict) else {"name": str(item)} for item in result]
            else:
                # If it's not a list, wrap it in a list with a single item
                return [{"tools": str(result)}]
        except Exception as e:
            logger.error(f"Failed to list tools from service: {target_service}", error=str(e))
            raise CommunicationError(
                f"Failed to list tools from service '{target_service}': {e}", target=target_service
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
        """Sample a prompt from a model using the MCP protocol.

        Args:
            target_service: The service to sample the prompt from
            messages: A list of messages to send to the model
            system_prompt: Optional system prompt to use
            temperature: Optional temperature parameter for sampling
            max_tokens: Optional maximum number of tokens to generate
            include_context: Optional context to include in the prompt
            model_preferences: Optional model preferences
            stop_sequences: Optional list of stop sequences
            timeout: Optional timeout in seconds

        Returns:
            The response from the model

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        # In this implementation, we'll use custom tool to sample a prompt
        # This is a workaround as standard ClientSession may not have sample_prompt method
        try:
            # Use the call_tool method to call a sample_prompt tool
            params: Dict[str, Any] = {
                "messages": messages,
            }
            if system_prompt is not None:
                params["system_prompt"] = system_prompt
            if temperature is not None:
                params["temperature"] = temperature
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            if include_context is not None:
                params["include_context"] = include_context
            if model_preferences is not None:
                params["model_preferences"] = model_preferences
            if stop_sequences is not None:
                params["stop_sequences"] = stop_sequences

            # Call the sample_prompt tool
            result = await self.call_tool(
                target_service=target_service,
                tool_name="sample_prompt",
                arguments=params,
                timeout=timeout,
            )

            # Ensure we return a Dictionary
            if isinstance(result, dict):
                # Convert to Dict[str, Any] to match return type
                response_dict: Dict[str, Any] = {str(k): v for k, v in result.items()}
                return response_dict
            elif hasattr(result, "__dict__"):
                # Convert to Dict[str, Any] to match return type
                response_dict = {str(k): v for k, v in result.__dict__.items() if not k.startswith("_")}
                return response_dict
            else:
                # Fallback for other types - wrap in a dictionary
                return {"result": str(result)}
        except Exception as e:
            logger.exception(f"Failed to sample prompt from service: {target_service}", error=str(e))
            # Return error as a dictionary to maintain type signature
            return {
                "error": str(e),
                "status": "failed",
                "service": target_service,
            }

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on the target service.

        Args:
            target_service: The name of the service to call the tool on
            tool_name: The name of the tool to call
            arguments: Optional arguments for the tool
            timeout: Optional timeout in seconds

        Returns:
            The result of the tool call

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        try:
            result = await self.send_request(
                target_service,
                f"tool/call/{tool_name}",
                params=arguments,
                timeout=timeout,
            )
            return result
        except Exception as e:
            logger.error(f"Failed to call tool on service: {target_service}", tool=tool_name, error=str(e))
            raise CommunicationError(
                f"Failed to call tool '{tool_name}' on service '{target_service}': {e}",
                target=target_service,
            )

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Get a prompt from the target service.

        Args:
            target_service: The name of the service to get the prompt from
            prompt_name: The name of the prompt to get
            arguments: Optional arguments for the prompt
            timeout: Optional timeout in seconds

        Returns:
            The result of the prompt

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        try:
            result = await self.send_request(
                target_service,
                f"prompt/get/{prompt_name}",
                params=arguments,
                timeout=timeout,
            )
            return result
        except Exception as e:
            logger.error(
                f"Failed to get prompt from service: {target_service}",
                prompt=prompt_name,
                error=str(e),
            )
            raise CommunicationError(
                f"Failed to get prompt '{prompt_name}' from service '{target_service}': {e}",
                target=target_service,
            )

    async def _handle_mcp_request(
        self, method: str, params: Optional[Dict[str, Any]] = None, target_service: Optional[str] = None
    ) -> None:
        """Handle an MCP request from a connected server.

        Args:
            method: The method to handle
            params: The parameters for the method
            target_service: Optional target service for forwarding the reques

        Returns:
            None
        """
        logger.debug(f"Handling MCP request: {method}", params=params)

        if method in self.handlers:
            try:
                handler = self.handlers[method]
                params = params or {}
                await handler(**params)
                # Explicitly return None
                return None
            except Exception as e:
                logger.exception(f"Error handling MCP request: {method}", error=str(e))
                # Explicitly return None
                return None
        elif target_service:
            try:
                await self.send_request(target_service, method, params)
                # Explicitly return None
                return None
            except Exception as e:
                logger.exception(f"Error forwarding MCP request: {method} to {target_service}", error=str(e))
                # Explicitly return None
                return None
        else:
            logger.warning(f"No handler found for MCP request: {method}")
            # Explicitly return None
            return None

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
            try:
                # Import necessary types
                from mcp.server.tools import Tool

                # Create Tool object firs
                tool = Tool(
                    name=name,
                    fn=function,
                    description=description,
                )

                # Then add it to the server
                self.server.add_tool(tool)
                logger.info(f"Registered tool '{name}' with FastMCP server")
            except Exception as e:
                logger.exception(f"Failed to register tool: {name}", error=str(e))
                # Store as handler as fallback
                self.handlers[name] = function
                logger.debug(f"Stored tool '{name}' as handler due to registration failure")
        else:
            # In client mode or if server not started yet, register as a handler
            self.handlers[name] = function
            logger.debug(f"Stored tool '{name}' as handler for later registration with server")

    async def register_prompt(self, name: str, description: str, function: Callable) -> None:
        """Register a prompt with the MCP server.

        This method is only valid in server mode.

        Args:
            name: The name of the prompt
            description: A description of the prompt
            function: The function to call when the prompt is requested

        Raises:
            RuntimeError: If not in server mode
        """
        if not self.server_mode:
            raise RuntimeError("Cannot register prompt when not in server mode")

        # Ensure server is initialized
        if not self.server:
            # Start the server if it's not already started
            await self.start()

        # Register the prompt with the server - using whatever method is available
        if self.server:
            # Try different registration methods that might be available
            if hasattr(self.server, "register_prompt"):
                getattr(self.server, "register_prompt")(name=name, description=description, function=function)
            elif hasattr(self.server, "register_tool"):
                getattr(self.server, "register_tool")(name=name, description=description, function=function)
            elif hasattr(self.server, "add_prompt"):
                getattr(self.server, "add_prompt")(name=name, description=description, function=function)
            else:
                logger.warning(f"Could not register prompt '{name}': FastMCP has no suitable registration method")
            logger.info(f"Registered prompt: {name}")

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
            try:
                # Import necessary types
                from mcp.server.resources import Resource

                # Create Resource object firs
                resource = Resource(
                    uri=name,
                    fn=function,
                    name=name,
                    description=description,
                    mime_type=mime_type,
                )

                # Then add it to the server
                self.server.add_resource(resource)
                logger.info(f"Registered resource '{name}' with FastMCP server")
            except Exception as e:
                logger.exception(f"Failed to register resource: {name}", error=str(e))
        else:
            # In client mode or if server not started yet, store for later
            logger.debug(f"Client mode or server not started, cannot register resource '{name}' yet")
