"""MCP server adapter for SimpleMAS.

This module provides a server adapter for the Anthropic MCP SDK.
"""

from typing import Any, Callable, Optional, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server

from simple_mas.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class McpServerWrapper:
    """Wrapper for MCP server functionality.

    This class provides a simplified interface for creating MCP servers
    that can be exposed via stdio or HTTP/SSE.
    """

    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
    ):
        """Initialize the MCP server wrapper.

        Args:
            name: The name of the server
            instructions: Optional instructions for the server
        """
        self.name = name
        self.instructions = instructions
        self.tools = []
        self.resources = []
        self.prompts = []
        logger.debug(f"Initialized MCP server wrapper: {name}")

    def add_tool(
        self,
        fn: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a tool to the server.

        Args:
            fn: The function to add as a tool
            name: Optional name for the tool (defaults to function name)
            description: Optional description of the tool
        """
        self.tools.append((fn, name, description))
        logger.debug(f"Added tool to MCP server: {name or fn.__name__}")

    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator to add a tool to the server.

        Args:
            name: Optional name for the tool (defaults to function name)
            description: Optional description of the tool

        Returns:
            A decorator that registers the function as a tool
        """

        def decorator(fn: F) -> F:
            self.add_tool(fn, name, description)
            return fn

        return decorator

    def add_resource(self, resource: Any) -> None:
        """Add a resource to the server.

        Args:
            resource: The resource to add
        """
        self.resources.append(resource)
        logger.debug("Added resource to MCP server")

    def resource(
        self,
        uri: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator to add a resource to the server.

        Args:
            uri: The URI for the resource
            name: Optional name for the resource
            description: Optional description of the resource
            mime_type: Optional MIME type for the resource

        Returns:
            A decorator that registers the function as a resource
        """
        from mcp.server.resources import Resource

        def decorator(fn: F) -> F:
            resource = Resource(uri=uri, fn=fn, name=name, description=description, mime_type=mime_type)
            self.add_resource(resource)
            return fn

        return decorator

    def add_prompt(self, prompt: Any) -> None:
        """Add a prompt to the server.

        Args:
            prompt: The prompt to add
        """
        self.prompts.append(prompt)
        logger.debug("Added prompt to MCP server")

    def prompt(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Decorator to add a prompt to the server.

        Args:
            name: Optional name for the prompt
            description: Optional description of the prompt

        Returns:
            A decorator that registers the function as a prompt
        """
        from mcp.server.prompts import Prompt

        def decorator(fn: F) -> F:
            prompt = Prompt(fn=fn, name=name or fn.__name__, description=description)
            self.add_prompt(prompt)
            return fn

        return decorator

    def run(self, transport: str = "stdio") -> None:
        """Run the server with the specified transport.

        This is a blocking call that will run until the process is terminated.

        Args:
            transport: The transport to use ("stdio" or "sse")
        """
        if transport == "stdio":
            import asyncio

            asyncio.run(self.run_stdio_async())
        elif transport == "sse":
            import asyncio

            asyncio.run(self.run_sse_async())
        else:
            raise ValueError(f"Unsupported transport: {transport}")

    async def run_stdio_async(self) -> None:
        """Run the server with stdio transport asynchronously."""
        server = stdio_server.create_server(name=self.name, instructions=self.instructions)
        self._setup_server(server)
        await server.run()

    async def run_sse_async(self) -> None:
        """Run the server with SSE transport asynchronously."""
        try:
            import uvicorn
            from fastapi import FastAPI
        except ImportError:
            raise ImportError(
                "FastAPI and uvicorn are required for SSE transport. " "Install them with: pip install fastapi uvicorn"
            )

        app = FastAPI(title=f"{self.name} MCP Server")
        mcp_app = FastMCP(name=self.name, instructions=self.instructions)
        self._setup_server(mcp_app)
        mcp_app.register_with_app(app, path="/mcp")

        config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    def _setup_server(self, server: Any) -> None:
        """Set up the server with tools, resources, and prompts.

        Args:
            server: The server to set up
        """
        # Add tools
        for fn, name, description in self.tools:
            server.add_tool(fn, name=name, description=description)

        # Add resources
        for resource in self.resources:
            server.add_resource(resource)

        # Add prompts
        for prompt in self.prompts:
            server.add_prompt(prompt)
