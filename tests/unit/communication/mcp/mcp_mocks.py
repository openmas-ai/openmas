"""Mock utilities for MCP tests.

This module contains mock classes and functions for testing MCP functionality
without requiring the actual MCP package to be installed.
"""

from __future__ import annotations

import sys
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple
from unittest import mock


class TextContent:
    """Mock implementation of MCP TextContent."""

    def __init__(self, text: str = "", type: str = "text") -> None:
        """Initialize the mock text content.

        Args:
            text: Text content
            type: Content type (defaults to "text")
        """
        self.type = type
        self.text = text

    def __eq__(self, other):
        if isinstance(other, TextContent):
            return self.text == other.text
        return False


class CallToolResult:
    """Mock CallToolResult class."""

    def __init__(self, tool_name: str, result: Dict[str, Any]):
        """Initialize the CallToolResult.

        Args:
            tool_name: Name of the tool that was called
            result: Result of the tool call
        """
        self.tool_name = tool_name
        self.result = result

    def __eq__(self, other):
        if isinstance(other, CallToolResult):
            return self.tool_name == other.tool_name and self.result == other.result
        return False


class Context:
    """Mock Context class for MCP."""

    def __init__(self, session_id: str = "test-session"):
        """Initialize the Context.

        Args:
            session_id: ID of the session
        """
        self.session_id = session_id
        self.resources: Dict[str, Any] = {}
        self.root_id: Optional[str] = None
        self.tool_registry: Dict[str, Any] = {}
        self.prompt_registry: Dict[str, Any] = {}
        self.resource_registry: Dict[str, Any] = {}

    def add_resource(self, key: str, value: Any) -> None:
        """Add a resource to the context."""
        self.resources[key] = value
        self.resource_registry[key] = value

    def get_resource(self, key: str) -> Any:
        """Get a resource from the context."""
        return self.resources.get(key)


class Tool:
    """Mock Tool class for MCP."""

    def __init__(self, name: str, description: str, handler: Callable):
        """Initialize a Tool.

        Args:
            name: Name of the tool
            description: Description of the tool
            handler: Function that handles the tool call
        """
        self.name = name
        self.description = description
        self.handler = handler
        self.schema: Dict[str, Any] = {"type": "object", "properties": {}}


class MockClientSession:
    """Mock implementation of MCP ClientSession."""

    def __init__(self, read_stream: Any = None, write_stream: Any = None) -> None:
        """Initialize the mock client session.

        Args:
            read_stream: Read stream
            write_stream: Write stream
        """
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.url = "https://mock-mcp-url.test"
        self.headers = {"Authorization": "Bearer mock-token"}

        # Mock methods
        self.initialize = mock.AsyncMock()
        self.request = mock.AsyncMock()
        self.call_tool = mock.AsyncMock(return_value="mock-tool-result")
        self.list_tools = mock.AsyncMock()
        self.send_notification = mock.AsyncMock()
        self.sample = mock.AsyncMock()
        self.send_message = mock.AsyncMock(return_value="mock-message-id")
        self.close = mock.AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class MockFastMCP:
    """Mock implementation of MCP FastMCP."""

    def __init__(self, context: Optional[Context] = None, instructions: Optional[str] = None) -> None:
        """Initialize the mock FastMCP server.

        Args:
            context: MCP context
            instructions: Server instructions (optional)
        """
        self.context = context or Context()
        self.instructions = instructions
        self.prompts: Dict[str, Any] = {}
        self.tools: Dict[str, Tool] = {}

        # Mock methods
        self.register_tool = mock.MagicMock()
        self.register_prompt = mock.MagicMock()
        self.register_resource = mock.MagicMock()
        self.add_prompt = mock.MagicMock()
        self.add_tool = mock.MagicMock()
        self.handle_message = mock.AsyncMock()
        self.start = mock.AsyncMock()
        self.stop = mock.AsyncMock()

    def get_context(self, session_id: str) -> Context:
        """Get a context for a session."""
        return Context(session_id=session_id)


