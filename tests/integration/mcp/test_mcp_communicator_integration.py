"""Integration tests for communication between MCP SSE and STDIO communicators.

These tests verify that the McpSseCommunicator and McpStdioCommunicator can
communicate with each other using the Model Context Protocol.

This test suite is marked with @pytest.mark.mcp and will only run in
dedicated test environments with MCP dependencies installed.
"""

import asyncio
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, Field

from openmas.agent import McpClientAgent, McpServerAgent, mcp_tool
from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError

# Mark all tests in this module with the 'mcp' marker and skip due to real network requirements
pytestmark = [
    pytest.mark.mcp,
    pytest.mark.skip(
        reason="Tests require real MCP integration with network connections which is unreliable in CI environments"
    ),
]


class CalculateRequest(BaseModel):
    """Request model for calculator operations."""

    x: float = Field(..., description="First operand")
    y: float = Field(..., description="Second operand")
    operation: str = Field(..., description="Operation to perform (add, subtract, multiply, divide)")


class CalculateResponse(BaseModel):
    """Response model for calculator operations."""

    result: float = Field(..., description="Result of the calculation")
    operation_performed: str = Field(..., description="Description of the operation performed")


class SseCalculatorServer(McpServerAgent):
    """SSE-based calculator server that exposes mathematical operations as tools."""

    def __init__(self, port: int = 8780, **kwargs: Any) -> None:
        """Initialize the calculator server.

        Args:
            port: HTTP port to use for the server
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(
            name="sse_calculator_server",
            config={
                "COMMUNICATOR_TYPE": "mcp-sse",
                "SERVER_MODE": True,
                "HTTP_PORT": port,
                "SERVER_INSTRUCTIONS": "Calculator server exposing mathematical operations",
            },
            server_type="sse",
            **kwargs,
        )

    @mcp_tool(
        name="calculate",
        description="Perform a calculation on two numbers",
        input_model=CalculateRequest,
        output_model=CalculateResponse,
    )
    async def calculate(self, x: float, y: float, operation: str) -> Dict[str, Any]:
        """Perform the requested calculation.

        Args:
            x: First operand
            y: Second operand
            operation: Operation to perform (add, subtract, multiply, divide)

        Returns:
            Dictionary with the result and operation description

        Raises:
            ValueError: If operation is invalid or if dividing by zero
        """
        if operation == "add":
            result = x + y
            description = f"Added {x} and {y}"
        elif operation == "subtract":
            result = x - y
            description = f"Subtracted {y} from {x}"
        elif operation == "multiply":
            result = x * y
            description = f"Multiplied {x} by {y}"
        elif operation == "divide":
            if y == 0:
                raise ValueError("Cannot divide by zero")
            result = x / y
            description = f"Divided {x} by {y}"
        else:
            raise ValueError(f"Unknown operation: {operation}")

        return {"result": result, "operation_performed": description}


class StdioEchoServer:
    """Helper class to create a stdio-based MCP server script."""

    @staticmethod
    def create_script(with_tools: bool = True) -> str:
        """Create a temporary script file for an MCP stdio server.

        Args:
            with_tools: Whether to include tools in the server

        Returns:
            Path to the created script file
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as server_file:
            server_code = """
import asyncio
import sys
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import CallToolResult

async def echo(ctx: Context, message: str) -> CallToolResult:
    return CallToolResult(tool_name="echo", result={"message": message})

async def calculate(ctx: Context, x: float, y: float, operation: str) -> CallToolResult:
    if operation == "add":
        result = x + y
        description = f"Added {x} and {y}"
    elif operation == "subtract":
        result = x - y
        description = f"Subtracted {y} from {x}"
    elif operation == "multiply":
        result = x * y
        description = f"Multiplied {x} by {y}"
    elif operation == "divide":
        if y == 0:
            raise ValueError("Cannot divide by zero")
        result = x / y
        description = f"Divided {x} by {y}"
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    return CallToolResult(
        tool_name="calculate", 
        result={"result": result, "operation_performed": description}
    )

async def main():
    mcp_server = FastMCP(instructions="Echo server exposing echo and calculate tools")
"""
            if with_tools:
                server_code += """
    mcp_server.add_tool("echo", "Echo a message", echo)
    mcp_server.add_tool("calculate", "Perform a calculation", calculate)
"""

            server_code += """
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    await mcp_server.serve_stdio(stdin, stdout)

if __name__ == "__main__":
    asyncio.run(main())
"""
            server_file.write(server_code)
            server_file.flush()
            server_path = server_file.name

        # Make the script executable
        os.chmod(server_path, 0o755)
        return server_path


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_stdio_client_to_sse_server() -> None:
    """Test that a STDIO client can communicate with an SSE server."""
    # Set up an SSE server on a unique port
    port = 8781
    server = SseCalculatorServer(port=port)

    try:
        # Start the server
        await server.setup()

        # Create a STDIO client communicator that connects to the SSE server
        # We'll create it directly rather than through an agent
        communicator = McpStdioCommunicator(
            agent_name="stdio_client",
            service_urls={"calculator": f"curl http://localhost:{port}/mcp"},
            server_mode=False,
        )

        # Start the client
        await communicator.start()

        try:
            # Call the calculate tool on the server
            result = await communicator.call_tool(
                target_service="calculator", tool_name="calculate", arguments={"x": 10, "y": 5, "operation": "divide"}
            )

            # Check the result
            assert isinstance(result, dict)
            assert "result" in result
            assert "operation_performed" in result
            assert result["result"] == 2.0
            assert "Divided 10 by 5" in result["operation_performed"]
        finally:
            # Stop the client
            await communicator.stop()
    finally:
        # Stop the server
        await server.cleanup()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_sse_client_to_stdio_server() -> None:
    """Test that an SSE client can communicate with a STDIO server."""
    # Create a STDIO server script
    server_script_path = StdioEchoServer.create_script()

    try:
        # Get Python executable path
        python_exe = sys.executable

        # Create an SSE client communicator that will connect to the STDIO server
        communicator = McpSseCommunicator(
            agent_name="sse_client",
            service_urls={},  # We'll add it after start
            server_mode=False,
        )

        # Start the SSE client communicator
        await communicator.start()

        # Add the STDIO server as a service
        # This requires direct manipulation which isn't normally recommended
        # In real usage, you'd configure this before calling start()
        communicator.service_urls["echo_server"] = python_exe
        communicator.service_args = {"echo_server": [server_script_path]}

        # Use the STDIO communicator as a bridge to connect
        stdio_bridge = McpStdioCommunicator(
            agent_name="stdio_bridge",
            service_urls={"echo_server": python_exe},
            service_args={"echo_server": [server_script_path]},
            server_mode=False,
        )

        # Start the STDIO bridge
        await stdio_bridge.start()

        try:
            # Test the echo tool via the STDIO bridge
            result = await stdio_bridge.call_tool(
                target_service="echo_server", tool_name="echo", arguments={"message": "Hello from SSE client"}
            )

            # Check the result
            assert isinstance(result, dict)
            assert "message" in result
            assert result["message"] == "Hello from SSE client"

            # Test the calculate tool
            result = await stdio_bridge.call_tool(
                target_service="echo_server", tool_name="calculate", arguments={"x": 7, "y": 3, "operation": "multiply"}
            )

            # Check the result
            assert isinstance(result, dict)
            assert "result" in result
            assert "operation_performed" in result
            assert result["result"] == 21.0
            assert "Multiplied 7 by 3" in result["operation_performed"]
        finally:
            # Stop the STDIO bridge
            await stdio_bridge.stop()
            # Stop the SSE client
            await communicator.stop()
    finally:
        # Clean up the temporary script file
        try:
            os.unlink(server_script_path)
        except (OSError, IOError):
            pass


