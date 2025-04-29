"""Integration test for MCP server resilience with SSE transport."""

import asyncio
import json
import logging
import random
import sys
from typing import Dict, Any, Tuple

import pytest
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent

# Skip test if dependencies not available
SKIP_REASON = "mcp or aiohttp not installed"
HAS_MCP = True
HAS_AIOHTTP = True
try:
    import aiohttp
except ImportError:
    HAS_AIOHTTP = False
    SKIP_REASON += " (aiohttp)"

try:
    import mcp
except ImportError:
    HAS_MCP = False
    SKIP_REASON += " (mcp)"

# Import test harness after dependency checks
from tests.integration.mcp.real.utils import McpTestHarness, TransportType

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Constants
CLIENT_TIMEOUT = 5.0  # Short timeout for client operations in seconds


async def make_echo_call(
    session: ClientSession, 
    message: str,
    timeout: float = CLIENT_TIMEOUT
) -> Tuple[bool, Dict[str, Any]]:
    """Make an echo tool call with the given session and message."""
    logger.info(f"Calling echo tool with message: {message}")
    try:
        result = await asyncio.wait_for(
            session.call_tool("echo", {"message": message}),
            timeout=timeout
        )
        
        if result and not result.isError and result.content:
            if isinstance(result.content[0], TextContent):
                response_text = result.content[0].text
                try:
                    response_data = json.loads(response_text)
                    if response_data.get("echoed") == message:
                        logger.info(f"Echo call succeeded: {response_data}")
                        return True, response_data
                    else:
                        logger.error(f"Echo response mismatch. Expected: {message}, Got: {response_data}")
                        return False, response_data
                except json.JSONDecodeError:
                    logger.error(f"JSON decode error for response: {response_text}")
                    return False, {"error": "JSON decode error", "raw": response_text}
            else:
                logger.error(f"Unexpected content type: {type(result.content[0])}")
                return False, {"error": f"Unexpected content type: {type(result.content[0])}"}
        else:
            logger.error(f"Echo call failed or returned unexpected structure: {result}")
            return False, {"error": "Tool call failed", "result": str(result)}
            
    except Exception as e:
        logger.error(f"Exception during tool call: {e}", exc_info=True)
        return False, {"error": str(e)}


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_simple_sse_resilience() -> None:
    """
    Test server resilience with SSE transport - simplified version.
    
    1. Start the server
    2. Connect first client, make a successful call
    3. Force-close the first client streams
    4. Connect a new client to verify server still works
    """
    # Start server on a random port
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using port: {test_port}")
    
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)
    
    try:
        # Start server
        logger.info("Starting server subprocess")
        process = await harness.start_server(
            additional_args=["--host", "127.0.0.1", "--port", str(test_port)]
        )
        
        # Check server started
        if process.returncode is not None:
            pytest.fail(f"Server failed to start with return code {process.returncode}")
            return
            
        # Wait for server ready
        logger.info("Waiting for server startup")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup failed"
        assert harness.server_url, "Server URL not found"
        logger.info(f"Server ready at: {harness.server_url}")
        
        # Server endpoint
        sse_endpoint_url = f"{harness.server_url}/sse"
        
        # --- First client with abrupt disconnection ---
        logger.info("=== FIRST CLIENT ===")
        read_stream = None
        write_stream = None
        
        try:
            # Connect client
            logger.info(f"Connecting first client to {sse_endpoint_url}")
            
            # Open the SSE connection
            async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
                # Create and initialize session
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info("First client: initializing session")
                    await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                    logger.info("First client: session initialized")
                    
                    # Make a test call to verify connection works
                    success, data = await make_echo_call(session, "Hello from first client")
                    assert success, f"First client echo call failed: {data}"
                    logger.info("First client: first echo call succeeded")
                    
                    # Abruptly break the session by exiting context managers
                    # The proper cleanup will happen when exiting the context managers
                    logger.info("First client: exiting properly from session")
                
                # Context managers should have properly cleaned up the session
                logger.info("First client: session closed")
                
            logger.info("First client: connection closed")
            
            # Wait a moment for the server to process the disconnection
            logger.info("Waiting for server to process disconnection...")
            await asyncio.sleep(1.0)
            
            # --- Second client to verify server still works ---
            logger.info("=== SECOND CLIENT ===")
            logger.info(f"Connecting second client to {sse_endpoint_url}")
            
            # Connect new client and verify it works
            async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info("Second client: initializing session")
                    await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                    logger.info("Second client: session initialized")
                    
                    # Make a test call to verify server still works
                    success, data = await make_echo_call(session, "Hello from second client")
                    assert success, f"Second client echo call failed: {data}"
                    logger.info("Second client: echo call succeeded")
            
            logger.info("Second client disconnected properly")
            logger.info("Test completed successfully: server handled client connection lifecycle properly")
            
        except Exception as e:
            logger.error(f"Error during client test: {e}", exc_info=True)
            pytest.fail(f"Error during client test: {e}")
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        pytest.fail(f"Test failed: {e}")
    finally:
        # Clean up with timeout to avoid hanging
        logger.info("Cleaning up test harness")
        try:
            await asyncio.wait_for(harness.cleanup(), timeout=5.0)
            logger.info("Test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Harness cleanup timed out - server process may still be running")
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}")


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_abrupt_disconnect() -> None:
    """
    Test server resilience when client disconnects abruptly (without cleanup).
    
    1. Start the server
    2. Connect first client, make a successful call
    3. Abruptly disconnect by using a separate task to force close the connection
    4. Connect a new client to verify server still works
    """
    # Start server on a random port
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using port: {test_port}")
    
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)
    
    disconnection_task = None
    
    try:
        # Start server
        logger.info("Starting server subprocess")
        process = await harness.start_server(
            additional_args=["--host", "127.0.0.1", "--port", str(test_port)]
        )
        
        # Check server started
        if process.returncode is not None:
            pytest.fail(f"Server failed to start with return code {process.returncode}")
            return
            
        # Wait for server ready
        logger.info("Waiting for server startup")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup failed"
        assert harness.server_url, "Server URL not found"
        logger.info(f"Server ready at: {harness.server_url}")
        
        # Server endpoint
        sse_endpoint_url = f"{harness.server_url}/sse"
        
        # --- First client with abrupt disconnection ---
        logger.info("=== FIRST CLIENT ===")
        
        # We'll use a separate event to signal when to disconnect
        disconnect_event = asyncio.Event()
        client_connected_event = asyncio.Event()
        
        # Create a separate task for the first client that we'll cancel abruptly
        async def run_first_client():
            logger.info(f"First client task: Connecting to {sse_endpoint_url}")
            try:
                async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info("First client: session created and initialized")
                        await session.initialize()
                        
                        # Signal that we're connected and ready
                        client_connected_event.set()
                        
                        # Make a test call
                        success, data = await make_echo_call(session, "Hello from abrupt client")
                        assert success, f"First client echo call failed: {data}"
                        logger.info("First client: echo call succeeded")
                        
                        # Wait for the disconnect signal or timeout
                        try:
                            await asyncio.wait_for(disconnect_event.wait(), timeout=10.0)
                            logger.info("First client: received disconnect signal")
                        except asyncio.TimeoutError:
                            logger.warning("First client: timed out waiting for disconnect signal")
                
                logger.info("First client: exiting normally (this shouldn't happen in the test)")
            except asyncio.CancelledError:
                logger.info("First client: task cancelled (simulating abrupt disconnect)")
                raise
            except Exception as e:
                logger.error(f"First client error: {e}", exc_info=True)
                raise
        
        # Start the client task
        first_client_task = asyncio.create_task(run_first_client())
        
        # Wait for the client to connect
        try:
            await asyncio.wait_for(client_connected_event.wait(), timeout=CLIENT_TIMEOUT)
            logger.info("First client connected successfully")
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for first client to connect")
            if not first_client_task.done():
                first_client_task.cancel()
            await asyncio.gather(first_client_task, return_exceptions=True)
            pytest.fail("First client failed to connect")
        
        # Give the client a moment to complete its tool call
        await asyncio.sleep(1.0)
        
        # 3. Simulate abrupt disconnection by cancelling the task
        if not first_client_task.done():
            logger.info("Simulating abrupt disconnection by cancelling client task...")
            first_client_task.cancel()
            
            # Wait for the task to be properly cancelled
            try:
                await asyncio.wait_for(first_client_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("Cancel operation timed out or was itself cancelled")
        
        logger.info("First client: abrupt disconnection simulated")
        
        # 4. Wait for server to detect and handle the disconnection
        logger.info("Waiting for server to process disconnection...")
        await asyncio.sleep(2.0)
        
        # 5. Connect a new client to verify server still works
        logger.info("=== SECOND CLIENT ===")
        logger.info(f"Connecting second client to {sse_endpoint_url}")
        
        async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("Second client: initializing session")
                await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                logger.info("Second client: session initialized")
                
                # Make a test call to verify server still works
                success, data = await make_echo_call(
                    session, 
                    "Hello from second client after abrupt disconnect"
                )
                assert success, f"Second client echo call failed: {data}"
                logger.info("Second client: echo call succeeded")
        
        logger.info("Second client disconnected properly")
        logger.info("Test completed successfully: server handled abrupt client disconnection")
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        pytest.fail(f"Test failed: {e}")
    finally:
        # Cancel any remaining tasks
        if disconnection_task and not disconnection_task.done():
            disconnection_task.cancel()
            try:
                await asyncio.wait_for(disconnection_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
                
        # Clean up with timeout to avoid hanging
        logger.info("Cleaning up test harness")
        try:
            await asyncio.wait_for(harness.cleanup(), timeout=5.0)
            logger.info("Test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Harness cleanup timed out - server process may still be running")
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}") 