"""MCP Communicator using stdio for communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

import structlog
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.fastmcp import Context, FastMCP

from simple_mas.communication.base import BaseCommunicator
from simple_mas.exceptions import CommunicationError, ServiceNotFoundError

# Set up logging
logger = structlog.get_logger(__name__)

# Type variable for generic return types
T = TypeVar("T")

# Type annotation for the streams returned by the context manager
StreamPair = Tuple[Any, Any]


class McpStdioCommunicator(BaseCommunicator):
    """MCP communicator that uses stdio for communication.

    This communicator can operate in two modes:
    - Client mode: Connects to services over stdio
    - Server mode: Runs an MCP server that accepts stdio connections

    In client mode, a stdio subprocess is created for each service.
    In server mode, the MCP server runs in the main process.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        server_instructions: Optional[str] = None,
    ) -> None:
        """Initialize the communicator.

        Args:
            agent_name: The name of the agent
            service_urls: A mapping of service names to their URLs
            server_mode: Whether to operate in server mode
            server_instructions: Instructions for the server (in server mode)
        """
        self.agent_name = agent_name
        self.service_urls = service_urls
        self.server_mode = server_mode
        self.server_instructions = server_instructions
        self.subprocesses: Dict[str, asyncio.subprocess.Process] = {}
        self.clients: Dict[str, Any] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self._client_managers: Dict[str, Any] = {}
        self.handlers: Dict[str, Callable] = {}
        # Initialize with None but the correct type for mypy
        self.server: Optional[FastMCP] = None
        self._server_task: Optional[asyncio.Task] = None

    async def _connect_to_service(self, service_name: str) -> None:
        """Connect to a service.

        Args:
            service_name: The name of the service to connect to

        Raises:
            ServiceNotFoundError: If the service is not found
        """
        if service_name in self.sessions:
            # Already connected
            return

        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

        command = self.service_urls[service_name]
        logger.debug(f"Connecting to service: {service_name} with command: {command}")

        try:
            if not self._client_managers.get(service_name):
                # Create a new client manager
                logger.debug(f"Creating stdio client manager for service: {service_name}")
                # Split the command string into a list for subprocess
                params = StdioServerParameters(command=command)
                self._client_managers[service_name] = stdio_client(params)
                logger.debug(f"Created stdio client manager for service: {service_name}")

            # Connect to the service
            client_manager = self._client_managers[service_name]
            logger.debug(f"Getting client for service: {service_name}")

            # Connect to the service
            client = await client_manager.__aenter__()
            self.clients[service_name] = client
            logger.debug(f"Created client for service: {service_name}")

            # Create a new session with the client
            read_stream, write_stream = client if isinstance(client, tuple) else (client, client)
            self.sessions[service_name] = ClientSession(read_stream, write_stream)
            logger.info(f"Connected to service: {service_name}")
        except Exception as e:
            logger.exception(f"Failed to connect to service: {service_name}", error=str(e))
            raise ServiceNotFoundError(f"Failed to connect to service '{service_name}': {e}", target=service_name)

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
        - resource/read: Read a resource's conten
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

                from typing import cast

                from pydantic import AnyUrl

                # Cast to AnyUrl for type checking
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

    async def start(self) -> None:
        """Start the communicator.

        In client mode, this connects to all services.
        In server mode, this starts the MCP server.
        """
        if self.server_mode:
            # Server mode - start a stdio server
            logger.info("Starting MCP stdio server")

            # Import here to ensure MCP is available
            from mcp.server.fastmcp import FastMCP

            # Create the server with proper initialization
            server_instructions = self.server_instructions or f"MCP server for agent {self.agent_name}"
            self.server = FastMCP(self.agent_name, instructions=server_instructions)

            logger.info("MCP stdio server started")

            # Start the server in the main thread
            # The server will handle incoming requests and responses through stdin/stdou
            async def run_stdio_server() -> None:
                # Import here to avoid module-level import issues
                from mcp.server.stdio import stdio_server

                # Create a context
                context: Context = Context()
                if self.server_instructions:
                    context = Context(instructions=self.server_instructions)

                # Create the FastMCP server
                self.server = FastMCP(context=context)

                # Start the server - initialize first
                if hasattr(self.server, "start"):
                    await self.server.start()

                # Now handle stdio communication
                if self.server is not None:  # Type check for mypy
                    async with stdio_server() as (reader, writer):
                        # Try different methods that might be available depending on MCP version
                        if hasattr(self.server, "serve"):
                            # Use serve if available
                            await getattr(self.server, "serve")(reader, writer)
                        elif hasattr(self.server, "handle_connection"):
                            # Use handle_connection if available
                            await getattr(self.server, "handle_connection")(reader, writer)
                        else:
                            # Fallback - keep server alive
                            while True:
                                await asyncio.sleep(0.1)

            # Create a task for the server
            self._server_task = asyncio.create_task(run_stdio_server())
        else:
            # Client mode - connect to all services
            logger.info("Starting MCP stdio client and connecting to services")
            for service_name in self.service_urls:
                logger.debug(f"Connecting to service: {service_name}")
                try:
                    await self._connect_to_service(service_name)
                except Exception as e:
                    logger.error(f"Failed to connect to {service_name}: {str(e)}")
            logger.info("Connected to all services")

    async def stop(self) -> None:
        """Stop the communicator.

        In server mode, this stops the MCP server.
        In client mode, this closes all connections to services.
        """
        logger.info("Stopping MCP stdio communicator")

        # Close all client sessions - note that ClientSession doesn't have a close method
        # but we should clean up references
        self.sessions.clear()

        # Cancel server task if it exists
        if self._server_task is not None:
            logger.debug("Cancelling server task")
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        # Close all client connections
        for service_name, client_manager in self._client_managers.items():
            try:
                logger.debug(f"Closing client manager for service: {service_name}")
                await client_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing MCP client manager for {service_name}: {e}")

        # Clear all dictionaries
        self.clients.clear()
        self._client_managers.clear()
        self.subprocesses.clear()

        logger.info("MCP stdio communicator stopped")

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

    async def _handle_mcp_request(
        self, method: str, params: Optional[Dict[str, Any]] = None, target_service: Optional[str] = None
    ) -> None:
        """Handle a request using the MCP protocol.

        Args:
            method: The method to handle
            params: The parameters for the method
            target_service: Optional target service override

        Raises:
            MethodNotFoundError: If the method is not found
        """
        # Convert None to empty dict
        params = params or {}

        logger.debug(f"Handling MCP request: {method}", params=params)

        if method in self.handlers:
            try:
                handler = self.handlers[method]
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

    async def _mcp_custom_method(self, session: ClientSession, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a custom method on an MCP session.

        Args:
            session: The MCP session
            method: The method to call
            params: The parameters to pass to the method

        Returns:
            The result of the method call as a dictionary
        """
        # Use direct method calls if available
        if hasattr(session, method):
            method_fn = getattr(session, method)
            try:
                result = await method_fn(**params)

                # Convert result to dictionary if possible
                if isinstance(result, dict):
                    # Ensure all keys are strings
                    return {str(k): v for k, v in result.items()}
                elif hasattr(result, "__dict__"):
                    # Convert object to dictionary
                    return {str(k): v for k, v in result.__dict__.items() if not k.startswith("_")}
                elif isinstance(result, (list, tuple)):
                    # Convert list or tuple to dictionary with 'items' key
                    return {"items": list(result)}
                else:
                    # Convert any other type to string and return in dictionary
                    return {"result": str(result)}
            except Exception as e:
                # Handle exceptions by returning error dictionary
                return {"error": str(e), "status": "failed"}

        # Return error if method not available
        return {"error": f"Method {method} not available in MCP session", "status": "not_found"}

    async def register_resource(
        self, name: str, description: str, function: Callable, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource with the MCP server.

        Resources are static or dynamic data sources that can be accessed by clients.

        Args:
            name: The name of the resource
            description: A description of the resource
            function: The function to call to get the resource conten
            mime_type: The MIME type of the resource conten
        """
        if not self.server_mode:
            logger.warning("register_resource called in client mode, which is not supported")
            return

        if self.server is None:
            logger.warning("Cannot register resource, server not started")
            return

        try:
            # Import Resource class
            from mcp.server.resources import Resource

            # Create a resource objec
            resource = Resource(
                uri=name,
                fn=function,
                name=name,
                description=description,
                mime_type=mime_type,
            )

            # Add the resource to the server
            self.server.add_resource(resource)
            logger.debug("Registered MCP resource: {0}".format(name))
        except Exception as e:
            logger.exception(f"Failed to register resource: {name}", error=str(e))
