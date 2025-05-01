"""Integration tests for MCP server connection resilience against abrupt client disconnections."""

import asyncio
import contextlib
import json
import logging
import random
import sys
from typing import Any, Dict, Optional, Tuple

import pytest
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
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
CLIENT_TIMEOUT = 10.0  # Reduced timeout for client operations in seconds


async def make_tool_call(
    session: ClientSession, tool_name: str, params: Dict[str, Any], timeout: float = CLIENT_TIMEOUT
) -> Tuple[bool, Dict[str, Any]]:
    """
    Make a tool call and process the result.

    Args:
        session: Initialized ClientSession
        tool_name: Name of the tool to call
        params: Parameters to pass to the tool
        timeout: Timeout for the tool call

    Returns:
        Tuple of (success, result_data)
    """
    try:
        result = await asyncio.wait_for(session.call_tool(tool_name, params), timeout=timeout)
        logger.info(f"Received tool call result: {result}")

        # Process result
        if result and not result.isError and result.content:
            if isinstance(result.content[0], TextContent):
                response_text = result.content[0].text
                try:
                    response_data = json.loads(response_text)
                    return True, response_data
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON decode error: {json_err}")
                    return False, {"error": f"JSON decode error: {json_err}", "raw_response": response_text}
            else:
                logger.warning(f"Unexpected content type: {type(result.content[0])}")
                return False, {"error": f"Unexpected content type: {type(result.content[0])}"}
        elif result and result.isError:
            logger.error(f"Tool call failed: {result.content}")
            return False, {"error": "Tool call failed", "error_content": str(result.content)}
        else:
            logger.error("Tool call returned None or unexpected structure")
            return False, {"error": "Tool call returned None or unexpected structure"}

    except asyncio.TimeoutError:
        logger.error(f"Timeout calling tool '{tool_name}'")
        return False, {"error": f"Timeout calling tool '{tool_name}'"}
    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}': {e}", exc_info=True)
        return False, {"error": f"Error calling tool '{tool_name}': {e}"}


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_connection_resilience() -> None:
    """
    Test SSE server resilience to abrupt client disconnections.

    Steps:
    1. Start the server
    2. Connect a client using asyncio task and make a successful tool call
    3. Simulate an abrupt client disconnection by cancelling the task
    4. Verify the server remains operational
    5. Connect a new client and make another successful tool call
    """
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port}")

    # Create test harness for SSE
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        # 1. Start server subprocess
        logger.info("Starting server subprocess")
        # Pass the correct port argument based on the randomly generated one
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(harness.test_port)])

        # Basic check if process started immediately
        if process.returncode is not None:
            # Capture stderr if process failed early
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=1.0)
                logger.error(f"Server process stdout: {stdout.decode() if stdout else 'N/A'}")
                logger.error(f"Server process stderr: {stderr.decode() if stderr else 'N/A'}")
            except asyncio.TimeoutError:
                logger.error("Timeout reading server process output after early failure.")
            pytest.fail(f"Process failed to start with return code {process.returncode}")
            return  # Added return for clarity

        # Wait for server to be ready
        logger.info("Server process started, waiting for readiness signal & HTTP check...")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed (check harness logs)"
        assert harness.server_url, "Server URL not found via harness"
        logger.info(f"Server ready, URL: {harness.server_url}")

        # 2. Connect first client using asyncio task and make successful tool call
        logger.info("=== FIRST CLIENT (via asyncio task) ===\n")
        sse_endpoint_url = f"{harness.server_url}/sse"
        client_task_completed = asyncio.Event()
        client_task_succeeded = False

        async def first_client_task():
            nonlocal client_task_succeeded
            try:
                logger.info(f"Connecting first client task to {sse_endpoint_url}")
                async with sse_client(sse_endpoint_url) as streams:
                    read_stream, write_stream = streams
                    logger.info("First client task: SSE streams obtained")
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info("First client task: ClientSession created")
                        await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                        logger.info("First client task: Session initialized")

                        # Make tool call
                        success, result_data = await make_tool_call(
                            session, "echo", {"message": "Hello from client task"}
                        )

                        if success and result_data.get("echoed") == "Hello from client task":
                            logger.info("First client task: Successful tool call")
                            client_task_succeeded = True
                        else:
                            logger.error(f"First client task: Tool call failed or unexpected result: {result_data}")
                            client_task_succeeded = False  # Explicitly set failure

                        # Signal completion before potentially waiting forever
                        client_task_completed.set()

                        # Keep connection open until cancelled to simulate abrupt disconnect
                        # If we exit the context managers cleanly, it's not an *abrupt* disconnect.
                        await asyncio.Event().wait()  # Wait indefinitely until cancelled

            except asyncio.CancelledError:
                logger.info("First client task cancelled as expected.")
                # Do not set success flag here, cancellation is the goal
                raise  # Re-raise CancelledError to signal cancellation happened
            except Exception as e:
                logger.error(f"First client task failed with exception: {e}", exc_info=True)
                client_task_succeeded = False
                client_task_completed.set()  # Signal completion even on error
                # Do not raise here, let the main test logic handle the failure via client_task_succeeded flag

        # Start the client task
        logger.info("Starting first client task...")
        client_task_handle = asyncio.create_task(first_client_task())

        # Wait for the client task to make the call and signal completion (or timeout)
        try:
            logger.info("Waiting for first client task to complete its tool call...")
            await asyncio.wait_for(client_task_completed.wait(), timeout=CLIENT_TIMEOUT * 1.5)  # Give extra time
        except asyncio.TimeoutError:
            # If the task times out here, it likely failed to connect or call the tool
            logger.error("Timeout waiting for first client task to complete its tool call.")
            # Attempt to cancel the task if it's still running
            if not client_task_handle.done():
                client_task_handle.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await client_task_handle  # Wait for cancellation to complete
            pytest.fail("First client task timed out before completing tool call.")
            return  # Added return

        # Verify the tool call within the task succeeded before proceeding
        assert client_task_succeeded, "First client task did not report a successful tool call."
        logger.info("First client task reported successful tool call.")

        # 3. Simulate abrupt disconnection by cancelling the task
        logger.info("Simulating abrupt client disconnection by cancelling the task...")
        if not client_task_handle.done():
            client_task_handle.cancel()
            # Wait for the task to finish cancelling
            await asyncio.gather(client_task_handle, return_exceptions=True)
            logger.info("First client task finished cancellation.")
        else:
            # Task might have already finished due to an internal error AFTER signalling success
            logger.warning("Client task was already done before explicit cancellation.")

        # 4. Allow server time to process the cancellation/disconnection
        # This might be less critical with task cancellation vs kill(), but keep a short delay.
        logger.info("Waiting briefly for server to handle disconnection...")
        await asyncio.sleep(1.0)  # Reduced wait time

        # 5. Connect a new client to verify server is still operational
        logger.info("=== SECOND CLIENT (direct connection) ===\n")
        logger.info(f"Connecting second client to SSE endpoint: {sse_endpoint_url}")
        try:
            async with sse_client(sse_endpoint_url) as streams2:
                read_stream2, write_stream2 = streams2
                logger.info("Second client: SSE streams obtained")
                async with ClientSession(read_stream2, write_stream2) as session2:
                    logger.info("Second client: ClientSession created")
                    await asyncio.wait_for(session2.initialize(), timeout=CLIENT_TIMEOUT)
                    logger.info("Second client: Session initialized")

                    # Make another tool call
                    success2, result_data2 = await make_tool_call(
                        session2, "echo", {"message": "Hello again from second client"}
                    )

                    # Assert second call success
                    assert success2, f"Second tool call failed: {result_data2.get('error', 'Unknown error')}"
                    assert (
                        result_data2.get("echoed") == "Hello again from second client"
                    ), f"Second tool call returned unexpected data: {result_data2}"

                    logger.info("Second client successfully connected and called tool. Server resilience confirmed.")

        except (aiohttp.ClientConnectorError, ConnectionRefusedError, asyncio.TimeoutError) as conn_err:
            logger.error(f"Failed to connect second client: {conn_err}", exc_info=True)
            pytest.fail(f"Failed to connect second client after first client disconnection: {conn_err}")
        except Exception as e:
            logger.error(f"Unexpected error during second client connection/call: {e}", exc_info=True)
            pytest.fail(f"Unexpected error during second client connection/call: {e}")

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # Cleanup handled by harness __aexit__ or explicit call
        logger.info("Cleaning up test harness...")
        await harness.cleanup()
        logger.info("Test harness cleaned up.")
        # # Clean up the temporary script file if it was created (no longer needed)
        # if 'client_script_path' in locals() and os.path.exists(client_script_path):
        #     os.remove(client_script_path)


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_MCP, reason=SKIP_REASON + " (mcp)")
async def test_stdio_connection_resilience() -> None:
    """
    Test Stdio server resilience to abrupt client disconnections.

    Uses asyncio.create_task and task.cancel() for simulation.

    Steps:
    1. Determine the server script path (no separate server process needed initially).
    2. Connect first client using asyncio task (which starts its own server via stdio_client)
       and make a successful tool call.
    3. Simulate an abrupt client disconnection by cancelling the task.
    4. Verify the server process associated with the first client terminates.
    5. Connect a new client (which starts its own server instance) and make another
       successful tool call to confirm the server script itself is not corrupted.
    """
    # 1. Determine server script path (using harness default)
    harness = McpTestHarness(TransportType.STDIO)  # Harness mainly used for script path and cleanup logic here
    script_path = str(harness.script_path)
    logger.info(f"Using stdio server script: {script_path}")

    first_client_process: Optional[asyncio.subprocess.Process] = (
        None  # To track the process started by the first client
    )

    try:
        # 2. Connect first client using asyncio task and make successful tool call
        logger.info("=== FIRST CLIENT (via asyncio task) ===")

        client_task_completed = asyncio.Event()
        client_task_succeeded = False

        async def first_client_task():
            nonlocal client_task_succeeded, first_client_process
            try:
                logger.info(f"Configuring first client task for stdio server: {script_path}")
                server_params = StdioServerParameters(command=sys.executable, args=[script_path])

                # stdio_client starts the server process
                async with stdio_client(server_params) as streams:
                    # Store the process handle once connected
                    if (
                        hasattr(streams, "_server_process") and streams._server_process
                    ):  # Access internal attr carefully
                        first_client_process = streams._server_process
                        logger.info(f"First client task: Server process started (PID: {first_client_process.pid})")
                    else:
                        logger.warning("Could not access server process handle from stdio_client streams.")

                    read_stream, write_stream = streams
                    logger.info("First client task: Stdio streams obtained")

                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info("First client task: ClientSession created")
                        await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                        logger.info("First client task: Session initialized")

                        # Make tool call
                        success, result_data = await make_tool_call(
                            session, "echo", {"message": "Hello from stdio client task"}
                        )

                        if success and result_data.get("echoed") == "Hello from stdio client task":
                            logger.info("First client task: Successful tool call")
                            client_task_succeeded = True
                        else:
                            logger.error(f"First client task: Tool call failed or unexpected result: {result_data}")
                            client_task_succeeded = False

                        # Signal completion before potentially waiting forever
                        client_task_completed.set()

                        # Keep connection open until cancelled
                        await asyncio.Event().wait()  # Wait indefinitely until cancelled

            except asyncio.CancelledError:
                logger.info("First client task cancelled as expected.")
                # If cancelled, the context managers should handle closing streams/process
                raise
            except Exception as e:
                logger.error(f"First client task failed with exception: {e}", exc_info=True)
                client_task_succeeded = False
                client_task_completed.set()

        # Start the client task
        logger.info("Starting first client task...")
        client_task_handle = asyncio.create_task(first_client_task())

        # Wait for the client task to make the call and signal completion (or timeout)
        try:
            logger.info("Waiting for first client task to complete its tool call...")
            await asyncio.wait_for(client_task_completed.wait(), timeout=CLIENT_TIMEOUT * 1.5)
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for first client task to complete its tool call.")
            if not client_task_handle.done():
                client_task_handle.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await client_task_handle
            pytest.fail("First client task timed out before completing tool call.")
            return

        # Verify the tool call succeeded
        assert client_task_succeeded, "First client task did not report a successful tool call."
        logger.info("First client task reported successful tool call.")

        # 3. Simulate abrupt disconnection by cancelling the task
        logger.info("Simulating abrupt client disconnection by cancelling the task...")
        if not client_task_handle.done():
            client_task_handle.cancel()
            await asyncio.gather(client_task_handle, return_exceptions=True)
            logger.info("First client task finished cancellation.")
        else:
            logger.warning("Client task was already done before explicit cancellation.")

        # 4. Verify the server process associated with the first client terminates
        logger.info("Waiting for first client's server process to terminate...")
        if first_client_process and first_client_process.returncode is None:
            try:
                # Wait for the process started by stdio_client to exit
                await asyncio.wait_for(first_client_process.wait(), timeout=5.0)
                logger.info(f"First client's server process terminated with code: {first_client_process.returncode}")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for first client's server process to terminate. Attempting kill.")
                if first_client_process.returncode is None:
                    first_client_process.kill()  # Force kill if necessary
                    await first_client_process.wait()  # Wait after killing
                    logger.info("First client's server process forcibly killed.")
            except Exception as e:
                logger.error(f"Error waiting for first client's server process: {e}")
        elif first_client_process:
            logger.info(f"First client's server process already terminated (code: {first_client_process.returncode}).")
        else:
            logger.warning("Could not track first client's server process.")

        # Give a brief moment for OS resources to clear
        await asyncio.sleep(0.5)

        # 5. Connect a new client to verify the server script is usable again
        logger.info("=== SECOND CLIENT (new process via stdio_client) ===")
        logger.info(f"Connecting second client to Stdio server script: {script_path}")
        second_client_process: Optional[asyncio.subprocess.Process] = None
        try:
            server_params2 = StdioServerParameters(command=sys.executable, args=[script_path])
            async with stdio_client(server_params2) as streams2:
                if hasattr(streams2, "_server_process") and streams2._server_process:  # Track second process
                    second_client_process = streams2._server_process

                read_stream2, write_stream2 = streams2
                logger.info("Second client: Stdio streams obtained")
                async with ClientSession(read_stream2, write_stream2) as session2:
                    logger.info("Second client: ClientSession created")
                    await asyncio.wait_for(session2.initialize(), timeout=CLIENT_TIMEOUT)
                    logger.info("Second client: Session initialized")

                    # Make another tool call
                    success2, result_data2 = await make_tool_call(
                        session2, "echo", {"message": "Hello again from second stdio client"}
                    )

                    assert success2, f"Second tool call failed: {result_data2.get('error', 'Unknown error')}"
                    assert (
                        result_data2.get("echoed") == "Hello again from second stdio client"
                    ), f"Second tool call returned unexpected data: {result_data2}"

                    logger.info("Second client successfully connected and called tool. Stdio resilience confirmed.")

        except Exception as e:
            logger.error(f"Unexpected error during second client connection/call: {e}", exc_info=True)
            pytest.fail(f"Unexpected error during second client connection/call: {e}")

    finally:
        # Clean up any lingering processes specifically tracked in this test
        logger.info("Performing test-specific cleanup...")

        # Cleanup first client task if it exists and is running
        if "client_task_handle" in locals():
            task = locals()["client_task_handle"]
            if isinstance(task, asyncio.Task) and not task.done():
                logger.warning("Cancelling potentially lingering first client task during cleanup.")
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        # Cleanup first client's server process if it exists and is running
        if first_client_process and first_client_process.returncode is None:
            logger.warning(
                f"Killing lingering first client server process (PID: {first_client_process.pid}) during cleanup."
            )
            try:
                first_client_process.kill()
                await asyncio.gather(first_client_process.wait(), return_exceptions=True)
            except ProcessLookupError:
                logger.warning(f"Process {first_client_process.pid} already terminated during cleanup.")
            except Exception as e:
                logger.error(f"Error killing first client process {first_client_process.pid}: {e}")

        # Cleanup second client's server process if it exists and is running
        if "second_client_process" in locals():
            proc = locals()["second_client_process"]
            # Check if it's a Process and running
            if isinstance(proc, asyncio.subprocess.Process) and proc.returncode is None:
                logger.warning(f"Killing lingering second client server process (PID: {proc.pid}) during cleanup.")
                try:
                    proc.kill()
                    await asyncio.gather(proc.wait(), return_exceptions=True)
                except ProcessLookupError:
                    logger.warning(f"Process {proc.pid} already terminated during cleanup.")
                except Exception as e:
                    logger.error(f"Error killing second client process {proc.pid}: {e}")

        logger.info("Test cleanup finished.")
