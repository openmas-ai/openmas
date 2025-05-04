"""MCP Communicator using SSE for communication."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, cast

import structlog
import uvicorn

# Conditionally import server-side components
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from mcp.server.fastmcp import FastMCP
    from mcp.server.sse import SseServerTransport
    from starlette.routing import Mount  # type: ignore  # Missing stubs for starlette.routing

    HAS_SERVER_DEPS = True
except ImportError:
    HAS_SERVER_DEPS = False
    FastAPI = None  # type: ignore
    Request = None  # type: ignore
    FastMCP = None  # type: ignore
    SseServerTransport = None  # type: ignore
    JSONResponse = None  # type: ignore
    Mount = None  # type: ignore

# Import client-side components
from mcp.client import sse
from mcp.client.session import ClientSession

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

    Handles both client and server modes using the mcp library (v1.6+ patterns).
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        http_port: int = 8000,
        http_host: str = "0.0.0.0",
        server_instructions: Optional[str] = None,
    ) -> None:
        """Initialize the MCP SSE communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to SSE endpoint URLs
            server_mode: Whether to run as a server
            http_port: Port to use when in server mode
            http_host: Host to bind to when in server mode
            server_instructions: Optional instructions for the server
        """
        super().__init__(agent_name, service_urls)
        self.server_mode = server_mode
        self.http_port = http_port
        self.http_host = http_host
        self.server_instructions = server_instructions or f"Agent: {agent_name}"

        # Initialize server components
        self.app: Optional[FastAPI] = None
        self.server: Optional[FastMCP] = None
        self._server_task: Optional[asyncio.Task] = None
        self._background_tasks: Set[asyncio.Task] = set()

        # Initialize client tracking
        self.clients: Dict[str, Any] = {}
        self.sessions: Dict[str, Any] = {}

        # Initialize tool registry
        self.tool_registry: Dict[str, Dict[str, Any]] = {}

        # Logger for this communicator
        self.logger = structlog.get_logger(__name__)

        # Client-side state is now managed per-request

        # Server-side attributes (only used if server_mode is True)
        self.handlers: Dict[str, Callable] = {}
        self.sse_transport: Optional[SseServerTransport] = None
        self.uvicorn_server: Optional[uvicorn.Server] = None
        self._server_ready_event = asyncio.Event()

        if self.server_mode and not HAS_SERVER_DEPS:
            raise ImportError("MCP server dependencies (fastapi, mcp[server]) are required for server mode.")

    # --- Client Mode Methods ---

    def _get_service_url(self, service_name: str) -> str:
        """Validate service name and return the corresponding SSE endpoint URL."""
        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found in service URLs", target=service_name)

        service_url = self.service_urls[service_name]
        # Ensure the URL targets the /sse endpoint expected by sse_client
        if not service_url.endswith("/sse"):
            if service_url.endswith("/"):
                service_url += "sse"
            else:
                service_url += "/sse"
        return service_url

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,  # response_model not used by MCP, kept for compatibility
        timeout: Optional[float] = None,  # timeout handled by asyncio.wait_for where needed
    ) -> Any:
        """Send a request to a target service using MCP methods.

        Establishes a connection, initializes a session, sends the request,
        and cleans up the connection for each call.
        """
        service_url = self._get_service_url(target_service)
        params = params or {}
        request_timeout = timeout or 30.0  # Default timeout for requests

        logger.debug(f"Sending MCP request to {target_service}: method={method}, params={params}")

        try:
            # Establish connection and session per request
            async with sse.sse_client(service_url) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the session
                    logger.debug(f"Initializing MCP session for {target_service} request...")
                    await asyncio.wait_for(session.initialize(), timeout=15.0)  # Use a dedicated init timeout
                    logger.debug(f"MCP session for {target_service} request initialized.")

                    # Perform the actual MCP call within the session context
                    if method == "tool/list":
                        tools = await asyncio.wait_for(session.list_tools(), timeout=request_timeout)
                        # Return the raw list of tool objects/structs from the session
                        return tools
                    elif method.startswith("tool/call/"):
                        tool_name = method[10:]
                        result = await asyncio.wait_for(
                            session.call_tool(tool_name, arguments=params), timeout=request_timeout
                        )
                        # Process result
                        if (
                            HAS_MCP_TYPES
                            and result
                            and not result.isError
                            and result.content
                            and isinstance(result.content[0], TextContent)
                        ):
                            import json

                            try:
                                # Attempt to parse the text content as JSON
                                return json.loads(result.content[0].text)
                            except json.JSONDecodeError:
                                # Return raw text if not JSON
                                return {"raw_content": result.content[0].text}
                        elif result and result.isError:
                            raise CommunicationError(
                                f"Tool call '{tool_name}' failed: {result.content}", target=target_service
                            )
                        # Return raw result object if not parsed or not an error
                        return result
                    elif method == "prompt/list":
                        prompts = await asyncio.wait_for(session.list_prompts(), timeout=request_timeout)
                        return [
                            {"name": getattr(p, "name", "unknown"), "description": getattr(p, "description", "")}
                            for p in prompts
                        ]
                    elif method.startswith("prompt/get/"):
                        prompt_name = method[11:]
                        # Use Any to avoid incompatible type for wait_for
                        get_prompt_coro: Any = session.get_prompt(prompt_name, arguments=params)
                        result = await asyncio.wait_for(get_prompt_coro, timeout=request_timeout)
                        return result
                    elif method == "resource/list":
                        resources = await asyncio.wait_for(session.list_resources(), timeout=request_timeout)
                        return [
                            {"name": getattr(r, "name", "unknown"), "description": getattr(r, "description", "")}
                            for r in resources
                        ]
                    elif method.startswith("resource/read/"):
                        resource_uri = method[14:]
                        uri = cast(AnyUrl, resource_uri)
                        content, mime_type = await asyncio.wait_for(session.read_resource(uri), timeout=request_timeout)
                        return {"content": content, "mime_type": mime_type}
                    else:
                        logger.warning(f"Method '{method}' not recognized, attempting generic tool call.")
                        result = await asyncio.wait_for(
                            session.call_tool(method, arguments=params), timeout=request_timeout
                        )
                        # Process result similarly to tool/call
                        if (
                            HAS_MCP_TYPES
                            and result
                            and not result.isError
                            and result.content
                            and isinstance(result.content[0], TextContent)
                        ):
                            import json

                            try:
                                return json.loads(result.content[0].text)
                            except json.JSONDecodeError:
                                return {"raw_content": result.content[0].text}
                        elif result and result.isError:
                            raise CommunicationError(
                                f"Tool call '{method}' failed: {result.content}", target=target_service
                            )
                        return result

        except asyncio.TimeoutError as e:
            # Check if timeout occurred during initialize() or the actual call
            # This distinction might be harder now, log generic timeout
            logger.error(f"Timeout during MCP request to {target_service}", method=method, timeout=request_timeout)
            raise CommunicationError(
                f"Timeout during MCP request to service '{target_service}' method '{method}'", target=target_service
            ) from e
        except Exception as e:
            # Catch potential ClosedResourceError if session closed unexpectedly
            if isinstance(e, CommunicationError):  # Don't wrap existing CommunicationErrors
                raise
            logger.exception(f"Failed MCP request to {target_service}", method=method, error=str(e))
            raise CommunicationError(
                f"Failed MCP request to service '{target_service}' method '{method}': {e}",
                target=target_service,
            ) from e

    async def send_notification(
        self, target_service: str, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification (fire-and-forget tool call) to a target service."""
        service_url = self._get_service_url(target_service)
        params = params or {}

        async def _fire_and_forget_task() -> None:
            """Task to establish connection and send the tool call."""
            try:
                async with sse.sse_client(service_url) as streams:
                    read_stream, write_stream = streams
                    async with ClientSession(read_stream, write_stream) as session:
                        # Initialize first
                        await asyncio.wait_for(session.initialize(), timeout=15.0)
                        # Send the tool call (use short timeout for the call itself)
                        await asyncio.wait_for(session.call_tool(method, arguments=params), timeout=5.0)
                        logger.debug("Sent notification (tool call) successfully", target=target_service, method=method)
            except asyncio.TimeoutError as e:
                # Distinguish between init timeout and call timeout if possible/needed
                logger.debug(f"Notification task timed out ({type(e).__name__}) for {target_service}/{method}")
            except Exception as e:
                logger.warning(
                    f"Failed to send notification (tool call) for {target_service}/{method}",
                    target_service=target_service,
                    method=method,
                    error=str(e),
                )

        # Run the connection and send logic in the background
        asyncio.create_task(_fire_and_forget_task())

    # --- Server Mode Methods ---

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler function for a specific method (tool name)."""
        if not self.server_mode:
            logger.warning("Cannot register handler in client mode.")
            return
        if not HAS_SERVER_DEPS:
            logger.error("Cannot register handler, server dependencies missing.")
            return

        self.handlers[method] = handler
        logger.debug(f"Handler registered for method/tool: {method}")

        # If server is already running, dynamically register the tool
        if self.server and self.server._mcp_server:
            await self._register_tool_with_server(method, f"Handler for {method}", handler)

    async def _register_tool_with_server(self, name: str, description: str, function: Callable) -> None:
        """Helper to register a tool with the running FastMCP server instance."""
        if not self.server or not self.server._mcp_server:
            logger.warning("Cannot register tool, server instance not available.")
            return

        try:
            # Use the @server.tool() decorator approach conceptually
            # Since we can't re-decorate, we manually add to the server's internal registry
            # Note: This relies on internal structure and might break with MCP updates
            if hasattr(self.server._mcp_server, "add_tool"):
                # Directly add if a simple add_tool exists (less likely for FastMCP)
                # self.server._mcp_server.add_tool(name=name, description=description, fn=function) # Check exact API
                # Or more likely, modify the internal tools dictionary

                # Create a simple dict-based tool instance, avoiding direct Tool import
                tool_instance = {"name": name, "description": description, "function": function}

                # Safely access/modify _tools dictionary if it exists
                if hasattr(self.server._mcp_server, "_tools"):
                    tools_dict = getattr(self.server._mcp_server, "_tools", {})
                    tools_dict[name] = tool_instance
                    logger.info(f"Dynamically registered tool with running server: {name}")
                else:
                    logger.warning(f"Could not dynamically register tool '{name}'. No _tools attribute found.")
            else:
                logger.warning(f"Could not dynamically register tool '{name}'. Server object structure unexpected.")

        except Exception as e:
            logger.error(f"Failed to dynamically register tool '{name}' with running server", error=str(e))

    async def start(self) -> None:
        """Start the communicator. In server mode, starts the MCP SSE server."""
        if not self.server_mode:
            logger.debug("Communicator in client mode, start() is a no-op.")
            return

        if self._server_task and not self._server_task.done():
            logger.warning("Server task already running.")
            return

        if not HAS_SERVER_DEPS:
            logger.error("Cannot start server, dependencies (fastapi, mcp[server]) missing.")
            raise ImportError("MCP server dependencies missing.")

        logger.info(f"Starting MCP SSE server for agent {self.agent_name} on port {self.http_port}")
        self._server_ready_event.clear()
        self.uvicorn_server = None  # Ensure clean state

        # Define the task to run the Uvicorn server
        async def run_uvicorn_server_task() -> None:
            self.app = FastAPI(title=f"{self.agent_name} MCP Server", version="1.0")  # Create app instance here
            try:
                # 1. Create FastMCP instance
                self.server = FastMCP(
                    name=self.agent_name,
                    instructions=self.server_instructions or f"Agent {self.agent_name}",
                    log_level="DEBUG",  # Use DEBUG for detailed MCP logs
                )
                logger.info("FastMCP server instance created.")

                # 2. Create SSE Transport instance
                self.sse_transport = SseServerTransport("/messages/")  # Path for client POSTs
                logger.info("SseServerTransport instance created.")

                # 3. Mount the POST handler for incoming client messages to FastAPI app
                # CRITICAL: Allows server to receive messages via POST /messages/
                self.app.router.routes.append(Mount("/messages", app=self.sse_transport.handle_post_message))
                logger.info("Mounted SseServerTransport POST handler at /messages.")

                # 4. Define the main /sse GET endpoint for establishing connections
                @self.app.get("/sse", tags=["MCP"])  # type: ignore
                async def handle_sse_connection(request: Request) -> Any:
                    """Handles incoming SSE connection requests and runs the MCP protocol loop."""
                    client_id = request.client.host if request.client else "unknown"
                    logger.info(f"Incoming SSE connection request from {client_id}")

                    if not self.sse_transport or not self.server or not self.server._mcp_server:
                        logger.error("Server or transport not initialized during SSE request.")
                        return JSONResponse(status_code=503, content={"error": "Server components not ready"})

                    try:
                        # sse_transport.connect_sse handles handshake & provides streams
                        async with self.sse_transport.connect_sse(request.scope, request.receive, request._send) as (
                            read_stream,
                            write_stream,
                        ):
                            logger.info(f"SSE connection established for {client_id}, entering MCP server run loop...")
                            try:
                                # Run the FastMCP server logic for this connection
                                await self.server._mcp_server.run(
                                    read_stream,
                                    write_stream,
                                    self.server._mcp_server.create_initialization_options(),
                                )
                                logger.info(f"MCP server run loop finished NORMALLY for {client_id}.")
                            except asyncio.CancelledError:
                                logger.warning(f"MCP server run loop CANCELLED for {client_id}.")
                                raise
                            except Exception:
                                logger.exception(f"MCP server run loop ERRORED for {client_id}")
                                raise  # Re-raise to allow higher level handling if needed
                            finally:
                                logger.debug(f"Exiting 'async with connect_sse' block for {client_id}")
                    except asyncio.CancelledError:
                        logger.warning(f"handle_sse_connection task CANCELLED for {client_id}")
                        raise
                    except Exception:
                        logger.error(f"Error during SSE handling for {client_id}", exc_info=True)
                        # Avoid returning JSONResponse if headers already sent
                        # Consider specific exception types if needed

                logger.info("Defined /sse GET endpoint handler.")

                # 5. Register pre-defined handlers as tools on the FastMCP instance
                for method_name, handler_func in self.handlers.items():
                    # Use the @server.tool() decorator mechanism
                    self.server.tool(name=method_name, description=f"Handler for {method_name}")(handler_func)
                logger.info(f"Registered {len(self.handlers)} pre-existing handlers as tools.")

                # Optional: Add a root endpoint for basic health check
                @self.app.get("/", tags=["General"], include_in_schema=False)  # type: ignore
                async def read_root() -> JSONResponse:
                    return JSONResponse({"status": "running", "agent": self.agent_name})

                # 6. Configure and run Uvicorn
                config = uvicorn.Config(
                    app=self.app,  # Pass the configured FastAPI app
                    host="0.0.0.0",  # Listen on all interfaces
                    port=self.http_port,
                    log_level="info",  # Uvicorn's logging level
                    lifespan="on",  # Important for startup/shutdown events
                )
                uvicorn_server = uvicorn.Server(config)
                self.uvicorn_server = uvicorn_server

                # Hook Uvicorn's startup to set our ready event
                original_startup = uvicorn_server.startup

                async def tracked_startup(*args: Any, **kwargs: Any) -> None:
                    await original_startup(*args, **kwargs)
                    logger.info("Uvicorn startup sequence complete, signaling readiness.")
                    self._server_ready_event.set()

                setattr(uvicorn_server, "startup", tracked_startup)

                logger.info("Starting Uvicorn server...")
                await uvicorn_server.serve()
                logger.info("Uvicorn server has stopped.")

            except ImportError as import_err:
                logger.critical(f"ImportError preventing server start: {import_err}", exc_info=True)
                # Signal failure immediately
                self._server_ready_event.set()  # Set event anyway to unblock waiter
            except Exception as setup_err:
                # Ensure exception variable 'e' is used
                logger.exception(
                    f"Error setting up or running MCP SSE server ({type(setup_err).__name__}): {setup_err}",
                    error=str(setup_err),
                )
                # Signal failure immediately
                self._server_ready_event.set()  # Set event anyway to unblock waiter
            finally:
                logger.info("MCP SSE server task run_uvicorn_server_task finishing.")
                # Ensure state is cleaned up even if serve() fails
                self.server = None
                self.uvicorn_server = None
                self.sse_transport = None
                if not self._server_ready_event.is_set():
                    logger.warning("Server task finished without signaling ready (likely error).")
                    self._server_ready_event.set()  # Unblock waiter if startup failed before signaling

        # Start the server task
        self._server_task = asyncio.create_task(run_uvicorn_server_task())

        # Wait for the server to signal readiness
        try:
            logger.info("Waiting for MCP SSE server readiness signal...")
            await asyncio.wait_for(self._server_ready_event.wait(), timeout=20.0)  # Increased timeout slightly

            # Double-check if the server actually started or if the event was set due to an error
            if self._server_task and self._server_task.done():
                exc = self._server_task.exception()
                if exc:
                    logger.error(f"Server task finished prematurely with exception: {exc}")
                    raise CommunicationError(f"MCP SSE server task failed on startup: {exc}") from exc

            if self.uvicorn_server is None or not self.uvicorn_server.started:
                logger.error("Server readiness signaled, but Uvicorn server not marked as started.")
                raise CommunicationError("MCP SSE server failed to start correctly.")

            logger.info(f"MCP SSE server started and appears ready on port {self.http_port}")

        except asyncio.TimeoutError:
            logger.error("Timeout waiting for MCP SSE server startup signal.")
            if self._server_task and not self._server_task.done():
                self._server_task.cancel()
            raise CommunicationError("MCP SSE server failed to start within timeout.")
        except Exception as e:
            # Catch other potential errors during startup wait
            logger.exception("Error occurred while waiting for server startup", error=str(e))
            if self._server_task and not self._server_task.done():
                self._server_task.cancel()
            raise CommunicationError(f"Error waiting for server startup: {e}") from e

    async def stop(self) -> None:
        """Stop the communicator.

        In client mode, this closes connections by exiting stored context managers.
        In server mode, this stops the MCP server task.
        """
        if self.server_mode:
            # --- Stop Server Task ---
            if self._server_task and not self._server_task.done():
                logger.info("Stopping MCP SSE server task...")
                if self.uvicorn_server and self.uvicorn_server.started:
                    logger.info("Attempting graceful shutdown of Uvicorn server...")
                    self.uvicorn_server.should_exit = True
                    # Give Uvicorn time to shut down gracefully
                    try:
                        await asyncio.wait_for(self._server_task, timeout=10.0)
                        logger.info("Uvicorn server shut down gracefully.")
                    except asyncio.TimeoutError:
                        logger.warning("Uvicorn graceful shutdown timed out, cancelling server task.")
                        self._server_task.cancel()
                    except asyncio.CancelledError:
                        logger.info("Server task was already cancelled during shutdown wait.")
                    except Exception as e:
                        logger.error(f"Error during graceful Uvicorn shutdown: {e}, cancelling task.", exc_info=True)
                        self._server_task.cancel()
                else:
                    # If Uvicorn wasn't running or instance lost, just cancel the task
                    logger.warning("Uvicorn server not running or instance missing, cancelling task directly.")
                    self._server_task.cancel()

                # Ensure task is awaited after cancellation/shutdown attempt
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    logger.info("Server task successfully cancelled.")
                except Exception as e:
                    logger.error(f"Error awaiting server task completion after stop: {e}", exc_info=True)

            # Reset server state
            self._server_task = None
            self.uvicorn_server = None
            self.server = None
            self.sse_transport = None
            self.handlers.clear()  # Clear handlers associated with this server instance
            self._server_ready_event.clear()
            logger.info("MCP SSE Server stopped and state reset.")

        else:
            # Client mode: stop() is a no-op as connections are per-request
            logger.debug("Stopping communicator in client mode (no persistent connections to close).")

    # --- Helper Methods ---

    def _convert_messages_to_mcp(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert standard message format to MCP SDK format (using TextContent if available)."""
        mcp_messages = []
        for msg in messages:
            role = msg["role"]
            content_data = msg["content"]

            # Create TextContent if types are available and content is string
            if HAS_MCP_TYPES and isinstance(content_data, str):
                mcp_content = TextContent(type="text", text=content_data)
            elif HAS_MCP_TYPES and isinstance(content_data, TextContent):
                mcp_content = content_data  # Pass through if already TextContent
            else:
                # Either types are not available or content is not a string/TextContent
                # Just use the raw content directly
                mcp_content = content_data
                logger.warning(
                    "Passing non-string/TextContent message content directly to MCP sample",
                    content_type=type(content_data),
                )

            mcp_messages.append({"role": role, "content": mcp_content})
        return mcp_messages

    # --- Methods common to client/server or just passthrough ---

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List tools available in a target service."""
        result = await self.send_request(target_service, "tool/list")
        if isinstance(result, list):
            return result
        return []

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
        """Sample a prompt from a target service."""
        client_id = target_service
        if client_id not in self.clients:
            raise ServiceNotFoundError(f"Service '{client_id}' not found")

        # Create a version of messages that uses TextContent if available
        mcp_messages = self._convert_messages_to_mcp(messages)

        # Create sample parameters
        sample_params: Dict[str, Any] = {
            "messages": mcp_messages,
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

        request_timeout = timeout or 60.0

        try:
            # Use the client session
            session = self.sessions[client_id]

            # Check if the session has a sample method, otherwise fall back to call_tool
            if not hasattr(session, "sample"):
                result = await asyncio.wait_for(
                    session.call_tool("sample", arguments=sample_params), timeout=request_timeout
                )
                return {"content": result}

            # Use Any type to handle mypy issues with session.sample
            sample_method: Any = session.sample
            result = await asyncio.wait_for(sample_method(**sample_params), timeout=request_timeout)

            # Process result (assuming simple text content for now)
            if result and not result.isError and result.content:
                # Process different content types properly
                processed_content = ""
                for content in result.content:
                    # Avoid isinstance check with TextContent directly
                    if hasattr(content, "text") and hasattr(content, "type"):
                        processed_content += content.text
                    elif hasattr(content, "text"):
                        processed_content += content.text
                    elif isinstance(content, str):
                        processed_content += content
                return {"content": processed_content}
            elif result and result.isError:
                logger.error(f"MCP sampling failed for {target_service}: {result.content}")
                raise CommunicationError(f"MCP sampling failed: {result.content}", target=target_service)
            else:
                logger.warning(f"MCP sampling returned unexpected result: {result}")
                return {"content": None}  # Or raise an error

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout during MCP sampling for {target_service}", timeout=request_timeout)
            raise CommunicationError(f"Timeout during MCP sampling ({target_service})", target=target_service) from e
        except Exception as e:
            # Revert: Always wrap generic exceptions
            # if isinstance(e, CommunicationError): raise # Avoid double wrapping
            logger.exception(f"Error during MCP sampling for {target_service}", error=str(e))
            raise CommunicationError(f"Error during MCP sampling ({target_service}): {e}", target=target_service) from e

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a service."""
        if not tool_name:
            raise ValueError("Tool name cannot be empty")
        arguments = arguments or {}
        # Directly call send_request which handles connection and uses the correct MCP method pattern
        return await self.send_request(target_service, f"tool/call/{tool_name}", arguments, timeout=timeout)

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Get a prompt from a target service."""
        if not prompt_name:
            raise ValueError("Prompt name cannot be empty")
        arguments = arguments or {}
        # Directly call send_request which handles connection and uses the correct MCP method pattern
        return await self.send_request(target_service, f"prompt/get/{prompt_name}", arguments, timeout=timeout)

    async def _register_tools_with_server(self) -> None:
        """Register tools with the FastMCP server."""
        if not self.tool_registry:
            return

        try:
            for tool_name, tool_info in self.tool_registry.items():
                tool_function = tool_info["function"]
                tool_description = tool_info["description"]

                try:
                    if self.server is not None and hasattr(self.server, "register_tool"):
                        await self.server.register_tool(
                            name=tool_name,
                            description=tool_description,
                            fn=tool_function,
                        )
                    elif self.server is not None and hasattr(self.server, "add_tool"):
                        self.server.add_tool(
                            name=tool_name,
                            description=tool_description,
                            fn=tool_function,
                        )
                    else:
                        self.logger.warning(f"Cannot register tool {tool_name}: No suitable registration method found")
                except Exception as e:
                    self.logger.error(f"Failed to register tool {tool_name}: {e}")
                    # Continue registering other tools
        except Exception as e:
            self.logger.error(f"Failed to register tools with server: {e}")
            raise


# Register the communicator *after* the class is defined
register_communicator("mcp-sse", McpSseCommunicator)

# Removed _handle_mcp_request as server logic is in FastAPI handlers
# Removed _register_tool, _register_prompt, _register_resource helpers (integrated into start/register_handler)
# Removed _mcp_custom_method
# Removed _ensure_trailing_slash
# Removed _cleanup_client_manager
