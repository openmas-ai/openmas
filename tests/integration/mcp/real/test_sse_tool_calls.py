"""Integration tests for SSE transport with MCP tool calls."""

# openmas/tests/integration/mcp/test_sse_tool_calls.py

import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import ListToolsResult, TextContent

# Fix E402: Move dependency checks and utils import to the top
SKIP_REASON = "mcp or aiohttp not installed"
HAS_MCP = True
HAS_AIOHTTP = True
try:
    # Fix F401: Comment out direct aiohttp import as it's only used in utils.py
    import aiohttp  # type: ignore # noqa: F401
except ImportError:
    HAS_AIOHTTP = False
    SKIP_REASON += " (aiohttp)"

try:
    # Check for MCP installation
    import mcp  # noqa: F401
except ImportError:
    HAS_MCP = False
    SKIP_REASON += " (mcp)"

# Ensure this import is AFTER the dependency checks
from tests.integration.mcp.real.utils import McpTestHarness, TransportType  # noqa: E402

logger = logging.getLogger(__name__)

# Determine the path to the server script dynamically
_current_dir = Path(__file__).parent
_server_script_path = _current_dir / "sse_server_script.py"

# Configure detailed logging (moved below imports and path setup)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr,
)


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_echo_basic_types() -> None:
    """Test the echo tool with various basic parameter types."""
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port}")
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)
    # No need to define client_manager here anymore

    try:
        # Start the server subprocess
        logger.info("Starting server subprocess")
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])
        # Check if process started successfully (basic check)
        if process.returncode is not None:
            stderr_output = ""
            if process.stderr:
                stderr_data = await process.stderr.read()
                stderr_output = stderr_data.decode("utf-8") if stderr_data else ""
            logger.error(f"Process failed to start with return code {process.returncode}")
            logger.error(f"Process stderr: {stderr_output}")
            pytest.fail(f"Process failed to start with return code {process.returncode}")
            return  # Exit test if process failed

        logger.info("Server process started, waiting for readiness signal...")

        # Wait for the server to signal readiness via stderr & HTTP check
        startup_ok = await harness.verify_server_startup(timeout=15.0)  # Increased timeout
        assert startup_ok, "Server startup verification failed (check harness logs)"
        assert harness.server_url, "Server URL not found via harness after startup verification"
        logger.info(f"Server ready, URL: {harness.server_url}")

        # Construct the target URL explicitly with the /sse endpoint
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"Connecting to SSE endpoint: {sse_endpoint_url}")

        async def check_echo(session: ClientSession, input_value: Any, expected_echoed_value: Any) -> None:
            """Helper function to call echo tool and verify the response."""
            logger.info(
                f"Testing echo with input: {input_value!r} (type: {type(input_value)}), expecting echoed: {expected_echoed_value!r}"
            )
            result = await asyncio.wait_for(session.call_tool("echo", {"message": input_value}), timeout=15.0)
            logger.debug(f"Echo raw result: {result}")

            # Basic verification
            assert result is not None, f"Result is None for input {input_value!r}"
            assert not result.isError, f"Result indicates error for input {input_value!r}: {result.content}"
            assert (
                result.content is not None and len(result.content) > 0
            ), f"Result content is missing or empty for input {input_value!r}"
            text_content = result.content[0]
            assert isinstance(text_content, TextContent), f"Result content is not TextContent for input {input_value!r}"

            # Parse and check JSON response from the text content
            response_text = text_content.text
            logger.debug(f"Response text content for {input_value!r}: {response_text!r}")
            try:
                response_data = json.loads(response_text)
                assert isinstance(response_data, dict), f"Parsed response is not a dictionary for input {input_value!r}"
                assert (
                    "echoed" in response_data
                ), f"'echoed' key missing in response JSON for input {input_value!r}: {response_data}"
                assert (
                    response_data["echoed"] == expected_echoed_value
                ), f"Echoed value mismatch for input {input_value!r}. Expected {expected_echoed_value!r}, got {response_data['echoed']!r}"
                logger.info(f"Assertion passed for input: {input_value!r}")
            except (json.JSONDecodeError, AssertionError, TypeError) as e:
                logger.error(f"Echo verification failed for input {input_value!r}: {e}")
                pytest.fail(f"Echo verification failed for {input_value!r}: {e}. Response text was: {response_text!r}")

        # --- Start Client Connection ---
        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            logger.info(f"SSE client streams obtained for {sse_endpoint_url} via async with")

            async with ClientSession(read_stream, write_stream) as session:
                logger.info("MCP ClientSession created")
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                logger.info("MCP session initialized successfully")
                await asyncio.sleep(0.1)  # Brief pause after init

                # === Test Cases ===
                await check_echo(session, "Hello, MCP!", "Hello, MCP!")  # String
                await check_echo(session, 42, 42)  # Integer
                await check_echo(session, -100, -100)  # Negative Integer
                await check_echo(session, 0, 0)  # Zero Integer
                await check_echo(session, 3.14159, 3.14159)  # Float
                await check_echo(session, -0.5, -0.5)  # Negative Float
                await check_echo(session, 0.0, 0.0)  # Zero Float
                await check_echo(session, True, True)  # Boolean True
                await check_echo(session, False, False)  # Boolean False
                await check_echo(session, None, None)  # Null/None
                # === End Test Cases ===

    except ConnectionRefusedError:
        logger.error(f"Connection refused when connecting to {sse_endpoint_url}. Is the server running?")
        pytest.fail(f"Connection refused to {sse_endpoint_url}")
    except asyncio.TimeoutError as e:
        logger.error(f"Test timed out: {e}", exc_info=True)
        pytest.fail(f"Test timed out: {e}")
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        # Ensure harness cleanup even on unexpected test errors
        try:
            await harness.cleanup()
        except Exception as cleanup_err:
            logger.error(f"Error during cleanup after test failure: {cleanup_err}", exc_info=True)
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # Ensure harness cleanup happens reliably
        logger.info("Cleaning up test harness...")
        await harness.cleanup()
        logger.info("Test harness cleaned up.")


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_echo_complex_types() -> None:
    """Test the echo tool with complex parameter types (list, dict)."""
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port} for complex types test")
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])
        if process.returncode is not None:
            pytest.fail(f"Process failed to start with return code {process.returncode}")

        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed"
        assert harness.server_url, "Server URL not found"
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"Complex types test: Server ready at {sse_endpoint_url}")

        async def check_complex_echo(session: ClientSession, input_value: Any, expected_echoed_value: Any) -> None:
            """Helper for complex echo checks."""
            logger.info(f"Testing complex echo: {input_value!r}")
            result = await asyncio.wait_for(session.call_tool("echo", {"message": input_value}), timeout=15.0)
            logger.debug(f"Complex echo raw result: {result}")
            assert result is not None and not result.isError and result.content
            text_content = result.content[0]
            assert isinstance(text_content, TextContent)
            response_text = text_content.text
            logger.debug(f"Complex response text: {response_text!r}")
            try:
                response_data = json.loads(response_text)
                assert isinstance(response_data, dict)
                assert "echoed" in response_data
                assert (
                    response_data["echoed"] == expected_echoed_value
                ), f"Expected {expected_echoed_value!r}, got {response_data['echoed']!r}"
                logger.info(f"Complex assertion passed for: {input_value!r}")
            except (json.JSONDecodeError, AssertionError, TypeError) as e:
                pytest.fail(
                    f"Complex echo verification failed for {input_value!r}: {e}. Response text: {response_text!r}"
                )

        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                await asyncio.sleep(0.1)

                # Test list
                list_input = [1, "two", True, None, 3.14]
                await check_complex_echo(session, list_input, list_input)

                # Test dictionary
                dict_input = {"a": 1, "b": "hello", "c": False, "d": None, "e": [10, 20]}
                await check_complex_echo(session, dict_input, dict_input)

                # Test nested structure
                nested_input = {"outer": [{"inner_key": "value", "inner_list": [1, None]}, False]}
                await check_complex_echo(session, nested_input, nested_input)

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        try:
            await harness.cleanup()
        except Exception:
            pass
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        await harness.cleanup()


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_multiple_sequential_calls() -> None:
    """Test multiple sequential calls to the echo tool."""
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port} for sequential calls test")
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])
        if process.returncode is not None:
            pytest.fail("Process failed start")

        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed"
        assert harness.server_url, "Server URL not found"
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"Sequential calls test: Server ready at {sse_endpoint_url}")  # noqa: F541

        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                await asyncio.sleep(0.1)

                # Make multiple calls
                for i in range(5):
                    message = f"Call number {i+1}"
                    logger.info(f"Sequential call {i+1}: Sending '{message}'")
                    result = await asyncio.wait_for(session.call_tool("echo", {"message": message}), timeout=15.0)
                    logger.debug(f"Sequential call {i+1} raw result: {result}")
                    assert result is not None and not result.isError and result.content
                    text_content = result.content[0]
                    assert isinstance(text_content, TextContent)
                    response_data = json.loads(text_content.text)
                    assert response_data.get("echoed") == message
                    logger.info(f"Sequential call {i+1} successful.")
                    await asyncio.sleep(0.05)  # Small delay between calls

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        try:
            await harness.cleanup()
        except Exception:
            pass
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        await harness.cleanup()


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_list_tools() -> None:
    """Test the list_tools functionality via SSE."""
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port} for list_tools test")
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(test_port)])
        if process.returncode is not None:
            pytest.fail("Process failed start")

        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed"
        assert harness.server_url, "Server URL not found"
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"List tools test: Server ready at {sse_endpoint_url}")  # noqa: F541

        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                await asyncio.sleep(0.1)

                logger.info("Calling list_tools...")
                list_tools_result = await asyncio.wait_for(session.list_tools(), timeout=15.0)
                logger.info(f"list_tools result: {list_tools_result}")

                assert isinstance(list_tools_result, ListToolsResult), "Result is not ListToolsResult"
                assert list_tools_result.tools is not None, "list_tools result has no tools list or indicates an error"
                assert len(list_tools_result.tools) > 0, "list_tools returned empty list"

                # Find the 'echo' tool
                echo_tool_found = False
                for tool in list_tools_result.tools:
                    if tool.name == "echo":
                        echo_tool_found = True
                        assert tool.description == "Echo back the input message"
                        # Could add more checks for parameters if needed
                        break

                assert echo_tool_found, "'echo' tool not found in list_tools result"
                logger.info("list_tools test passed.")

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        try:
            await harness.cleanup()
        except Exception:
            pass
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        await harness.cleanup()
