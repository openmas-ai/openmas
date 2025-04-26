"""MCP Client Agent implementation for the OpenMAS framework.

This module provides a client-side Model Context Protocol (MCP) agent implementation that
allows for easy integration with MCP servers.
"""

from typing import Any, Dict, List, Optional

from openmas.agent.mcp import McpAgent
from openmas.exceptions import CommunicationError, ServiceNotFoundError


class McpClientAgent(McpAgent):
    """Client agent that connects to MCP servers.

    This specialized agent provides convenience methods for client-specific operations
    like connecting to servers, listing available tools/prompts/resources, etc.
    """

    async def connect_to_service(self, service_name: str, host: str, port: int, protocol: str = "sse") -> None:
        """Connect to an MCP service.

        Args:
            service_name: The name to use for the service in this client
            host: The hostname or IP address of the service
            port: The port number of the service
            protocol: The protocol to use ('sse' or 'stdio')

        Raises:
            ValueError: If the protocol is not supported
            CommunicationError: If there is a problem connecting to the service
        """
        if not self.communicator:
            raise RuntimeError("Agent must have a communicator set before connecting to services")

        # Update service URLs in the communicator
        if protocol.lower() == "sse":
            url = f"http://{host}:{port}/mcp"
        elif protocol.lower() == "stdio":
            url = f"stdio://{host}:{port}"
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")

        # Add/update the URL in the communicator's service_urls
        self.communicator.service_urls[service_name] = url
        self.logger.info(f"Added service URL for {service_name}: {url}")

        # Try to connect to verify the service is available
        try:
            if hasattr(self.communicator, "_connect_to_service"):
                await self.communicator._connect_to_service(service_name)
                self.logger.info(f"Successfully connected to {service_name}")
        except (CommunicationError, ServiceNotFoundError) as e:
            # Remove the URL if connection failed
            if service_name in self.communicator.service_urls:
                del self.communicator.service_urls[service_name]
            self.logger.error(f"Failed to connect to {service_name}: {e}")
            raise

    async def disconnect_from_service(self, service_name: str) -> None:
        """Disconnect from an MCP service.

        Args:
            service_name: The name of the service to disconnect from
        """
        if not self.communicator:
            return

        # If the communicator has a method to disconnect, use it
        try:
            if hasattr(self.communicator, "_cleanup_client_manager"):
                await self.communicator._cleanup_client_manager(service_name)
                self.logger.info(f"Disconnected from service: {service_name}")
            elif hasattr(self.communicator, "_disconnect_from_service"):
                await self.communicator._disconnect_from_service(service_name)
                self.logger.info(f"Disconnected from service: {service_name}")
            else:
                # Remove the service from connected services if tracking is available
                if hasattr(self.communicator, "connected_services"):
                    if service_name in self.communicator.connected_services:
                        self.communicator.connected_services.remove(service_name)
                        self.logger.info(f"Disconnected from service: {service_name}")
        except Exception as e:
            self.logger.warning(f"Error disconnecting from service {service_name}: {e}")

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available tools from a service.

        Args:
            target_service: The service to get tools from

        Returns:
            A list of tool definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        if hasattr(self.communicator, "list_tools"):
            # Call the communicator's list_tools method
            tools = await self.communicator.list_tools(target_service)
        else:
            # Fall back to send_request with the tool/list method
            tools = await self.communicator.send_request(
                target_service=target_service,
                method="tool/list",
            )

        # Ensure the return type is consistent
        if isinstance(tools, list):
            return [
                {"name": str(t.get("name", "")), "description": str(t.get("description", "")), **t}
                for t in tools
                if isinstance(t, dict)
            ]
        # Handle case where tools might be under a 'tools' key in a dict
        elif isinstance(tools, dict) and "tools" in tools and isinstance(tools["tools"], list):
            return [
                {"name": str(t.get("name", "")), "description": str(t.get("description", "")), **t}
                for t in tools["tools"]
                if isinstance(t, dict)
            ]
        else:
            self.logger.warning(f"Unexpected format for tool list from {target_service}: {tools}")
            return []

    async def list_prompts(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available prompts from a service.

        Args:
            target_service: The service to get prompts from

        Returns:
            A list of prompt definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        try:
            response = await self.communicator.send_request(
                target_service=target_service,
                method="prompt/list",
            )

            # Handle different response formats
            if isinstance(response, list):
                prompts = response
            elif isinstance(response, dict) and "prompts" in response:
                prompts = response["prompts"]
            else:
                prompts = []

            return [
                {"name": str(p.get("name", "")), "description": str(p.get("description", "")), **p}
                for p in prompts
                if isinstance(p, dict)
            ]
        except Exception as e:
            self.logger.error(f"Error listing prompts from {target_service}: {e}")
            raise

    async def list_resources(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available resources from a service.

        Args:
            target_service: The service to get resources from

        Returns:
            A list of resource definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        try:
            response = await self.communicator.send_request(
                target_service=target_service,
                method="resource/list",
            )

            # Handle different response formats
            if isinstance(response, list):
                resources = response
            elif isinstance(response, dict) and "resources" in response:
                resources = response["resources"]
            else:
                resources = []

            return [
                {
                    "name": str(r.get("name", "")),
                    "description": str(r.get("description", "")),
                    "uri": str(r.get("uri", "")),
                    **r,
                }
                for r in resources
                if isinstance(r, dict)
            ]
        except Exception as e:
            self.logger.error(f"Error listing resources from {target_service}: {e}")
            raise

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
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        arguments = arguments or {}

        try:
            if hasattr(self.communicator, "call_tool"):
                return await self.communicator.call_tool(
                    target_service=target_service,
                    tool_name=tool_name,
                    arguments=arguments,
                    timeout=timeout,
                )
            else:
                # Fall back to send_request with the tool/call method
                response = await self.communicator.send_request(
                    target_service=target_service,
                    method=f"tool/call/{tool_name}",
                    params=arguments,
                    timeout=timeout,
                )

                # Handle different response formats
                if isinstance(response, dict) and "result" in response:
                    return response["result"]
                return response
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name} on {target_service}: {e}")
            raise

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
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        arguments = arguments or {}

        try:
            if hasattr(self.communicator, "get_prompt"):
                return await self.communicator.get_prompt(
                    target_service=target_service,
                    prompt_name=prompt_name,
                    arguments=arguments,
                    timeout=timeout,
                )
            else:
                # Fall back to send_request with the prompt/get method
                response = await self.communicator.send_request(
                    target_service=target_service,
                    method=f"prompt/get/{prompt_name}",
                    params=arguments,
                    timeout=timeout,
                )
                return response
        except Exception as e:
            self.logger.error(f"Error getting prompt {prompt_name} from {target_service}: {e}")
            raise

    async def read_resource(self, target_service: str, uri: str, timeout: Optional[float] = None) -> bytes:
        """Read a resource from a service.

        Args:
            target_service: The service to get the resource from
            uri: The URI of the resource to get
            timeout: Optional timeout in seconds

        Returns:
            The content of the resource as bytes

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator:
            raise AttributeError("Agent has no communicator set")

        try:
            if hasattr(self.communicator, "read_resource"):
                result = await self.communicator.read_resource(
                    target_service=target_service,
                    resource_uri=uri,
                    timeout=timeout,
                )
                # Ensure we always return bytes
                if isinstance(result, str):
                    return result.encode("utf-8")
                elif isinstance(result, bytes):
                    return result
                else:
                    # If result is neither str nor bytes, convert to string and then to bytes
                    return str(result).encode("utf-8")
            else:
                # Fall back to send_request with the resource/read method
                response = await self.communicator.send_request(
                    target_service=target_service,
                    method="resource/read",
                    params={"uri": uri},
                    timeout=timeout,
                )

                # Handle case where response is already bytes (from MockCommunicator)
                if isinstance(response, bytes):
                    return response

                # Handle dict response with content field
                if isinstance(response, dict):
                    content = response.get("content", b"")
                    if isinstance(content, str):
                        return content.encode("utf-8")
                    elif isinstance(content, bytes):
                        return content
                    else:
                        # If content is neither str nor bytes, convert to string and then to bytes
                        return str(content).encode("utf-8")

                # If response is neither bytes nor dict, convert to string and then to bytes
                return str(response).encode("utf-8")
        except Exception as e:
            self.logger.error(f"Error reading resource {uri} from {target_service}: {e}")
            raise

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
        """Sample a prompt from a service.

        This is a specialized method for MCP client-based interaction with LLMs.

        Args:
            target_service: The service to sample from
            messages: List of message objects
            system_prompt: Optional system prompt
            temperature: Optional temperature parameter
            max_tokens: Optional maximum tokens parameter
            include_context: Optional include_context parameter
            model_preferences: Optional model preferences
            stop_sequences: Optional stop sequences
            timeout: Optional timeout in seconds

        Returns:
            The sampling result with at least a "content" field

        Raises:
            CommunicationError: If there's a communication problem
        """
        return await super().sample_prompt(
            target_service=target_service,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            include_context=include_context,
            model_preferences=model_preferences,
            stop_sequences=stop_sequences,
            timeout=timeout,
        )