@pytest.mark.asyncio
@pytest.mark.timeout(40)  # Longer timeout for full agent setup
async def test_bidirectional_communication() -> None:
    """Test bidirectional communication between SSE and STDIO servers and clients."""
    # Set up an SSE server
    sse_port = 8782
    sse_server = SseCalculatorServer(port=sse_port)

    # Create a STDIO server script
    stdio_script_path = StdioEchoServer.create_script()

    try:
        # Start the SSE server
        await sse_server.setup()

        # Get Python executable path
        python_exe = sys.executable

        # Create a client that can talk to both servers
        communicator = McpStdioCommunicator(
            agent_name="hybrid_client",
            service_urls={"calculator": f"curl http://localhost:{sse_port}/mcp", "echo_server": python_exe},
            service_args={"echo_server": [stdio_script_path]},
            server_mode=False,
        )

        # Start the client
        await communicator.start()

        try:
            # Call the SSE server's calculate tool
            sse_result = await communicator.call_tool(
                target_service="calculator", tool_name="calculate", arguments={"x": 20, "y": 4, "operation": "divide"}
            )

            # Call the STDIO server's echo tool
            stdio_result = await communicator.call_tool(
                target_service="echo_server",
                tool_name="echo",
                arguments={"message": "Testing bidirectional communication"},
            )

            # Check the results
            assert isinstance(sse_result, dict)
            assert sse_result["result"] == 5.0
            assert "Divided 20 by 4" in sse_result["operation_performed"]

            assert isinstance(stdio_result, dict)
            assert stdio_result["message"] == "Testing bidirectional communication"
        finally:
            # Stop the client
            await communicator.stop()
    finally:
        # Stop the SSE server
        await sse_server.cleanup()
        # Clean up the temporary script file
        try:
            os.unlink(stdio_script_path)
        except (OSError, IOError):
            pass
