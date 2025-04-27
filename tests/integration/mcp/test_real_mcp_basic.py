"""Tests for the MCP integration functionality."""

import asyncio
import os
import subprocess
import sys
import time
from typing import Optional, AsyncGenerator, Dict, Any
import pytest

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent


async def test_simple_mcp_integration() -> None:
    """Test simple interaction with an MCP server.
    
    This is a basic integration test that:
    1. Launches a stdio server script
    2. Creates an MCP client connected to that server
    3. Tests the echo tool functionality
    """
    # Get the path to the stdio server script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script_path = os.path.join(script_dir, "stdio_server_script.py")
    
    # First verify the server script works in test-only mode
    try:
        # Run with a timeout to prevent hanging
        result = subprocess.run(
            [sys.executable, server_script_path, "--test-only"],
            capture_output=True,
            text=True,
            timeout=5  # 5 second timeout
        )
        
        # Check for successful execution
        assert result.returncode == 0, f"Server script test-only mode failed with code {result.returncode}. Stderr: {result.stderr}"
        assert "test-only-mode" in result.stdout, f"Test-only mode response not found in stdout: {result.stdout}"
    except subprocess.TimeoutExpired:
        pytest.fail("Server script test-only mode timed out after 5 seconds")
    
    # Main test with full server/client interaction
    client_manager = None
    session = None
    server_process = None
    
    try:
        # Start server process
        server_process = subprocess.Popen(
            [sys.executable, server_script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # Important for binary pipes
        )
        
        # Allow server to initialize (with timeout)
        init_timeout = 5  # seconds
        start_time = time.time()
        initialized = False
        
        while time.time() - start_time < init_timeout:
            # Check if process is still running
            if server_process.poll() is not None:
                stderr_output = server_process.stderr.read() if server_process.stderr else b"No stderr available"
                pytest.fail(f"Server process terminated unexpectedly with code {server_process.returncode}. "
                           f"Stderr: {stderr_output.decode('utf-8', errors='replace')}")
            
            # Try to read some initial output - this confirms the server started
            if server_process.stdout and server_process.stdout.readable():
                # Peek at the output without consuming it
                stdout_data = server_process.stdout.peek(1024)
                if stdout_data and b"test-init" in stdout_data:
                    initialized = True
                    break
            
            # Small delay before checking again
            await asyncio.sleep(0.1)
        
        if not initialized:
            if server_process.poll() is not None:
                stderr_output = server_process.stderr.read() if server_process.stderr else b"No stderr available"
                pytest.fail(f"Server failed to start. Exit code: {server_process.returncode}. "
                           f"Stderr: {stderr_output.decode('utf-8', errors='replace')}")
            else:
                # Force terminate and collect stderr
                server_process.terminate()
                stderr_output = server_process.stderr.read() if server_process.stderr else b"No stderr available"
                pytest.fail(f"Server initialization timed out after {init_timeout} seconds. "
                           f"Stderr: {stderr_output.decode('utf-8', errors='replace')}")
        
        # Open the streams with timeout
        stream_timeout = 5  # seconds
        try:
            # Async context manager with timeout
            client_manager_task = asyncio.create_task(
                sse_client.open_stdio_streams(server_process.stdout, server_process.stdin)
            )
            client_manager = await asyncio.wait_for(client_manager_task, timeout=stream_timeout)
        except asyncio.TimeoutError:
            pytest.fail(f"Opening stdio streams timed out after {stream_timeout} seconds")
        
        # Initialize the session with timeout
        session_timeout = 5  # seconds
        try:
            async with client_manager as manager:
                session_init_task = asyncio.create_task(ClientSession(manager).enter_async())
                session = await asyncio.wait_for(session_init_task, timeout=session_timeout)
                
                # Verify session is initialized
                assert session is not None, "Session was not properly initialized"
                
                # List tools with timeout
                list_tools_timeout = 3  # seconds
                try:
                    tools_task = asyncio.create_task(session.list_tools())
                    tools = await asyncio.wait_for(tools_task, timeout=list_tools_timeout)
                    
                    # Verify the echo tool exists
                    assert any(tool.name == "echo" for tool in tools), "Echo tool not found in available tools"
                    
                    # Test the echo tool with timeout
                    echo_timeout = 3  # seconds
                    try:
                        message = "Hello, MCP world!"
                        echo_task = asyncio.create_task(
                            session.call_tool("echo", {"message": message})
                        )
                        echo_result = await asyncio.wait_for(echo_task, timeout=echo_timeout)
                        
                        # Verify the echo result
                        assert echo_result.get("echoed") == message, f"Echo result {echo_result} doesn't match input {message}"
                    except asyncio.TimeoutError:
                        pytest.fail(f"Call to echo tool timed out after {echo_timeout} seconds")
                    
                except asyncio.TimeoutError:
                    pytest.fail(f"Listing tools timed out after {list_tools_timeout} seconds")
                
                # Close the session with timeout
                close_timeout = 3  # seconds
                try:
                    # No need to assign this to a variable, just await it with timeout
                    await asyncio.wait_for(session.aclose(), timeout=close_timeout)
                except asyncio.TimeoutError:
                    pytest.fail(f"Closing session timed out after {close_timeout} seconds")
        except Exception as e:
            pytest.fail(f"Exception during MCP session: {e}")
        finally:
            # Clean up client resources with timeout if necessary
            if client_manager and not client_manager.is_closed:
                close_mgr_timeout = 3  # seconds
                try:
                    # Try to gracefully close if not already closed
                    await asyncio.wait_for(client_manager.aclose(), timeout=close_mgr_timeout)
                except asyncio.TimeoutError:
                    # Report but continue with cleanup
                    print(f"WARNING: Closing client manager timed out after {close_mgr_timeout} seconds")
                except Exception as e:
                    print(f"WARNING: Error closing client manager: {e}")
    
    finally:
        # Clean up server process
        if server_process:
            # Check if still running before trying to terminate
            if server_process.poll() is None:
                # Try graceful termination
                server_process.terminate()
                try:
                    # Wait with timeout
                    server_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if termination didn't work
                    server_process.kill()
                    server_process.wait()
            
            # Collect any remaining stderr for diagnostics
            if server_process.stderr and server_process.stderr.readable():
                stderr_data = server_process.stderr.read()
                if stderr_data:
                    print(f"Server stderr output: {stderr_data.decode('utf-8', errors='replace')}") 