"""Integration tests for testing concurrent connections to MCP server via SSE transport."""

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

# Number of concurrent clients for testing
NUM_CONCURRENT_CLIENTS = 8
CLIENT_TIMEOUT = 20.0  # Timeout for each client operation in seconds


async def connect_and_call_echo(server_url: str, client_id: int, message: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Connect to the MCP server, initialize a session, and call the echo tool.

    Args:
        server_url: Base URL of the server (without /sse)
        client_id: Identifier for this client
        message: Message to send to the echo tool

    Returns:
        Tuple of (success, result_data)
    """
    sse_endpoint_url = f"{server_url}/sse"
    client_logger = logger.getChild(f"client_{client_id}")
    client_logger.info(f"Connecting to SSE endpoint: {sse_endpoint_url}")

    try:
        # Use async with for the transport client
        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            client_logger.info(f"SSE streams obtained for {sse_endpoint_url}")

            # Use async with for the ClientSession
            async with ClientSession(read_stream, write_stream) as session:
                client_logger.info("ClientSession created")

                # Initialize the session with a timeout
                try:
                    await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                    client_logger.info("Session initialized successfully")
                except asyncio.TimeoutError:
                    client_logger.error("Timeout initializing session")
                    return False, {"error": "Timeout initializing session"}
                except Exception as init_err:
                    client_logger.error(f"Error initializing session: {init_err}", exc_info=True)
                    return False, {"error": f"Initialization error: {init_err}"}

                # Add a short delay after initialization (can help with timing issues)
                await asyncio.sleep(0.1)

                # Call the echo tool
                params = {"message": f"{message} from client {client_id}"}
                client_logger.info(f"Calling 'echo' tool with params: {params}")
                try:
                    result = await asyncio.wait_for(session.call_tool("echo", params), timeout=CLIENT_TIMEOUT)
                    client_logger.info(f"Received result: {result}")

                    # Process result
                    if result and not result.isError and result.content:
                        if isinstance(result.content[0], TextContent):
                            response_text = result.content[0].text
                            client_logger.info(f"Tool response text: {response_text!r}")
                            try:
                                response_data = json.loads(response_text)
                                # Validate the response
                                expected_message = f"{message} from client {client_id}"
                                if response_data.get("echoed") == expected_message:
                                    return True, response_data
                                else:
                                    client_logger.error(
                                        f"Response data mismatch. Expected '{expected_message}', got '{response_data.get('echoed')}'"
                                    )
                                    return False, {"error": "Response data mismatch", "response": response_data}
                            except json.JSONDecodeError as json_err:
                                client_logger.error(f"JSON decode error: {json_err}")
                                return False, {"error": f"JSON decode error: {json_err}", "raw_response": response_text}
                        else:
                            client_logger.warning(f"Unexpected content type: {type(result.content[0])}")
                            return False, {"error": f"Unexpected content type: {type(result.content[0])}"}
                    elif result and result.isError:
                        client_logger.error(f"Tool call failed: {result.content}")
                        return False, {"error": "Tool call failed", "error_content": str(result.content)}
                    else:
                        client_logger.error("Tool call returned None or unexpected structure")
                        return False, {"error": "Tool call returned None or unexpected structure"}

                except asyncio.TimeoutError:
                    client_logger.error("Timeout calling tool")
                    return False, {"error": "Timeout calling tool"}
                except Exception as call_err:
                    client_logger.error(f"Error calling tool: {call_err}", exc_info=True)
                    return False, {"error": f"Error calling tool: {call_err}"}

    except ConnectionRefusedError:
        client_logger.error(f"Connection refused when connecting to {sse_endpoint_url}")
        return False, {"error": f"Connection refused to {sse_endpoint_url}"}
    except Exception as conn_err:
        client_logger.error(f"Error during SSE client connection: {conn_err}", exc_info=True)
        return False, {"error": f"Connection error: {conn_err}"}


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_concurrent_sse_connections() -> None:
    """
    Test multiple clients connecting concurrently to the MCP server via SSE.

    This test simulates multiple clients connecting simultaneously to verify
    that the server can handle concurrent connections without errors or hangs.
    """
    # Use a random port to avoid conflicts with other tests
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port}")

    # Create test harness for SSE
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        # Start server subprocess
        logger.info("Starting server subprocess")
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])

        # Basic check if process started immediately
        if process.returncode is not None:
            pytest.fail(f"Process failed to start with return code {process.returncode}")
            return

        # Wait for server to be ready
        logger.info("Server process started, waiting for readiness signal & HTTP check...")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed (check harness logs)"
        assert harness.server_url, "Server URL not found via harness"
        logger.info(f"Server ready, URL: {harness.server_url}")

        # Create concurrent client tasks
        tasks = []
        base_message = "Hello MCP"
        server_url = harness.server_url

        # Create tasks for each client
        for client_id in range(NUM_CONCURRENT_CLIENTS):
            task = connect_and_call_echo(server_url, client_id, base_message)
            tasks.append(task)

        logger.info(f"Created {len(tasks)} client tasks")

        # Run all client tasks concurrently
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()

        logger.info(f"All client tasks completed in {end_time - start_time:.2f} seconds")

        # Verify results from all clients
        success_count = 0
        failure_details = []

        for i, result in enumerate(results):
            # Handle any exceptions raised during task execution
            if isinstance(result, Exception):
                logger.error(f"Client {i} task raised exception: {result}")
                failure_details.append(f"Client {i}: Exception - {result}")
                continue

            success, data = result
            if success:
                success_count += 1
                logger.info(f"Client {i} succeeded with data: {data}")
            else:
                logger.error(f"Client {i} failed with data: {data}")
                failure_details.append(f"Client {i}: {data.get('error', 'Unknown error')}")

        # Assert that all clients succeeded
        if success_count < NUM_CONCURRENT_CLIENTS:
            failure_summary = "\n".join(failure_details)
            pytest.fail(f"{NUM_CONCURRENT_CLIENTS - success_count} clients failed:\n{failure_summary}")
        else:
            logger.info(f"All {NUM_CONCURRENT_CLIENTS} clients succeeded")

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # Ensure cleanup of server process
        logger.info("Cleaning up test harness...")
        await harness.cleanup()
        logger.info("Test harness cleaned up")