class MockSSEClient:
    """Mock SSE Client for streaming responses."""

    def __init__(self, responses: List[Dict[str, Any]]):
        """Initialize the SSE client.

        Args:
            responses: List of response dictionaries to yield
        """
        self.responses = responses
        self.current_index = 0

    async def __aiter__(self) -> "MockSSEClient":
        """Return self as an async iterator."""
        return self

    async def __anext__(self) -> Tuple[Any, Any]:
        """Return a mock read/write stream tuple."""
        # For the first call, return a tuple of mock read/write streams
        if self.current_index == 0:
            self.current_index += 1
            mock_read = mock.AsyncMock()
            mock_write = mock.AsyncMock()
            return (mock_read, mock_write)
        raise StopAsyncIteration

    async def __call__(self, *args, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate mock SSE responses."""
        for response in self.responses:
            yield response


def create_mock_sse_client(responses: List[Dict[str, Any]]) -> Callable:
    """Create a mock SSE client with predefined responses.

    Args:
        responses: List of response dictionaries to yield

    Returns:
        A callable that yields the responses
    """
    return MockSSEClient(responses)


# Create mock module objects
mock_mcp = mock.MagicMock()
mock_client = mock.MagicMock()
mock_sse = mock.MagicMock()
mock_stdio = mock.MagicMock()
mock_session = mock.MagicMock()
mock_server = mock.MagicMock()
mock_types = mock.MagicMock()

# Set up mock sse_client function
mock_sse.sse_client = create_mock_sse_client([])

# Create mock stdio_client function
mock_stdio_client = mock.MagicMock()
mock_stdio.stdio_client = mock_stdio_client

# Set up module structure
mock_mcp.client = mock_client
mock_client.sse = mock_sse
mock_client.stdio = mock_stdio
mock_client.session = mock_session
mock_session.ClientSession = MockClientSession
mock_mcp.server = mock_server
mock_server.fastmcp = mock.MagicMock()
mock_server.fastmcp.Context = Context
mock_server.fastmcp.FastMCP = MockFastMCP
mock_mcp.types = mock_types
mock_types.TextContent = TextContent
mock_types.CallToolResult = CallToolResult

# Add shared mock network for MockCommunicator
_MOCK_NETWORK: Dict[str, Any] = {}


class MockNetwork:
    """Mock network for testing."""

    def __init__(self):
        """Initialize the mock network."""
        self.servers = {}

    def register_server(self, name: str, server: Any) -> None:
        """Register a server in the network.

        Args:
            name: Name of the server
            server: Server instance
        """
        self.servers[name] = server

    def get_server(self, name: str) -> Optional[Any]:
        """Get a server by name.

        Args:
            name: Name of the server

        Returns:
            Server instance or None if not found
        """
        return self.servers.get(name)


# Add method to MockCommunicator class
def add_to_mock_communicator():
    """Add get_mock_network method to MockCommunicator class if imported."""
    if "openmas.testing.mock_communicator" in sys.modules:
        from openmas.testing.mock_communicator import MockCommunicator

        @staticmethod
        def get_mock_network():
            """Get the shared mock network.

            Returns:
                Shared MockNetwork instance
            """
            global _MOCK_NETWORK
            if not _MOCK_NETWORK:
                _MOCK_NETWORK["network"] = MockNetwork()
            return _MOCK_NETWORK["network"]

        # Add the method to the class
        setattr(MockCommunicator, "get_mock_network", get_mock_network)


# Apply this after all mocks
def apply_mcp_mocks() -> None:
    """Apply MCP mocks to sys.modules.

    This function should be called at the beginning of any test module
    that needs to mock MCP dependencies.
    """
    mcp_modules = {
        "mcp": mock_mcp,
        "mcp.client": mock_client,
        "mcp.client.sse": mock_sse,
        "mcp.client.stdio": mock_stdio,
        "mcp.client.session": mock_session,
        "mcp.server": mock_server,
        "mcp.server.fastmcp": mock_server.fastmcp,
        "mcp.types": mock_types,
    }

    # Update sys.modules with our mocks
    sys.modules.update(mcp_modules)

    # Add mock_network support to MockCommunicator if imported
    add_to_mock_communicator()


# Apply mocks when this module is imported
apply_mcp_mocks()
