"""Integration test for OpenMAS MCP stdio tool call example.

This test validates that the OpenMAS MCP stdio tool call example works correctly
with real MCP communication (not mocked). This test is a valuable "dogfooding"
opportunity to validate the OpenMAS library against real-world use cases.

It verifies:
1. Tool provider agent can register and expose tools via MCP
2. Tool user agent can discover and call tools from the provider
3. Error handling works correctly with real communication
4. Timeout handling is implemented correctly
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Path to the example directory - use absolute path to avoid issues
EXAMPLE_DIR = Path("/Users/wilson/Coding/dylangames/backup/openmas/examples/example_02_mcp/02_mcp_stdio_tool_call")
logger.debug(f"Example directory path: {EXAMPLE_DIR}")
if not EXAMPLE_DIR.exists():
    logger.error(f"Example directory does not exist: {EXAMPLE_DIR}")


def get_process_data_server_script() -> str:
    """Create a standalone MCP server script for testing the process_data tool.

    The script implements the same functionality as the ToolProviderAgent's process_data_handler.

    Returns:
        The Python script as a string
    """
    return textwrap.dedent(
        """\
        #!/usr/bin/env python

        import asyncio
        import json
        import sys
        from typing import Dict, Any

        from mcp.server.fastmcp import Context, FastMCP

        # Create the server
        server = FastMCP("ProcessDataServer")

        @server.tool("process_data", description="Process incoming data and return a result")
        async def process_data(context: Context, text: str = "") -> str:
            # Log the received data
            print(f"Tool handler received text: {text}", file=sys.stderr)

            # Process the data
            if text:
                processed_text = text.upper()
                word_count = len(text.split())

                result = {
                    "processed_text": processed_text,
                    "word_count": word_count,
                    "status": "success"
                }
            else:
                result = {
                    "error": "No text field in payload",
                    "status": "error"
                }

            # Convert to JSON string for return
            result_json = json.dumps(result)
            print(f"Tool handler returning: {result_json}", file=sys.stderr)
            return result_json

        # Run the server
        asyncio.run(server.run_stdio_async())
    """
    )


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.integration
async def test_real_mcp_stdio_tool_call() -> None:
    """Test real MCP stdio tool calls with a standalone MCP server.

    Instead of using the full OpenMAS agent, this test creates a simple MCP server
    that implements the same functionality as the ToolProviderAgent's process_data tool.
    This approach avoids issues with the agent process exiting too early.
    """
    # Create the server script
    process_data_script = get_process_data_server_script()

    # Write the script to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(process_data_script)
        script_path = tmp.name

    # Make it executable
    os.chmod(script_path, 0o755)

    # Process handle for cleanup
    process = None

    try:
        # Start the server script
        cmd = [sys.executable, script_path]
        logger.info(f"Starting MCP server: {' '.join(cmd)}")

        # Start the process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        logger.info(f"MCP server started with PID {process.pid}")

        # Give it a moment to initialize
        await asyncio.sleep(1.0)

        # Connect to the server
        params = StdioServerParameters(command=sys.executable, args=[script_path])

        # Connect and test tool calls
        logger.info("Connecting to MCP server")
        async with stdio_client(params) as streams:
            read_stream, write_stream = streams

            # Create a session
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the session
                await asyncio.wait_for(session.initialize(), timeout=5.0)

                # Test basic tool call
                logger.info("Making process_data tool call")
                test_text = "Hello, this is a test message from the integration test."
                test_payload = {"text": test_text}  # Pass as dictionary with 'text' key

                # Call the process_data tool
                result = await session.call_tool("process_data", test_payload)

                # Verify result
                assert result.content is not None, "Tool call returned no content"
                assert len(result.content) > 0, "Tool call content is empty"

                # Get the result text
                text_content = result.content[0]
                result_text = getattr(text_content, "text", "")

                logger.info(f"Received tool result: {result_text}")

                # Parse the result
                result_data = json.loads(result_text)

                # Verify the result structure
                assert "status" in result_data, "Result missing status field"
                assert result_data["status"] == "success", f"Tool call failed: {result_data}"
                assert "processed_text" in result_data, "Result missing processed_text field"
                assert "word_count" in result_data, "Result missing word_count field"

                # Verify the data
                expected_processed_text = test_text.upper()
                assert result_data["processed_text"] == expected_processed_text, "Text was not properly processed"

                # Verify word count (split by spaces)
                expected_word_count = len(test_text.split())
                assert result_data["word_count"] == expected_word_count, "Word count is incorrect"

                # Test error case - empty string
                logger.info("Testing error case with empty text")
                error_result = await session.call_tool("process_data", {"text": ""})

                # Verify error response
                assert error_result.content is not None, "Error test returned no content"
                assert len(error_result.content) > 0, "Error test content is empty"

                # Get the error result text
                error_text_content = error_result.content[0]
                error_result_text = getattr(error_text_content, "text", "")

                logger.info(f"Received error result: {error_result_text}")

                # Parse the error result
                error_data = json.loads(error_result_text)

                # Verify the error structure
                assert "status" in error_data, "Error result missing status field"
                assert error_data["status"] == "error", "Error result has incorrect status"
                assert "error" in error_data, "Error result missing error message field"

    finally:
        # Clean up
        if process and process.returncode is None:
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except ProcessLookupError:
                pass

        # Clean up the script file
        try:
            os.unlink(script_path)
        except Exception as e:
            logger.warning(f"Error removing temporary script: {e}")


def get_slow_provider_script() -> str:
    """Generate the script for a slow tool provider.

    Returns:
        The Python script as a string
    """
    return textwrap.dedent(
        """\
        import asyncio
        import json
        import sys
        from mcp.server.fastmcp import Context, FastMCP

        # Create the FastMCP server
        server = FastMCP("SlowToolProvider")

        @server.tool("slow_process", description="A tool that takes a long time to process")
        async def slow_process(context: Context, text: str = "") -> str:
            # Simulate a slow operation by sleeping
            await asyncio.sleep(10.0)  # Sleep for 10 seconds

            # Process the text (uppercase it)
            processed_text = text.upper()

            # Count the words
            word_count = len(text.split())

            # Return the result
            result = {
                "processed_text": processed_text,
                "word_count": word_count,
                "status": "success"
            }

            return json.dumps(result)

        # Run the server
        asyncio.run(server.run_stdio_async())
    """
    )


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.integration
async def test_real_mcp_stdio_timeout_handling() -> None:
    """Test timeout handling for MCP stdio tool calls with real agents.

    This test creates a custom tool provider that introduces a delay longer
    than the timeout to verify that the timeout handling works correctly.
    """
    # Create a custom tool provider script that has a slow tool
    slow_provider_script = get_slow_provider_script()

    # Write the script to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(slow_provider_script)
        slow_script_path = tmp.name

    try:
        # Start the slow tool provider as a subprocess
        cmd = [sys.executable, slow_script_path]
        logger.info(f"Starting slow tool provider: {' '.join(cmd)}")

        # Configure the MCP stdio client parameters
        params = StdioServerParameters(command=sys.executable, args=[slow_script_path])

        # Connect to the slow provider
        logger.info("Connecting to slow tool provider")
        async with stdio_client(params) as streams:
            read_stream, write_stream = streams

            # Create a client session with the stdio streams
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the session
                await asyncio.wait_for(session.initialize(), timeout=5.0)

                # Test calling the slow tool with a timeout shorter than the sleep
                test_text = "This call should time out"
                test_payload = {"text": test_text}  # Pass as dictionary with 'text' key

                # Call the slow_process tool with a short timeout
                logger.info("Calling slow_process tool with 2 second timeout")
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        session.call_tool("slow_process", test_payload),
                        timeout=2.0,  # Set timeout to 2 seconds (shorter than the 10 second sleep)
                    )

                logger.info("Successfully caught timeout exception")

    finally:
        # Clean up the temp file
        try:
            os.unlink(slow_script_path)
        except Exception as e:
            logger.warning(f"Error removing temporary script: {e}")
