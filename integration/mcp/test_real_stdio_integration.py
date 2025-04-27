"""Integration test for real MCP stdio communication.

This test verifies that the MCP stdio communication works correctly between
a client agent and a server script running as a subprocess.
"""

import asyncio
import json
import os
import subprocess
import sys
import pytest
import structlog
from pathlib import Path
from unittest import mock
import time
import functools
from contextlib import asynccontextmanager
import anyio
import logging

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from openmas.agent import McpClientAgent
# Explicitly import the communicator to ensure it's registered
from openmas.communication.mcp.stdio_communicator import McpStdioCommunicator
from openmas.communication.base import register_communicator, get_communicator_class
from openmas.communication import create_communicator

# Set up logging
logger = structlog.get_logger(__name__)

# Mark all tests in this module with the 'mcp' marker
pytestmark = [
    pytest.mark.mcp,
]

# Constants for timeouts
CONNECTION_TIMEOUT = 30.0  # seconds
OPERATION_TIMEOUT = 60.0  # seconds


async def safe_async_operation(coro_func, *args, timeout=None, max_retries=3, retry_delay=1.0, **kwargs):
    """Execute an async operation safely with retries and cancellation protection.
    
    Args:
        coro_func: A callable that returns a coroutine (not a coroutine itself)
        *args: Arguments to pass to the coroutine function
        timeout: Optional timeout in seconds
        max_retries: Maximum number of retries if operation fails
        retry_delay: Delay between retries in seconds
        **kwargs: Keyword arguments to pass to the coroutine function
        
    Returns:
        The result of the coroutine
        
    Raises:
        Exception: If all retries fail
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            # Create a new coroutine each time
            coro = coro_func(*args, **kwargs)
            
            # Use shield to protect from cancellation
            protected_coro = asyncio.shield(coro)
            
            # Apply timeout if specified
            if timeout is not None:
                return await asyncio.wait_for(protected_coro, timeout=timeout)
            else:
                return await protected_coro
                
        except asyncio.CancelledError as e:
            logger.warning(f"Operation was cancelled (attempt {attempt+1}/{max_retries})")
            last_error = e
            # Don't retry if this is the last attempt
            if attempt == max_retries - 1:
                raise
                
        except Exception as e:
            logger.warning(f"Operation failed with {type(e).__name__}: {e} (attempt {attempt+1}/{max_retries})")
            last_error = e
            # Don't retry if this is the last attempt
            if attempt == max_retries - 1:
                raise
                
        # Wait before retrying
        await asyncio.sleep(retry_delay * (attempt + 1))
        
    # If we get here, all retries failed
    assert last_error is not None
    raise last_error


@asynccontextmanager
async def create_test_communicator(script_path, agent_name="test_communicator"):
    """Create and manage a test communicator with proper setup and cleanup.
    
    Args:
        script_path: Path to the server script
        agent_name: Name for the agent using this communicator
        
    Yields:
        The configured communicator instance
    """
    # Create the communicator
    communicator = McpStdioCommunicator(
        agent_name=agent_name,
        service_urls={"stdio_server": sys.executable},
        service_args={"stdio_server": [str(script_path)]},
    )
    
    try:
        # Start the communicator
        logger.info(f"Starting communicator for {agent_name}")
        await safe_async_operation(communicator.start, timeout=CONNECTION_TIMEOUT)
        
        # Connect to the service
        logger.info(f"Connecting to stdio_server service for {agent_name}")
        await safe_async_operation(
            communicator._connect_to_service, 
            "stdio_server", 
            timeout=CONNECTION_TIMEOUT
        )
        
        # Verify the session was created
        assert "stdio_server" in communicator.sessions, "Session was not created"
        logger.info("Session created successfully")
        
        # Add a small delay to ensure session is fully ready
        await asyncio.sleep(2.0)
        
        # Yield the communicator for use in the test
        yield communicator
        
    finally:
        # Clean up
        logger.info(f"Stopping communicator for {agent_name}")
        try:
            await safe_async_operation(communicator.stop, timeout=CONNECTION_TIMEOUT)
            logger.info("Communicator stopped")
        except Exception as e:
            logger.exception(f"Error stopping communicator: {type(e).__name__}: {e}")
            # Force cleanup if normal stop fails
            if hasattr(communicator, "_processes"):
                for proc_name, proc in communicator._processes.items():
                    if proc and proc.returncode is None:
                        logger.warning(f"Forcibly terminating process {proc_name}")
                        proc.terminate()


@pytest.fixture(autouse=True)
def ensure_communicator_registered():
    """Ensure the MCP stdio communicator is registered before each test."""
    # Force re-registration of the communicator to ensure it's available
    register_communicator("mcp-stdio", McpStdioCommunicator)
    # Verify it's properly registered
    comm_class = get_communicator_class("mcp-stdio")
    assert comm_class is McpStdioCommunicator
    logger.info(f"Registered MCP stdio communicator: {comm_class}")
    yield


@pytest.mark.asyncio
async def test_server_script_can_run() -> None:
    """Test that the server script can run independently.
    
    This test verifies the basic functionality of the server script outside of the
    MCP protocol to ensure it can start up correctly.
    """
    # Get path to the server script
    script_dir = Path(__file__).parent
    server_script_path = script_dir / "stdio_server_script.py"
    
    # Ensure the script is executable
    os.chmod(server_script_path, 0o755)
    
    # Run the script directly with subprocess and capture output
    logger.info(f"Running script directly: {server_script_path}")
    
    # Use asyncio subprocess to run the command with the test-only flag
    proc = await asyncio.create_subprocess_exec(
        sys.executable, 
        str(server_script_path),
        "--test-only",  # Add test-only flag to make it exit after sending test message
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        # Set a timeout for script execution
        stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        
        # Check if the script started and printed anything
        logger.info(f"Script stdout: {stdout_data.decode('utf-8')}")
        logger.info(f"Script stderr: {stderr_data.decode('utf-8')}")
        
        # Check for our test JSON message
        assert stdout_data, "Script should output something to stdout"
        stdout_text = stdout_data.decode('utf-8')
        assert "jsonrpc" in stdout_text, "Script should output jsonrpc message to stdout"
        
        # Log success
        logger.info("Server script executed successfully.")
    except asyncio.TimeoutError:
        # Kill the process if it takes too long
        logger.error("Timeout waiting for server script to complete")
        if proc.returncode is None:
            proc.kill()
        raise
    except Exception as e:
        logger.exception(f"Error running server script: {e}")
        if proc.returncode is None:
            proc.kill()
        raise


@pytest.mark.asyncio
async def test_direct_stdio_process() -> None:
    """Test direct communication with a stdio process.
    
    A simpler test to isolate the MCP stdio client functionality.
    """
    # Get path to the server script
    script_dir = Path(__file__).parent
    server_script_path = script_dir / "stdio_server_script.py"
    
    # Ensure the script is executable
    os.chmod(server_script_path, 0o755)
    
    # Start the server process directly
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_script_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    try:
        # Read the initial test message
        assert process.stdout is not None, "Failed to get stdout stream"
        line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        assert line, "No initial message received from server"
        
        # Parse the test message
        initial_msg = json.loads(line.decode("utf-8"))
        assert isinstance(initial_msg, dict), "Initial message is not valid JSON"
        assert initial_msg.get("method") == "test", "Unexpected message format"
        
        # Create a simple initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.2",
                "clientInfo": {
                    "name": "test_client",
                    "version": "1.0.0"
                },
                "capabilities": {}
            }
        }
        
        # Send the request
        logger.info(f"Sending initialize request")
        init_request_json = json.dumps(init_request) + "\n"
        assert process.stdin is not None, "Failed to get stdin stream"
        process.stdin.write(init_request_json.encode('utf-8'))
        await process.stdin.drain()
        
        # Read the response
        response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        response_text = response_line.decode('utf-8').strip()
        logger.info(f"Received response: {response_text}")
        
        # Parse and validate the response
        response = json.loads(response_text)
        assert response.get("id") == "init-1", "Response ID should match request ID"
        
        logger.info("Direct stdio process test successful")
    finally:
        # Cleanup
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()


def test_direct_communicator():
    """Test the basic functionality of the MCP stdio script.
    
    This is a non-async test that just verifies the script runs correctly.
    """
    # Get path to the server script
    script_dir = Path(__file__).parent
    server_script_path = script_dir / "stdio_server_script.py"
    
    # Ensure the script is executable
    os.chmod(server_script_path, 0o755)
    
    # Run the script with --test-only flag using regular subprocess module
    logger.info("Running server script with --test-only flag")
    result = subprocess.run(
        [sys.executable, str(server_script_path), "--test-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    
    # Log the output
    logger.info(f"Script exit code: {result.returncode}")
    logger.info(f"Script stdout: {result.stdout}")
    logger.info(f"Script stderr: {result.stderr}")
    
    # Verify we got the expected output
    assert result.returncode == 0, "Script should exit with code 0"
    assert "jsonrpc" in result.stdout, "Expected JSON-RPC message in stdout"
    assert "test" in result.stdout, "Expected test message in stdout"
    assert "Creating FastMCP server instance" in result.stderr, "Server initialization message not found"
    
    logger.info("Server script test passed successfully")


@asynccontextmanager
async def create_test_agent(script_path, agent_name="test_agent"):
    """Create and manage a test agent with proper setup and cleanup.
    
    Args:
        script_path: Path to the server script
        agent_name: Name for the agent
        
    Yields:
        The configured agent instance
    """
    # Register the MCP service
    service_url = sys.executable
    service_args = [str(script_path)]
    
    logger.info(f"Registering service for agent {agent_name}")
    register_communicator("mcp-stdio", McpStdioCommunicator)
    
    # Create an agent
    logger.info(f"Creating agent {agent_name}")
    agent = McpClientAgent(
        name=agent_name,
        communicator_type="mcp-stdio",
        services={"stdio_server": service_url},
        service_args={"stdio_server": service_args},
    )
    
    try:
        # Start the agent
        logger.info(f"Starting agent {agent_name}")
        await safe_async_operation(agent.start, timeout=CONNECTION_TIMEOUT)
        
        # Add a small delay to ensure agent is fully ready
        await asyncio.sleep(2.0)
        
        # Yield the agent for use in the test
        yield agent
        
    finally:
        # Clean up
        logger.info(f"Stopping agent {agent_name}")
        try:
            await safe_async_operation(agent.stop, timeout=CONNECTION_TIMEOUT)
            logger.info("Agent stopped")
        except Exception as e:
            logger.exception(f"Error stopping agent: {type(e).__name__}: {e}")
            # If agent failed to stop properly, attempt to force cleanup
            if hasattr(agent, "_communicators"):
                for comm in agent._communicators:
                    if isinstance(comm, McpStdioCommunicator) and hasattr(comm, "_processes"):
                        for proc_name, proc in comm._processes.items():
                            if proc and proc.returncode is None:
                                logger.warning(f"Forcibly terminating process {proc_name}")
                                proc.terminate()


@pytest.mark.asyncio
async def test_agent_with_direct_communicator() -> None:
    """Test an agent instance with the McpStdioCommunicator.
    
    Creates and registers the communicator, then creates an agent using it.
    """
    # Get path to the server script
    script_dir = Path(__file__).parent
    server_script_path = script_dir / "stdio_server_script.py"
    
    # Ensure the script is executable
    os.chmod(server_script_path, 0o755)
    
    # Use unique agent name to avoid conflicts
    unique_agent_name = f"test_agent_with_communicator_{time.time()}"
    
    # Use the context manager to create and manage the agent
    async with create_test_agent(server_script_path, agent_name=unique_agent_name) as agent:
        # The agent is now started with the communicator connected
        
        # Verify the communicator was created
        assert hasattr(agent, "_communicators"), "Agent doesn't have _communicators attribute"
        communicator = next(
            (c for c in agent._communicators if isinstance(c, McpStdioCommunicator)), None
        )
        assert communicator, "Agent doesn't have an McpStdioCommunicator"
        
        # Call the echo tool using our safe operation function
        logger.info("Calling echo tool through agent")
        result = await safe_async_operation(
            agent.call_tool,
            target_service="stdio_server",
            tool_name="echo",
            arguments={"message": "Hello agent with communicator"},
            timeout=OPERATION_TIMEOUT
        )
        
        # Verify the result
        assert result is not None, "No result received"
        assert "echoed" in result, f"No 'echoed' key in result: {result}"
        assert result["echoed"] == "Hello agent with communicator", f"Unexpected echo value: {result['echoed']}"
        
        logger.info("Agent with direct communicator test successful!")


@pytest.mark.asyncio
async def test_error_handling() -> None:
    """Test error handling in MCP communication."""
    # Get path to the server script
    script_dir = Path(__file__).parent
    server_script_path = script_dir / "stdio_server_script.py"
    
    # Ensure the script is executable
    os.chmod(server_script_path, 0o755)
    
    # Create communicator directly
    logger.info("Creating MCP stdio communicator")
    communicator = McpStdioCommunicator(
        agent_name="test_errors",
        service_urls={"stdio_server": sys.executable},
        service_args={"stdio_server": [str(server_script_path)]},
    )
    
    # Create client agent without specifying communicator type
    logger.info("Creating agent")
    client = McpClientAgent(
        name="test_errors",
        config={},  # Empty config to avoid auto-creating communicator
    )
    
    # Set our communicator on the agent
    client.set_communicator(communicator)
    
    try:
        # Start the agent
        logger.info("Starting agent for error handling test")
        await asyncio.wait_for(client.start(), timeout=CONNECTION_TIMEOUT)
        
        # Call a non-existent tool
        logger.info("Calling non-existent tool")
        with pytest.raises(Exception):
            await asyncio.wait_for(
                client.call_tool(
                    target_service="stdio_server",
                    tool_name="non_existent_tool",
                    arguments={"message": "test"},
                ),
                timeout=OPERATION_TIMEOUT
            )
            
        # Call a non-existent service
        logger.info("Calling non-existent service")
        with pytest.raises(Exception):
            await asyncio.wait_for(
                client.call_tool(
                    target_service="non_existent_service",
                    tool_name="echo",
                    arguments={"message": "test"},
                ),
                timeout=OPERATION_TIMEOUT
            )
            
        logger.info("Error handling tests passed!")
    finally:
        # Clean up
        logger.info("Stopping agent")
        try:
            await asyncio.wait_for(client.stop(), timeout=CONNECTION_TIMEOUT)
            logger.info("Agent stopped successfully")
        except Exception as e:
            logger.warning(f"Error during agent cleanup: {e}")


def register_mcp_stdio_service(service_name, service_url, service_args, agent_name):
    """Register an MCP stdio service for an agent.
    
    Helper function to register a service using the MCP stdio communicator.
    
    Args:
        service_name: Name of the service
        service_url: URL or command to start the service
        service_args: Arguments to pass to the service
        agent_name: Name of the agent to register the service for
    """
    # Ensure the communicator type is registered
    register_communicator("mcp-stdio", McpStdioCommunicator)
    
    # Configure the service
    from openmas.agent import configure_service
    
    # Register the service with the agent
    configure_service(
        agent_name=agent_name,
        service_name=service_name,
        service_url=service_url,
        service_args=service_args,
        communicator_type="mcp-stdio"
    )
    
    logger.debug(f"Registered MCP stdio service {service_name} for agent {agent_name}") 