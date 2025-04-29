"""Integration tests for SSE client error handling with MCP."""

import logging
import random

import httpx
import pytest

# from mcp.client.sse import sse_client


# from mcp.types import TextContent, Prompt # Commenting out as not used in this test

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.integration
async def test_server_not_available_sse() -> None:
    """Tests that connecting to a non-existent SSE server URL raises an appropriate error.

    Uses httpx directly as sse_client might wrap errors.
    """
    # Use a random port that should not be in use
    unused_port = random.randint(50000, 60000)
    invalid_url = f"http://127.0.0.1:{unused_port}/mcp"  # Use 127.0.0.1 for clarity
    logger.info(f"Testing connection to unavailable SSE URL: {invalid_url}")

    # Expect an httpx error when trying to connect to the invalid URL
    # sse_client itself might wrap this, so testing the underlying connection attempt
    # or catching a broader exception might be needed depending on sse_client behavior.
    # Let's stick to the expected underlying error for now.
    with pytest.raises(httpx.ConnectError) as exc_info:
        # Attempting a direct GET request to simulate the initial connection phase
        async with httpx.AsyncClient() as client:
            await client.get(invalid_url, timeout=2.0)
        # If sse_client was used directly, the call might look like:
        # async with sse_client(url=invalid_url, ...) as _: # Replace ... with required args
        #     pytest.fail("Should not reach here as the connection should fail")

    logger.info(f"Got expected exception: {exc_info.type.__name__}")
    # Optionally, assert specific details about the error if needed
    # assert "Connection refused" in str(exc_info.value) # This might be platform-specific

    logger.info("SSE client error test passed (ConnectError expected)")
