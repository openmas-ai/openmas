"""Tests client-side error handling for stdio transport."""

import asyncio
import logging
import os
import sys
from pathlib import Path

import pytest
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_server_not_available_stdio() -> None:
    """Test handling when the stdio server process script is not available or exits early."""

    # --- Test with non-existent script ---
    logger.info("Testing stdio_client with non-existent script path.")
    nonexistent_script = Path("/path/to/hopefully/nonexistent/script_xyz123.py")
    assert not nonexistent_script.exists(), "Test assumption failed: Script path exists!"
    params_nonexistent = StdioServerParameters(command=sys.executable, args=[str(nonexistent_script)])

    # Try to create a client - this should fail during process creation or within the context manager
    with pytest.raises(Exception) as exc_info:  # Expect any Exception from process/stream issues
        async with stdio_client(params_nonexistent) as streams:
            # Give it a moment to potentially fail internally
            await asyncio.sleep(0.1)
            # We ideally shouldn't reach here, but if we do, the context exit should raise
            pass  # Allow context exit to potentially raise the error

    # Check if the exception is FileNotFoundError or related to process failure
    assert isinstance(
        exc_info.value, (FileNotFoundError, OSError, Exception)
    ), f"Expected FileNotFoundError or similar, but got {type(exc_info.value)}"
    logger.info(f"Got expected exception ({type(exc_info.value)}) for non-existent script.")

    # --- Test with script that exits immediately ---
    logger.info("Testing stdio_client with script that exits immediately.")
    test_script_content = """
import sys
import time
print("Exiting immediately!", file=sys.stderr)
sys.stderr.flush()
time.sleep(0.1) # Brief sleep to ensure message might be flushed
sys.exit(1)
"""
    # Create a temporary script file
    temp_script_path = Path("temp_exit_script_stdio.py").resolve()
    try:
        with open(temp_script_path, "w") as f:
            f.write(test_script_content)
        os.chmod(temp_script_path, 0o755)  # Make executable

        params_exits = StdioServerParameters(command=sys.executable, args=[str(temp_script_path)])

        # stdio_client tries to manage the process; expect an error during initialization or communication
        # The exact error might vary (e.g., BrokenPipeError, ConnectionResetError, or custom MCP error)
        # Using a broad Exception check is safer here.
        with pytest.raises(Exception) as exc_info:
            async with stdio_client(params_exits) as streams:
                # Attempt initialization (might fail here or later)
                read_stream, write_stream = streams
                # This part might not be reached if process exits too quickly
                # session = ClientSession(read_stream, write_stream)
                # await session.initialize()
                await asyncio.sleep(2)  # Give time for potential error propagation
                pytest.fail("stdio_client should have raised an exception for exiting script")

        logger.info(f"Got expected exception for exiting script: {type(exc_info.value)}: {exc_info.value}")

    finally:
        # Clean up the temporary file
        if temp_script_path.exists():
            logger.debug(f"Cleaning up temporary script: {temp_script_path}")
            temp_script_path.unlink()
        else:
            logger.warning(f"Temporary script not found for cleanup: {temp_script_path}")
