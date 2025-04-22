"""MCP stdio communicator for SimpleMAS.

This module provides a communicator that uses the MCP protocol over stdin/stdout.
It can be used as both a client (connecting to a subprocess) and a server (running as the main process).
"""

import asyncio
import subprocess
import sys
from typing import Any, AsyncContextManager, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel

from simple_mas.communication.base import BaseCommunicator
from simple_mas.exceptions import CommunicationError, ServiceNotFoundError
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class McpStdioCommunicator(BaseCommunicator):
    """Communicator that uses MCP protocol over stdin/stdout.

    This communicator can function in both client mode (connecting to a subprocess)
    and server mode (running as the main process and handling incoming requests).

    Attributes:
        agent_name: The name of the agent using this communicator.
        service_urls: Mapping of service names to commands for stdio.
        server_mode: Whether the communicator is running in server mode.
        clients: Dictionary of client objects for each service.
        sessions: Dictionary of ClientSession instances for each service.
        connected_services: Set of services that have been connected to.
        handlers: Dictionary of handler functions for each method.
        server: Server instance when running in server mode.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        server_instructions: Optional[str] = None,
    ):
        """Initialize the MCP Stdio communicator.

        Args:
            agent_name: The name of the agent using this communicator.
            service_urls: Mapping of service names to commands for stdio.
                In client mode, each URL should be a command to spawn a subprocess.
                In server mode, this parameter is ignored.
            server_mode: Whether to run in server mode (True) or client mode (False).
            server_instructions: Optional instructions for the server when in server mode.
        """
        super().__init__(agent_name, service_urls)
        self.server_mode = server_mode
        self.server_instructions = server_instructions
        self.clients: Dict[str, Tuple[Any, Any]] = {}  # Dictionary of client instances
        self.sessions: Dict[str, ClientSession] = {}  # Dictionary of ClientSession instances
        self.connected_services: Set[str] = set()
        self.handlers: Dict[str, Callable] = {}
        self.server = None  # Server instance when in server mode
        self.subprocesses: Dict[str, subprocess.Popen] = {}
        self._client_managers: Dict[str, AsyncContextManager] = {}  # Context managers for stdio clients

    async def _connect_to_service(self, service_name: str) -> None:
        """Connect to a MCP service using stdio.

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

        command = self.service_urls[service_name]
        logger.info(f"Connecting to MCP service: {service_name} with command: {command}")

        try:
            # Create a subprocess and stdio client
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
            self.subprocesses[service_name] = process

            # Create server parameters
            server_params = StdioServerParameters(command=command)

            # Create the stdio client
            client_manager = stdio_client(server_params, errlog=sys.stderr)
            self._client_managers[service_name] = client_manager

            # Enter the context manager to get the streams
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

    async def start(self) -> None:
        """Start the communicator.

        In server mode, this starts the server and registers all MCP tools, prompts, and resources
        from the associated agent.
        In client mode, this is a no-op.
        """
        if self.server_mode:
            logger.info("Starting MCP stdio server")

            # Import here to ensure MCP is available
            from mcp.server.prompts import Prompt
            from mcp.server.resources import Resource
            from mcp.server.stdio import stdio_server as create_stdio_server

            # Start the server
            server_cm = create_stdio_server(name=self.agent_name, instructions=self.server_instructions)
            self.server = await server_cm.__aenter__()

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

            logger.info("MCP stdio server started")
        else:
            logger.debug("Not in server mode, no server to start")

    async def stop(self) -> None:
        """Stop the communicator by closing all sessions and the server.

        This method should be called when the communicator is no longer needed.
        """
        logger.info("Stopping MCP stdio communicator")

        # Stop the server if running
        if self.server_mode and self.server is not None:
            logger.info("Stopping MCP stdio server")
            try:
                # The server is a context manager, so exit it
                await self.server.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error stopping MCP stdio server: {e}")
            self.server = None

        # Close all sessions and clients
        if self.sessions:
            logger.debug(f"Closing {len(self.sessions)} sessions")
            self.sessions.clear()

        # Exit the context managers for all stdio clients
        for service_name, client_manager in self._client_managers.items():
            logger.debug(f"Closing client for service: {service_name}")
            try:
                await client_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing client for {service_name}: {e}")

        # Terminate all subprocesses
        for service_name, process in self.subprocesses.items():
            logger.debug(f"Terminating subprocess for service: {service_name}")
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception as e:
                logger.warning(f"Error terminating subprocess for {service_name}: {e}")

        self.clients.clear()
        self._client_managers.clear()
        self.subprocesses.clear()
        self.connected_services.clear()

        logger.info("MCP stdio communicator stopped")

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

    async def _handle_mcp_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Handle an MCP request.

        This method is used to handle MCP requests in both client and server modes.

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
