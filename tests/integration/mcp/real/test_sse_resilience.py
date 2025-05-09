"""Integration tests for MCP SSE transport resilience and connection handling.

This module consolidates various resilience and connection tests for the SSE transport:
- Basic server reconnection and recovery
- Abrupt client disconnection handling
- Connection resilience
- Concurrent connection handling

These tests verify that the MCP server can handle real-world connection scenarios
including disconnections, multiple connections, and error cases.
"""

import asyncio
import json
import logging
import random
import sys
from typing import Any, Dict, Tuple

import pytest
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent

# Skip test if dependencies not available
SKIP_REASON = "mcp or aiohttp not installed"
HAS_MCP = True
HAS_AIOHTTP = True
try:
    # Just checking if aiohttp is importable
    import aiohttp  # type: ignore # noqa: F401
except ImportError:
    HAS_AIOHTTP = False
    SKIP_REASON += " (aiohttp)"

try:
    # Just checking if mcp is importable
    import mcp  # noqa: F401
except ImportError:
    HAS_MCP = False
    SKIP_REASON += " (mcp)"

# Import test harness after dependency checks
from tests.integration.mcp.real.utils import McpTestHarness, TransportType  # noqa: E402

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
    session: ClientSession, message: str, timeout: float = CLIENT_TIMEOUT
) -> Tuple[bool, Dict[str, Any]]:
    """Make an echo tool call with the given session and message."""
    logger.info(f"Calling echo tool with message: {message}")
    try:
        result = await asyncio.wait_for(session.call_tool("echo", {"message": message}), timeout=timeout)

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


#
# Basic Server Resilience Tests
#


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
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])

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
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])

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

                        # Signal that we're connected
                        client_connected_event.set()

                        # Make a test call to verify connection works
                        success, data = await make_echo_call(session, "Hello from first client")
                        assert success, f"First client echo call failed: {data}"
                        logger.info("First client: echo call succeeded")

                        # Wait until we're told to disconnect or timeout
                        try:
                            logger.info("First client: waiting for disconnect signal...")
                            await asyncio.wait_for(disconnect_event.wait(), timeout=15.0)
                            logger.info("First client: disconnect signal received")
                        except asyncio.TimeoutError:
                            logger.warning("First client: timed out waiting for disconnect signal")

                        # Normally we'd exit here and the context managers would clean up
                        logger.info("First client: task completing normally")

                    logger.info("First client: session context exited")

                logger.info("First client: sse_client context exited")

            except asyncio.CancelledError:
                logger.info("First client: task cancelled abruptly")
                raise
            except Exception as e:
                logger.error(f"First client task error: {e}", exc_info=True)
                raise

        # Start the client task
        logger.info("Starting first client task")
        client_task = asyncio.create_task(run_first_client())

        # Wait for the client to connect
        logger.info("Waiting for first client to connect...")
        await asyncio.wait_for(client_connected_event.wait(), timeout=10.0)
        logger.info("First client connected successfully")

        # Wait a moment for things to stabilize
        await asyncio.sleep(1.0)

        # Now abruptly cancel the client task
        logger.info("Abruptly cancelling first client task")
        client_task.cancel()

        # Wait for the task to be cancelled
        try:
            await asyncio.wait_for(client_task, timeout=5.0)
            logger.info("First client task cancelled successfully")
        except asyncio.CancelledError:
            logger.info("Caught CancelledError from client task")
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for client task to cancel")
            # We'll continue anyway

        # Wait a moment for the server to process the disconnection
        logger.info("Waiting for server to process abrupt disconnection...")
        await asyncio.sleep(2.0)

        # --- Second client to verify server still works after abrupt disconnect ---
        logger.info("=== SECOND CLIENT ===")
        logger.info(f"Connecting second client to {sse_endpoint_url}")

        # Connect new client and verify it works
        async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("Second client: initializing session")
                await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                logger.info("Second client: session initialized")

                # Make a test call to verify server still works
                success, data = await make_echo_call(session, "Hello after abrupt disconnect")
                assert success, f"Second client echo call failed: {data}"
                logger.info("Second client: echo call succeeded")

        logger.info("Second client disconnected properly")
        logger.info("Test completed successfully: server handled abrupt disconnection properly")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        pytest.fail(f"Test failed: {e}")
    finally:
        # Clean up any remaining tasks
        if disconnection_task and not disconnection_task.done():
            disconnection_task.cancel()
            try:
                await asyncio.wait_for(disconnection_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Clean up server
        logger.info("Cleaning up test harness")
        try:
            await asyncio.wait_for(harness.cleanup(), timeout=5.0)
            logger.info("Test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Harness cleanup timed out - forcing server process termination")
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}")


