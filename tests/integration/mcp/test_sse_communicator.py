"""Integration tests for the McpSseCommunicator.

These tests verify that the McpSseCommunicator can properly handle SSE-based
HTTP communication between MCP client and server agents using the real MCP library.

This test suite is marked with @pytest.mark.mcp and will only run in
dedicated test environments with MCP dependencies installed.
"""

import asyncio
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI, Request
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from pydantic import BaseModel, Field
from starlette.routing import Mount

from openmas.agent import McpClientAgent, McpServerAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.communication.mcp.sse_communicator import McpSseCommunicator
from openmas.exceptions import CommunicationError

# Mark all tests in this module with the 'mcp' marker and skip due to real network requirements
pytestmark = [
    pytest.mark.mcp,
    pytest.mark.skip(
        reason="Tests require real MCP integration with HTTP connections which is unreliable in CI environments"
    ),
]


class DivideRequest(BaseModel):
    """Request model for the divide tool."""

    numerator: float = Field(..., description="Number to be divided")
    denominator: float = Field(..., description="Number to divide by")


class DivideResponse(BaseModel):
    """Response model for the divide tool."""

    result: float = Field(..., description="Result of division")
    operation: str = Field(..., description="Description of operation performed")


class SearchRequest(BaseModel):
    """Request model for search tool."""

    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results")


class SearchResult(BaseModel):
    """A single search result."""

    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    relevance: float = Field(..., description="Relevance score")


