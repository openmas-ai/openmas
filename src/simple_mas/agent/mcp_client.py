"""MCP Client Agent implementation for the SimpleMAS framework.

This module provides a client-side Model Context Protocol (MCP) agent implementation that
allows for easy integration with MCP servers.
"""

from typing import Any, Dict, List, Optional

from simple_mas.agent.mcp import McpAgent


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

    async def list_tools(self, service_name: str) -> List[Dict[str, Any]]:
        """List all available tools from a service.

        Args:
            service_name: The service to get tools from

        Returns:
            A list of tool definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if not self.communicator or not hasattr(self.communicator, "list_tools"):
            raise AttributeError("Communicator does not support list_tools method")

        return await self.communicator.list_tools(service_name)

    async def list_prompts(self, service_name: str) -> List[Dict[str, Any]]:
        """List all available prompts from a service.

        Args:
            service_name: The service to get prompts from

        Returns:
            A list of prompt definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.communicator.send_request(
            target_service=service_name,
            method="prompt/list",
        )
        return response.get("prompts", [])

    async def list_resources(self, service_name: str) -> List[Dict[str, Any]]:
        """List all available resources from a service.

        Args:
            service_name: The service to get resources from

        Returns:
            A list of resource definitions

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.communicator.send_request(
            target_service=service_name,
            method="resource/list",
        )
        return response.get("resources", [])

    async def call_tool(self, service_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call a tool on a service.

        Args:
            service_name: The service to call the tool on
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool

        Returns:
            The result of the tool call

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if hasattr(self.communicator, "call_tool"):
            return await self.communicator.call_tool(
                target_service=service_name,
                tool_name=tool_name,
                arguments=arguments or {},
            )
        else:
            # Fall back to send_request with the tool/call method
            response = await self.communicator.send_request(
                target_service=service_name,
                method="tool/call",
                params={"name": tool_name, "arguments": arguments or {}},
            )
            return response.get("result")

    async def get_prompt(self, service_name: str, prompt_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Get a prompt from a service.

        Args:
            service_name: The service to get the prompt from
            prompt_name: The name of the prompt to get
            arguments: The arguments to pass to the prompt

        Returns:
            The result of the prompt

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        if hasattr(self.communicator, "get_prompt"):
            return await self.communicator.get_prompt(
                target_service=service_name,
                prompt_name=prompt_name,
                arguments=arguments or {},
            )
        else:
            # Fall back to send_request with the prompt/get method
            response = await self.communicator.send_request(
                target_service=service_name,
                method="prompt/get",
                params={"name": prompt_name, "arguments": arguments or {}},
            )
            return response

    async def get_resource(self, service_name: str, uri: str) -> bytes:
        """Get a resource from a service.

        Args:
            service_name: The service to get the resource from
            uri: The URI of the resource to get

        Returns:
            The content of the resource

        Raises:
            CommunicationError: If there is a problem with the communication
        """
        response = await self.communicator.send_request(
            target_service=service_name,
            method="resource/read",
            params={"uri": uri},
        )
        return (
            response.get("content", b"").encode("utf-8")
            if isinstance(response.get("content"), str)
            else response.get("content", b"")
        )
