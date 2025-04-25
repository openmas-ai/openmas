"""MCP Client Agent implementation for the OpenMAS framework.

This module provides a client-side Model Context Protocol (MCP) agent implementation that
allows for easy integration with MCP servers.
"""

from typing import Any, Dict, List, Optional

from openmas.agent.mcp import McpAgent


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

    async def disconnect_from_service(self, service_name: str) -> None:
        """Disconnect from an MCP service.

        Args:
            service_name: The name of the service to disconnect from
        """
        if not self.communicator:
            return

        # If the communicator has a method to disconnect, use it
        if hasattr(self.communicator, "_disconnect_from_service"):
            await self.communicator._disconnect_from_service(service_name)

        # Remove the service from connected services if tracking is available
        if hasattr(self.communicator, "connected_services"):
            if service_name in self.communicator.connected_services:
                self.communicator.connected_services.remove(service_name)
                self.logger.info(f"Disconnected from service: {service_name}")

    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available tools from a service.

        Args:
            target_service: The service to get tools from

        Returns:
            A list of tool definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator or not hasattr(self.communicator, "list_tools"):
            raise AttributeError("Communicator does not support list_tools method")

        # Call the communicator's list_tools method
        tools = await self.communicator.list_tools(target_service)

        # Ensure the return type is consistent
        return [
            {"name": str(t.get("name", "")), "description": str(t.get("description", ""))}
            for t in tools
            if isinstance(t, dict)
        ]

    async def list_prompts(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available prompts from a service.

        Args:
            target_service: The service to get prompts from

        Returns:
            A list of prompt definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.communicator.send_request(
            target_service=target_service,
            method="prompt/list",
        )
        # Handle the response, ensuring we return the expected type
        prompts = response.get("prompts", [])
        return [
            {"name": str(p.get("name", "")), "description": str(p.get("description", ""))}
            for p in prompts
            if isinstance(p, dict)
        ]

    async def list_resources(self, target_service: str) -> List[Dict[str, Any]]:
        """List all available resources from a service.

        Args:
            target_service: The service to get resources from

        Returns:
            A list of resource definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.communicator.send_request(
            target_service=target_service,
            method="resource/list",
        )
        # Handle the response, ensuring we return the expected type
        resources = response.get("resources", [])
        return [
            {"name": str(r.get("name", "")), "description": str(r.get("description", ""))}
            for r in resources
            if isinstance(r, dict)
        ]

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
        if hasattr(self.communicator, "call_tool"):
            return await self.communicator.call_tool(
                target_service=target_service,
                tool_name=tool_name,
                arguments=arguments or {},
                timeout=timeout,
            )
        else:
            # Fall back to send_request with the tool/call method
            response = await self.communicator.send_request(
                target_service=target_service,
                method="tool/call",
                params={"name": tool_name, "arguments": arguments or {}},
                timeout=timeout,
            )
            return response.get("result")

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
        if hasattr(self.communicator, "get_prompt"):
            return await self.communicator.get_prompt(
                target_service=target_service,
                prompt_name=prompt_name,
                arguments=arguments or {},
                timeout=timeout,
            )
        else:
            # Fall back to send_request with the prompt/get method
            response = await self.communicator.send_request(
                target_service=target_service,
                method="prompt/get",
                params={"name": prompt_name, "arguments": arguments or {}},
                timeout=timeout,
            )
            return response

    async def get_resource(self, target_service: str, uri: str) -> bytes:
        """Get a resource from a service.

        Args:
            target_service: The service to get the resource from
            uri: The URI of the resource to get

        Returns:
            The content of the resource as bytes

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.communicator.send_request(
            target_service=target_service,
            method="resource/read",
            params={"uri": uri},
        )

        # Ensure we always return bytes
        content = response.get("content", b"")
        if isinstance(content, str):
            return content.encode("utf-8")
        elif isinstance(content, bytes):
            return content
        else:
            # If content is neither str nor bytes, convert to string and then to bytes
            return str(content).encode("utf-8")