class SearchResponse(BaseModel):
    """Response model for search tool."""

    results: List[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total number of results")
    query_time_ms: int = Field(..., description="Query execution time in milliseconds")


class SseTestServer(McpServerAgent):
    """Test server agent that exposes tools, prompts, and resources via SSE."""

    def __init__(self, port: int = 8765, **kwargs: Any) -> None:
        """Initialize the test server.

        Args:
            port: HTTP port to use for the server
            **kwargs: Additional arguments to pass to the parent class
        """
        # Create custom FastAPI app for testing
        self.app = FastAPI(title="SSE Test Server")

        super().__init__(
            name="sse_test_server",
            config={
                "COMMUNICATOR_TYPE": "mcp-sse",
                "SERVER_MODE": True,
                "HTTP_PORT": port,
                "SERVER_INSTRUCTIONS": "Test SSE server for integration tests",
            },
            server_type="sse",
            host="localhost",
            port=port,
            **kwargs,
        )

        # Set app on the communicator (will be set after __init__ in set_communicator)
        if hasattr(self, "communicator") and self.communicator:
            self.communicator.app = self.app

    @mcp_tool(
        name="divide",
        description="Divide two numbers",
        input_model=DivideRequest,
        output_model=DivideResponse,
    )
    async def divide_numbers(self, numerator: float, denominator: float) -> Dict[str, Any]:
        """Divide two numbers and return the result.

        Args:
            numerator: Number to be divided
            denominator: Number to divide by

        Returns:
            Dictionary with the result and operation description

        Raises:
            ValueError: If denominator is zero
        """
        if denominator == 0:
            raise ValueError("Cannot divide by zero")

        return {"result": numerator / denominator, "operation": f"Divided {numerator} by {denominator}"}

    @mcp_tool(
        name="search",
        description="Search for information",
        input_model=SearchRequest,
        output_model=SearchResponse,
    )
    async def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Simulate a search operation.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            Search results
        """
        # Simulate processing time
        await asyncio.sleep(0.1)

        # Generate mock results
        results = []
        for i in range(min(limit, 5)):  # At most 5 results
            results.append(
                {
                    "title": f"Result {i+1} for '{query}'",
                    "url": f"https://example.com/search/{i+1}?q={query}",
                    "relevance": 0.9 - (i * 0.1),
                }
            )

        return {"results": results, "total": 5, "query_time_ms": 120}

    @mcp_prompt(
        name="custom_prompt",
        description="A customizable prompt template",
    )
    async def custom_prompt(self, subject: str, tone: str, length: str) -> str:
        """Generate a custom prompt with the given parameters.

        Args:
            subject: The subject to write about
            tone: The tone to use (formal, casual, etc.)
            length: Length indication (short, medium, long)

        Returns:
            The formatted prompt
        """
        return f"""Write a {length} article about {subject}.
Use a {tone} tone throughout the piece.
Ensure the content is engaging and informative.
"""

    @mcp_resource(
        uri="/api/data.json",
        name="sample_data",
        description="Sample JSON data",
        mime_type="application/json",
    )
    async def sample_data(self) -> bytes:
        """Provide sample JSON data.

        Returns:
            JSON data as bytes
        """
        data = {
            "name": "Sample Data",
            "version": "1.0",
            "items": [{"id": 1, "value": "Item One"}, {"id": 2, "value": "Item Two"}, {"id": 3, "value": "Item Three"}],
        }
        return str(data).encode("utf-8")


class SseTestClient(McpClientAgent):
    """Test client agent that connects to SSE-based MCP servers."""

    def __init__(self, server_port: int = 8765, **kwargs: Any) -> None:
        """Initialize the test client.

        Args:
            server_port: Port of the server to connect to
            **kwargs: Additional arguments to pass to the parent class
        """
        # The server name should match the name used in SseTestServer
        server_name = "sse_test_server"

        # Create the communicator first to ensure proper initialization
        from openmas.communication.mcp import McpSseCommunicator

        communicator = McpSseCommunicator(
            agent_name="sse_test_client",
            service_urls={server_name: f"http://localhost:{server_port}/mcp"},
            server_mode=False,
        )

        super().__init__(
            name="sse_test_client",
            config={
                "COMMUNICATOR_TYPE": "mcp-sse",
                "SERVICE_URLS": {server_name: f"http://localhost:{server_port}/mcp"},
            },
            **kwargs,
        )

        # Manually set the communicator to ensure we're using the right type
        self.set_communicator(communicator)


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_sse_direct_communicator() -> None:
    """Test direct instantiation and usage of McpSseCommunicator."""
    # Set up a server and client communicator with a different port to avoid conflicts
    port = 8766
    server_name = "direct_sse_server"

    # Create a specialized test server class for this test
    class DirectSseServer(McpServerAgent):
        """Test server with direct communication using SSE."""

        def __init__(self) -> None:
            """Initialize the test server."""
            # Create custom FastAPI app for testing
            self.app = FastAPI(title="Direct SSE Test")

            super().__init__(
                name=server_name,
                config={
                    "COMMUNICATOR_TYPE": "mcp-sse",
                    "SERVER_MODE": True,
                    "HTTP_PORT": port,
                    "SERVER_INSTRUCTIONS": "Test server for direct communicator test",
                },
            )

            # Set app on the communicator after initialization
            if hasattr(self, "communicator") and self.communicator:
                self.communicator.app = self.app

        @mcp_tool(name="greet", description="Greet a person by name")
        async def greet(self, name: str) -> Dict[str, str]:
            """Greet a person by name.

            Args:
                name: The name to greet

            Returns:
                Dictionary with greeting message
            """
            return {"greeting": f"Hello, {name}!"}

    # Create the server
    server = DirectSseServer()

    # Create a custom client with the known service URLs
    from openmas.communication.mcp import McpSseCommunicator

    client = McpClientAgent(name="direct_sse_client")
    client_comm = McpSseCommunicator(
        agent_name="direct_sse_client",
        service_urls={server_name: f"http://localhost:{port}/mcp"},
        server_mode=False,
    )
    client.set_communicator(client_comm)

    server_task = None
    try:
        # Setup agents
        await server.setup()
        await client.communicator.start()

        # Start server
        server_task = asyncio.create_task(server.run())

        # Allow server to start up
        await asyncio.sleep(2)

        # Call the tool
        result = await client.call_tool(
            target_service=server_name,
            tool_name="greet",
            arguments={"name": "World"},
        )

        # Verify the response
        assert isinstance(result, dict)
        assert "greeting" in result
        assert result["greeting"] == "Hello, World!"

    finally:
        # Clean up
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

        # Shutdown agents
        await server.shutdown()
        await client.communicator.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(40)  # Timeout in seconds
async def test_sse_agent_interaction() -> None:
    """Test interaction between SseTestServer and SseTestClient."""
    # Create server and client with different port to avoid conflicts
    port = 8767
    server = SseTestServer(port=port)
    client = SseTestClient(server_port=port)

    server_task = None
    try:
        # Setup agents
        await server.setup()
        await client.setup()

        # Start server
        server_task = asyncio.create_task(server.run())

        # Allow server to start up
        await asyncio.sleep(2)

        # Test divide tool
        divide_result = await client.call_tool(
            target_service=server.name,
            tool_name="divide",
            arguments={"numerator": 10.0, "denominator": 2.0},
        )

        # Check result
        assert isinstance(divide_result, dict)
        assert "result" in divide_result
        assert divide_result["result"] == 5.0
        assert "operation" in divide_result
        assert "Divided 10.0 by 2.0" in divide_result["operation"]

        # Test error handling for divide by zero
        with pytest.raises(CommunicationError) as excinfo:
            await client.call_tool(
                target_service=server.name,
                tool_name="divide",
                arguments={"numerator": 10.0, "denominator": 0},
            )
        assert "Cannot divide by zero" in str(excinfo.value)

        # Test search tool
        search_result = await client.call_tool(
            target_service=server.name,
            tool_name="search",
            arguments={"query": "test query", "limit": 3},
        )

        # Check search result
        assert isinstance(search_result, dict)
        assert "results" in search_result
        assert isinstance(search_result["results"], list)
        assert len(search_result["results"]) == 3
        assert "total" in search_result
        assert search_result["total"] == 5
        assert "query_time_ms" in search_result
        assert isinstance(search_result["query_time_ms"], int)

    finally:
        # Clean up
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        await server.stop()
        await client.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_sse_connection_error() -> None:
    """Test error handling when connection fails."""
    # Create client with invalid port
    client = SseTestClient(server_port=9999)  # Invalid port

    try:
        await client.setup()

        # Try to call a tool (should fail with connection error)
        with pytest.raises(CommunicationError) as excinfo:
            await client.call_tool(
                target_service="sse_server",
                tool_name="any_tool",
                arguments={},
            )

        # Verify error contains connection-related information or a not found message
        error_text = str(excinfo.value).lower()
        assert any(term in error_text for term in ["connection", "failed to", "connect", "refused", "not found"])
    finally:
        await client.shutdown()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_sse_custom_app_routes() -> None:
    """Test that custom FastAPI routes work alongside MCP endpoints."""
    # Create a server with custom routes
    port = 8768  # Another unique port
    server = SseTestServer(port=port)

    # Add a custom route to the FastAPI app
    @server.app.get("/custom-route")
    async def custom_route():
        return {"message": "This is a custom route"}

    server_task = None
    try:
        # Setup and start server
        await server.setup()
        server_task = asyncio.create_task(server.run())

        # Wait for server to start
        await asyncio.sleep(2)

        # Test the custom route using HTTPX
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{port}/custom-route")

            # Verify response
            assert response.status_code == 200
            assert response.json() == {"message": "This is a custom route"}

            # Also test that MCP endpoint exists
            response = await client.get(f"http://localhost:{port}/mcp")
            assert response.status_code == 200
    finally:
        # Clean up
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

        await server.shutdown()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_sse_multiple_clients() -> None:
    """Test multiple clients connecting to the same server."""
    # Setup server
    port = 8769
    server = SseTestServer(port=port)

    # Create multiple clients
    client1 = SseTestClient(server_port=port)
    client2 = SseTestClient(server_port=port)
    client3 = SseTestClient(server_port=port)

    server_task = None
    try:
        # Setup server and clients
        await server.setup()
        await client1.setup()
        await client2.setup()
        await client3.setup()

        # Start server
        server_task = asyncio.create_task(server.run())

        # Wait for server to start
        await asyncio.sleep(2)

        # All clients call the same tool with different arguments
        results = await asyncio.gather(
            client1.call_tool(
                target_service=server.name,
                tool_name="divide",
                arguments={"numerator": 10.0, "denominator": 2.0},
            ),
            client2.call_tool(
                target_service=server.name,
                tool_name="divide",
                arguments={"numerator": 20.0, "denominator": 4.0},
            ),
            client3.call_tool(
                target_service=server.name,
                tool_name="divide",
                arguments={"numerator": 30.0, "denominator": 3.0},
            ),
        )

        # Check results
        assert len(results) == 3
        assert results[0]["result"] == 5.0
        assert results[1]["result"] == 5.0
        assert results[2]["result"] == 10.0

    finally:
        # Clean up
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        await server.stop()
        await client1.stop()
        await client2.stop()
        await client3.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_add_tool_integration() -> None:
    """Test the ability to add tools to a running SSE server."""
    # Set up a server and client communicator
    port = 8780  # Use a higher port range to avoid conflicts

    # Create a FastAPI app with some debug routes
    app = FastAPI(title="Add Tool Integration Test")

    # Add a test route to confirm FastAPI is working
    @app.get("/test")
    async def test_route():
        return {"status": "ok"}

    # Create a communicator in server mode
    server_communicator = McpSseCommunicator(
        agent_name="add_tool_test_server",
        service_urls={},
        server_mode=True,
        http_port=port,
        server_instructions="Test server for adding tools",
        app=app,
    )

    # Try both formats of URLs
    client_urls = {
        "add_tool_server_with_slash": f"http://localhost:{port}/mcp/",
        "add_tool_server_no_slash": f"http://localhost:{port}/mcp",
    }

    # Create client communicator with both URL formats
    client_communicator = McpSseCommunicator(
        agent_name="add_tool_test_client",
        service_urls=client_urls,
        server_mode=False,
    )

    # Define a simple tool function
    async def subtract(a: int, b: int) -> Dict[str, int]:
        """Subtract b from a."""
        return {"result": a - b}

    server_task = None
    try:
        # Start the server
        await server_communicator.start()

        # Allow server to start up
        await asyncio.sleep(3)

        # Test if the FastAPI app is working with a simple HTTP request
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:{port}/test")
                # Log the test route response
                if resp.status_code == 200:
                    print(f"Test route works: {resp.json()}")
                else:
                    print(f"Test route returned: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Error testing route: {e}")

        # Register the tool
        await server_communicator.register_tool("subtract", "Subtract b from a", subtract)

        # Try different URL formats
        result = None
        error = None
        for service_name in client_urls:
            try:
                print(f"Trying to connect with: {service_name}")
                # Call the tool from the client
                result = await client_communicator.call_tool(
                    target_service=service_name,
                    tool_name="subtract",
                    arguments={"a": 10, "b": 5},
                )
                # If successful, break the loop
                if result:
                    print(f"Successful connection with: {service_name}")
                    break
            except Exception as e:
                print(f"Error with {service_name}: {e}")
                error = e
                continue

        # If we got a result, verify it
        if result:
            assert isinstance(result, dict)
            assert "result" in result
            assert result["result"] == 5  # 10 - 5 = 5
        else:
            # If all connection attempts failed, fail the test with the last error
            pytest.fail(f"Failed to connect to MCP server with any URL format: {error}")

    finally:
        # Clean up
        await server_communicator.stop()
        await client_communicator.stop()
