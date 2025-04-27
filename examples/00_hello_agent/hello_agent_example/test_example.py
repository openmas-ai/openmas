"""This test file is for internal OpenMAS framework testing via tox.

It verifies that the hello_agent example runs correctly with the library.

Note: This is NOT a pattern for how end-users will test their own OpenMAS applications.
"""

import asyncio
import logging
import os
import sys
from typing import Any
from unittest.mock import patch

import pytest

# Configure logging for test
logging.basicConfig(level=logging.INFO)


# Use a simple test to check that the pytest-asyncio setup is working
@pytest.mark.asyncio
async def test_basic_async_functionality() -> None:
    """Basic test to verify pytest-asyncio is working."""
    await asyncio.sleep(0.1)
    assert True


@pytest.mark.asyncio
async def test_hello_agent() -> None:
    """
    Test using the HelloAgent implementation.

    This test verifies that the HelloAgent can be properly initialized,
    set up, run, and shut down.
    """
    # Add the agent's directory to the path for import
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

    # Import the actual agent
    from agents.hello_agent.agent import HelloAgent

    # Initialize the agent
    agent = HelloAgent(config={"name": "hello_agent", "service_urls": {}})

    # Setup phase
    await agent.setup()

    # Run the agent's main loop as a background task with a very short run time
    original_sleep = asyncio.sleep

    # Patch asyncio.sleep to make the test run faster
    async def fast_sleep(seconds: float, *args: Any, **kwargs: Any) -> None:
        # Make all sleeps very short
        await original_sleep(0.01, *args, **kwargs)

    with patch("asyncio.sleep", fast_sleep):
        run_task = asyncio.create_task(agent.run(), name="HelloAgentRun")

        # Let it run for a bit
        await asyncio.sleep(0.1)

        # Cancel the task
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

    # Clean up
    await agent.shutdown()

    # Verify the task was cancelled
    assert run_task.cancelled()
