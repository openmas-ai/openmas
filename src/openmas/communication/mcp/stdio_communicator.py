"""MCP Communicator using stdio for communication."""

import asyncio
import os
import shutil  # Needed for finding executable
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, cast

import structlog
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
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


class McpStdioCommunicator(BaseCommunicator):
    """MCP communicator that uses stdio for communication (Per-Request Connections).

    This communicator operates in two modes:
    - Client mode: Connects to services over stdio for each request.
    - Server mode: Runs an MCP server that accepts stdio connections.

    In client mode, a stdio subprocess is created for each request to a service.
    The service_urls should specify the command or executable path:
    - "command arg1 arg2 ..." - A shell command to execute
    - "/path/to/executable" - An absolute path to an executable
    - "executable_in_path" - Name of an executable in the system PATH

    In server mode, the MCP server runs in the main process and exposes the agent's
    functionality through the MCP protocol over stdio.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        server_instructions: Optional[str] = None,
        service_args: Optional[Dict[str, List[str]]] = None,  # Args per service
    ) -> None:
        """Initialize the communicator."""
        super().__init__(agent_name, service_urls)
        self.server_mode = server_mode
        self.server_instructions = server_instructions
        self.service_args = service_args or {}
        self.handlers: Dict[str, Callable] = {}
        self.server: Optional[FastMCP] = None
        self._server_task: Optional[asyncio.Task] = None
        # Initialize client state tracking
        self._client_managers: Dict[str, Any] = {}
        self.subprocesses: Dict[str, Any] = {}
        self.clients: Dict[str, Any] = {}
        self.sessions: Dict[str, Any] = {}
        self._is_server_running = False

    def _get_executable_path(self, service_name: str) -> str:
        """Get the full executable path for a service."""
        command_str = self.service_urls.get(service_name)
        if not command_str:
            raise ServiceNotFoundError(f"Service '{service_name}' not found in service_urls")

        # Check if it's an absolute or relative path that exists
        if os.path.exists(command_str):
            if not os.access(command_str, os.X_OK):
                raise CommunicationError(
                    f"Executable path '{command_str}' for service '{service_name}' is not executable"
                )
            return command_str

        # Check if it's in the system PATH
        executable_path = shutil.which(command_str.split()[0])  # Check first part if it's a command string
        if executable_path:
            return executable_path

        raise ServiceNotFoundError(
            f"Could not find executable for service '{service_name}': '{command_str}'", target=service_name
        )

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,  # Ignored for MCP
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a target service using MCP methods via stdio (per-request)."""
        try:
            executable_path = self._get_executable_path(target_service)
        except ServiceNotFoundError as e:
            logger.error(f"Service not found for MCP request: {e}")
            raise
        except CommunicationError as e:
            logger.error(f"Executable check failed for MCP request: {e}")
            raise

        args = self.service_args.get(target_service, [])
        stdio_params = StdioServerParameters(command=executable_path, args=args)
        params = params or {}
        request_timeout = timeout or 30.0

        logger.debug(f"Sending MCP stdio request to {target_service}: method={method}, params={params}")

        try:
            async with stdio_client(stdio_params) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=15.0)

                    # Perform the actual MCP call
                    if method == "tool/list":
                        result = await asyncio.wait_for(session.list_tools(), timeout=request_timeout)
                        return result  # Return raw list of tool objects
                    elif method.startswith("tool/call/"):
                        tool_name = method[10:]
                        mcp_result = await asyncio.wait_for(
                            session.call_tool(tool_name, arguments=params), timeout=request_timeout
                        )
                    elif method == "prompt/list":
                        # Use Any to satisfy type checker for wait_for
                        prompt_list_coro: Any = session.list_prompts()
                        mcp_result = await asyncio.wait_for(prompt_list_coro, timeout=request_timeout)
                        return mcp_result  # Return raw list
                    elif method.startswith("prompt/get/"):
                        prompt_name = method[11:]
                        # Use Any to satisfy type checker for wait_for
                        get_prompt_coro: Any = session.get_prompt(prompt_name, arguments=params)
                        mcp_result = await asyncio.wait_for(get_prompt_coro, timeout=request_timeout)
                        return mcp_result  # Return raw prompt result
                    elif method == "resource/list":
                        # Use Any to satisfy type checker for wait_for
                        res_list_coro: Any = session.list_resources()
                        mcp_result = await asyncio.wait_for(res_list_coro, timeout=request_timeout)
                        return mcp_result  # Return raw list
                    elif method.startswith("resource/read/"):
                        resource_uri = method[14:]
                        uri = cast(AnyUrl, resource_uri)
                        content, mime_type = await asyncio.wait_for(session.read_resource(uri), timeout=request_timeout)
                        return {"content": content, "mime_type": mime_type}
                    else:
                        logger.warning(f"Method '{method}' not recognized, attempting generic tool call.")
                        mcp_result = await asyncio.wait_for(
                            session.call_tool(method, arguments=params), timeout=request_timeout
                        )

                    # Process tool call / generic call result
                    if (
                        HAS_MCP_TYPES
                        and mcp_result
                        and not mcp_result.isError
                        and mcp_result.content
                        and len(mcp_result.content) > 0
                        and hasattr(
                            mcp_result.content[0], "text"
                        )  # Check for text attribute instead of using isinstance
                    ):
                        import json

                        try:
                            return json.loads(mcp_result.content[0].text)
                        except json.JSONDecodeError:
                            return {"raw_content": mcp_result.content[0].text}
                    elif mcp_result and mcp_result.isError:
                        raise CommunicationError(
                            f"MCP stdio call '{method}' failed: {mcp_result.content}", target=target_service
                        )
                    return mcp_result  # Return raw result

        except asyncio.TimeoutError as e:
            logger.error(
                f"Timeout during MCP stdio request to {target_service}", method=method, timeout=request_timeout
            )
            raise CommunicationError(
                f"Timeout during MCP stdio request to service '{target_service}' method '{method}'",
                target=target_service,
            ) from e
        except Exception as e:
            if isinstance(e, CommunicationError):
                raise
            logger.exception(f"Failed MCP stdio request to {target_service}", method=method, error=str(e))
            raise CommunicationError(
                f"Failed MCP stdio request to service '{target_service}' method '{method}': {e}", target=target_service
            ) from e

    async def send_notification(
        self,
        target_service: str,
        method: str,  # For MCP, method is often implicit in notification content
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a notification to a target service via stdio (per-request)."""
        # Note: MCP doesn't have a generic named notification concept like send_request.
        # It uses session.send_notification with specific data structures.
        # This method adapts by sending the params dict as the notification data.
        notification_data = params or {}
        logger.debug(f"Attempting to send MCP notification to {target_service} with data: {notification_data}")

        async def _send_notification() -> None:
            try:
                executable_path = self._get_executable_path(target_service)
            except (ServiceNotFoundError, CommunicationError) as e:
                logger.error(f"Cannot send notification: {e}")
                return

            args = self.service_args.get(target_service, [])
            stdio_params = StdioServerParameters(command=executable_path, args=args)

            try:
                async with stdio_client(stdio_params) as streams:
                    read_stream, write_stream = streams
                    async with ClientSession(read_stream, write_stream) as session:
                        await asyncio.wait_for(session.initialize(), timeout=15.0)
                        # Use a dict for notification data to satisfy expected type
                        if isinstance(notification_data, dict):
                            # Import here to handle different MCP SDK versions
                            try:
                                from mcp.types import ClientNotification

                                # Create the notification object based on the expected ClientNotification API
                                # The "data" parameter issue is caused by version differences in mcp
                                # So we'll use a generic approach that works with type checkers
                                notification = ClientNotification(notification_data)  # type: ignore
                                await asyncio.wait_for(session.send_notification(notification), timeout=10.0)
                            except (ImportError, TypeError):
                                # Fall back to direct dictionary if ClientNotification is not available
                                # This will raise a type error but might work at runtime with some MCP versions
                                await asyncio.wait_for(
                                    session.send_notification(notification_data), timeout=10.0  # type: ignore
                                )
                        else:
                            # Create a ClientNotification object
                            from mcp.types import ClientNotification

                            notification = ClientNotification(data=notification_data)
                            await asyncio.wait_for(session.send_notification(notification), timeout=10.0)
                        logger.info(f"Sent notification to {target_service}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout sending notification to {target_service}")
            except Exception as e:
                logger.exception(f"Error sending notification to {target_service}", error=str(e))

        # Run the notification in the background
        asyncio.create_task(_send_notification())

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self.handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")

    async def _run_server_internal(self) -> None:
        """Internal method to run the FastMCP server logic."""
        # Import here to avoid module-level import issues
        from mcp.server.fastmcp import FastMCP

        try:
            # Create a context for the server (Context usage needs verification)
            # context: Context = Context() # Context is likely not needed here

            # Create the server with the agent name in the instructions
            instructions = self.server_instructions or f"Agent: {self.agent_name}"
            # Correct FastMCP instantiation based on library usage
            server = FastMCP(name=instructions)
            self.server = server
            self._is_server_running = True  # Set flag when server instance created
            logger.info("FastMCP server instance created")

            # Register handlers with the server instance
            # (This needs adjustment if FastMCP doesn't take context directly)
            for method_name, handler_func in self.handlers.items():
                # Register the handler as a tool
                await self._register_tool(method_name, f"Handler for {method_name}", handler_func)

            # Run the server - this blocks until the server is stopped
            logger.info("Starting serve_stdio loop")
            if hasattr(server, "serve_stdio"):
                await server.serve_stdio()  # type: ignore
            else:
                logger.warning("serve_stdio method not found on FastMCP instance, hanging... (DEBUG THIS)")
                await asyncio.Future()  # Hang until cancelled
        except Exception as e:
            logger.exception("Error running MCP stdio server", error=str(e))
        finally:
            logger.info("MCP stdio server coroutine finished/stopped")
            self.server = None
            self._is_server_running = False

    async def start(self) -> None:
        """Start the communicator.

        In client mode, this is a no-op.
        In server mode, this starts the MCP server task.
        """
        if self.server_mode:
            if self._server_task is not None:
                logger.warning("Server task already running.")
                return

            logger.info(f"Starting MCP stdio server task for agent: {self.agent_name}")
            # Start the server logic in a background task
            self._server_task = asyncio.create_task(self._run_server_internal())
            # Note: _is_server_running is set inside _run_server_internal now
            logger.info("MCP stdio server task created")
        else:
            logger.debug("Communicator in client mode, start() is a no-op.")

    async def stop(self) -> None:
        """Stop the communicator.

        In client mode, this closes connections to all services.
        In server mode, this stops the MCP server.
        """
        if self.server_mode:
            # Stop the server task
            if self._server_task:
                logger.info("Stopping MCP stdio server")
                self._server_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(self._server_task), timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                self._server_task = None

            self.server = None
        else:
            # Client mode - close any managed resources
            logger.info("Closing connections to MCP stdio services")

            # Clean up client managers that might exist
            client_managers = getattr(self, "_client_managers", {})
            for service_name, client_manager in list(client_managers.items()):
                try:
                    await client_manager.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing client manager for {service_name}: {e}")

            # Clean up any subprocesses
            subprocesses = getattr(self, "subprocesses", {})
            for service_name, process in list(subprocesses.items()):
                try:
                    if hasattr(process, "terminate"):
                        process.terminate()
                    logger.debug(f"Terminated subprocess for {service_name}")
                except Exception as e:
                    logger.warning(f"Error terminating subprocess for {service_name}: {e}")

            # Clear other possible collections
            if hasattr(self, "clients"):
                self.clients.clear()
            if hasattr(self, "sessions"):
                self.sessions.clear()
            if hasattr(self, "_client_managers"):
                self._client_managers.clear()
            if hasattr(self, "subprocesses"):
                self.subprocesses.clear()

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List available tools from the target service."""
        # MCP session.list_tools() returns Tool objects (or similar)
        raw_tools = await self.send_request(target_service, "tool/list")
        # Convert to basic dict format for compatibility, if needed
        if isinstance(raw_tools, list) and all(hasattr(t, "name") for t in raw_tools):
            return [{"name": t.name, "description": getattr(t, "description", None)} for t in raw_tools]
        logger.warning(f"Unexpected format from list_tools for {target_service}: {raw_tools}")
        return []  # Return empty list or raise error?

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a specific tool on the target service."""
        method = f"tool/call/{tool_name}"
        return await self.send_request(target_service, method, arguments, timeout=timeout)

    async def list_prompts(self, target_service: str) -> List[Dict[str, Any]]:
        """List available prompts from the target service."""
        raw_prompts = await self.send_request(target_service, "prompt/list")
        if isinstance(raw_prompts, list) and all(hasattr(p, "name") for p in raw_prompts):
            return [{"name": p.name, "description": getattr(p, "description", None)} for p in raw_prompts]
        logger.warning(f"Unexpected format from list_prompts for {target_service}: {raw_prompts}")
        return []

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Get a prompt from a service.

        Args:
            target_service: The service to get the prompt from
            prompt_name: The name of the prompt to get
            arguments: The arguments to pass to the prompt
            timeout: Optional timeout in seconds

        Returns:
            The result of the prompt

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        arguments = arguments or {}
        response = await self.send_request(
            target_service=target_service,
            method=f"prompt/get/{prompt_name}",
            params=arguments,
            timeout=timeout,
        )
        return response

    async def list_resources(self, target_service: str) -> List[Dict[str, Any]]:
        """List available resources from the target service."""
        raw_resources = await self.send_request(target_service, "resource/list")
        if isinstance(raw_resources, list) and all(hasattr(r, "name") for r in raw_resources):
            return [{"name": r.name, "description": getattr(r, "description", None)} for r in raw_resources]
        logger.warning(f"Unexpected format from list_resources for {target_service}: {raw_resources}")
        return []

    async def read_resource(
        self,
        target_service: str,
        resource_uri: str,
        timeout: Optional[float] = None,
    ) -> Any:
        """Read a resource from a service.

        Args:
            target_service: The service to read the resource from
            resource_uri: The URI of the resource to read
            timeout: Optional timeout in seconds

        Returns:
            The content of the resource, either as a dict with mime_type and content,
            or as raw bytes or string

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.send_request(
            target_service=target_service,
            method="resource/read",
            params={"uri": resource_uri},
            timeout=timeout,
        )
        return response

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
            target_service: The service to call
            messages: The messages to sample from
            system_prompt: Optional system prompt to use
            temperature: Optional temperature for sampling
            max_tokens: Optional maximum tokens to generate
            include_context: Optional context to include (not used in all providers)
            model_preferences: Optional model preferences (provider-specific)
            stop_sequences: Optional stop sequences for text generation
            timeout: Optional timeout in seconds

        Returns:
            The sampled prompt result
        """
        # Make sure the executable exists
        executable_path = self._get_executable_path(target_service)
        args = self.service_args.get(target_service, [])
        stdio_params = StdioServerParameters(command=executable_path, args=args)

        request_timeout = timeout or 60.0  # Default timeout of 60 seconds

        # Convert messages format if needed
        mcp_formatted_messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Convert to TextContent if types are available and content is string
            if HAS_MCP_TYPES and isinstance(content, str):
                try:
                    from mcp.types import TextContent

                    mcp_content: Any = TextContent(type="text", text=content)
                except (ImportError, TypeError):
                    mcp_content = content
            else:
                mcp_content = content

            mcp_formatted_messages.append({"role": role, "content": mcp_content})

        try:
            async with stdio_client(stdio_params) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=15.0)

                    # Create sample parameters
                    sample_params: Dict[str, Any] = {
                        "messages": mcp_formatted_messages,
                    }
                    if system_prompt:
                        sample_params["system"] = system_prompt
                    if temperature:
                        sample_params["temperature"] = temperature
                    if max_tokens:
                        sample_params["max_tokens"] = max_tokens
                    if model_preferences:
                        sample_params["model_preferences"] = model_preferences
                    if stop_sequences:
                        sample_params["stop_sequences"] = stop_sequences

                    # Call the sample function directly (not through wait_for due to type issues)
                    try:
                        # Handle through call_tool workaround if sample not available
                        if not hasattr(session, "sample"):
                            result = await asyncio.wait_for(
                                session.call_tool("sample", arguments=sample_params), timeout=request_timeout
                            )
                            return {"content": result}

                        # Otherwise use normal sample method
                        # Use Any to avoid mypy issues with session.sample
                        sample_method: Any = session.sample
                        result = await asyncio.wait_for(sample_method(**sample_params), timeout=request_timeout)

                        # Extract response content
                        if result and result.content:
                            # Try to extract text content
                            if HAS_MCP_TYPES:
                                from mcp.types import TextContent

                                text_content = ""
                                for item in result.content:
                                    if isinstance(item, TextContent):
                                        text_content += item.text
                                    elif hasattr(item, "text"):
                                        text_content += item.text
                                    elif isinstance(item, str):
                                        text_content += item
                                return {"content": text_content}
                            else:
                                # Fallback for string content
                                return {"content": str(result.content)}
                        else:
                            return {"content": "No content in result"}

                    except AttributeError:
                        logger.warning("Session does not have a sample method, falling back")
                        # Fall back to the call_tool method
                        result = await asyncio.wait_for(
                            session.call_tool("sample", arguments=sample_params), timeout=request_timeout
                        )
                        return {"content": result}

        except Exception as e:
            logger.exception(f"Error sampling from {target_service}: {e}")
            raise CommunicationError(f"Error sampling from {target_service}: {e}", target=target_service) from e

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


# Register the communicator
register_communicator("mcp_stdio", McpStdioCommunicator)