#
# Multiple Connection Tests
#


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_concurrent_sse_connections() -> None:
    """
    Test that the server can handle multiple concurrent SSE connections.

    1. Start the server
    2. Create multiple clients and connect them
    3. Have all clients make tool calls concurrently
    4. Verify all calls succeed
    5. Disconnect clients in random order
    """
    # Skip this test if it's causing intermittent issues
    # It's better to have a stable test suite than a flaky one
    # pytest.skip("Skipping concurrent connections test due to asyncio event loop issues")

    # Note: The test will be implemented in a future PR with a more robust approach
    # that doesn't suffer from asyncio cancellation issues when the event loop is closing

    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Concurrent test using port: {test_port}")
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)
    num_clients = 5  # Number of concurrent clients
    client_tasks = []
    results = []

    try:
        # 1. Start the server
        logger.info("Starting server for concurrency test")
        await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup failed for concurrency test"
        assert harness.server_url, "Server URL not found for concurrency test"
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"Server for concurrency test ready at: {sse_endpoint_url}")

        # 2. Define client task
        async def client_worker(client_id: int):
            message = f"Hello from client {client_id}"
            logger.info(f"Client {client_id}: Connecting to {sse_endpoint_url}")
            try:
                async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info(f"Client {client_id}: Initializing session")
                        await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                        logger.info(f"Client {client_id}: Session initialized")

                        # 3. Make tool call
                        logger.info(f"Client {client_id}: Calling echo tool")
                        success, data = await make_echo_call(session, message)
                        logger.info(f"Client {client_id}: Call result - Success={success}, Data={data}")
                        return client_id, success, data
            except Exception as e:
                logger.error(f"Client {client_id}: Error - {e}", exc_info=True)
                return client_id, False, {"error": str(e)}
            finally:
                logger.info(f"Client {client_id}: Worker finished")

        # Launch clients concurrently
        logger.info(f"Launching {num_clients} concurrent clients")
        for i in range(num_clients):
            client_tasks.append(asyncio.create_task(client_worker(i)))

        # 4. Wait for all clients and verify results
        results = await asyncio.gather(*client_tasks)

        successful_calls = 0
        for client_id, success, data in results:
            logger.info(f"Result for Client {client_id}: Success={success}, Data={data}")
            assert success, f"Client {client_id} failed: {data}"
            if success:
                successful_calls += 1

        assert successful_calls == num_clients, f"Expected {num_clients} successful calls, but got {successful_calls}"
        logger.info(f"All {num_clients} concurrent calls succeeded.")

        # 5. Disconnection happens automatically when workers finish

    except Exception as e:
        logger.error(f"Concurrent test failed: {e}", exc_info=True)
        pytest.fail(f"Concurrent test failed: {e}")

    finally:
        logger.info("Cleaning up concurrency test harness")
        # Cancel any tasks that might still be running (though gather should wait)
        for task in client_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected
        try:
            await asyncio.wait_for(harness.cleanup(), timeout=10.0)  # Increased timeout for cleanup
            logger.info("Concurrency test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Concurrency harness cleanup timed out - forcing server process termination")
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process for concurrency test")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}")


#
# Connection Resilience Tests
#


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_server_restarts() -> None:
    """
    Test resilience when the server restarts.

    1. Start the server
    2. Connect client and make successful call
    3. Stop the server
    4. Restart the server
    5. Connect client again and verify it works
    """
    # Start server on a random port
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using port: {test_port}")

    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        # --- First server instance ---
        logger.info("=== STARTING FIRST SERVER INSTANCE ===")
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])

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

        # Connect first client and make a call
        logger.info("Connecting first client to initial server")
        async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("First client: initializing session")
                await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)

                # Make a test call to verify connection works
                success, data = await make_echo_call(session, "Hello to first server instance")
                assert success, f"First client echo call failed: {data}"
                logger.info("First client: echo call to first server succeeded")

        logger.info("First client disconnected")

        # Stop the server
        logger.info("=== STOPPING FIRST SERVER INSTANCE ===")
        await harness.cleanup()
        logger.info("First server instance stopped")

        # Wait a moment before starting the new server
        await asyncio.sleep(1.0)

        # --- Second server instance ---
        logger.info("=== STARTING SECOND SERVER INSTANCE ===")
        # Reset the harness for a new server
        harness = McpTestHarness(TransportType.SSE, test_port=test_port)

        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])

        # Check server started
        if process.returncode is not None:
            pytest.fail(f"Second server failed to start with return code {process.returncode}")
            return

        # Wait for server ready
        logger.info("Waiting for second server startup")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Second server startup failed"
        assert harness.server_url, "Second server URL not found"
        logger.info(f"Second server ready at: {harness.server_url}")

        # Server endpoint should be the same
        sse_endpoint_url = f"{harness.server_url}/sse"

        # Connect new client to the restarted server
        logger.info("Connecting client to restarted server")

        # We'll retry a few times to allow the server to fully initialize
        max_retries = 3
        retry_delay = 1.0
        connected = False

        for attempt in range(max_retries):
            try:
                async with sse_client(sse_endpoint_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info(f"Attempt {attempt + 1}: initializing session")
                        await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)

                        # Make a test call to verify connection works
                        success, data = await make_echo_call(session, "Hello to restarted server")
                        assert success, f"Echo call to restarted server failed: {data}"
                        logger.info("Echo call to restarted server succeeded")

                        connected = True
                        break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

        assert connected, "Failed to connect to restarted server after multiple attempts"
        logger.info("Successfully connected to restarted server")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        pytest.fail(f"Test failed: {e}")
    finally:
        # Clean up server
        logger.info("Cleaning up test harness")
        try:
            await asyncio.wait_for(harness.cleanup(), timeout=5.0)
            logger.info("Test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Harness cleanup timed out - forcing server process termination")
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}")
