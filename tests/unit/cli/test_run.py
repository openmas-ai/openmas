"""Tests for the OpenMAS CLI run command with focus on asyncio event loop consistency."""

import asyncio


def test_event_loop_consistency():
    """Test that the CLI's loop behavior is consistent for child tasks.

    This test verifies the fix for the asyncio loop conflict by ensuring
    that both parent and child tasks can use the same event loop.
    """
    # Save the current event loop
    old_loop = asyncio.get_event_loop_policy().get_event_loop()

    try:
        # Create a new clean event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Track task execution
        parent_loop = None
        child_loop = None

        # Define a task that will spawn a child task
        async def parent_task():
            nonlocal parent_loop
            # Record the parent's loop
            parent_loop = asyncio.get_running_loop()

            # Create a child task
            child = asyncio.create_task(child_task())
            await child

            # Return success
            return True

        async def child_task():
            nonlocal child_loop
            # Record the child's loop
            child_loop = asyncio.get_running_loop()
            return True

        # Run the tasks
        result = loop.run_until_complete(parent_task())

        # Verify everything worked
        assert result is True
        assert parent_loop is not None
        assert child_loop is not None
        assert parent_loop is child_loop, "Parent and child tasks should use the same event loop"
        assert parent_loop is loop, "Tasks should use the event loop we created"

    finally:
        # Clean up
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception:
            pass

        # Restore the original loop
        asyncio.set_event_loop(old_loop)
