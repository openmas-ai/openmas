"""Tests for the agent module."""

import asyncio
from unittest import mock

import pytest

from openmas.exceptions import LifecycleError

# Import SimpleAgent from conftest.py
from tests.conftest import AgentConfig, SimpleAgent


class TestBaseAgent:
    """Tests for the BaseAgent class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_communicator: mock.AsyncMock, config: AgentConfig) -> None:
        """Test that initialization sets up the agent correctly."""
        communicator_class = mock.MagicMock(return_value=mock_communicator)

        agent = SimpleAgent(config=config, communicator_class=communicator_class)

        assert agent.name == "test-agent"
        assert agent.config.name == "test-agent"
        assert agent.communicator == mock_communicator
        assert not agent._is_running
        assert agent._task is None
        assert agent._background_tasks == set()

        # The communicator should be initialized with the agent name and service URLs
        communicator_class.assert_called_once_with("test-agent", {})

    @pytest.mark.asyncio
    async def test_lifecycle(self, simple_agent: SimpleAgent, mock_communicator: mock.AsyncMock) -> None:
        """Test the agent lifecycle."""
        agent = simple_agent

        # Start the agent
        await agent.start()

        # The agent should be running
        assert agent._is_running
        assert agent._task is not None

        # The setup hook should have been called
        assert agent.setup_called

        # The communicator should have been started
        mock_communicator.start.assert_called_once()

        # Let the agent run for a bit
        await asyncio.sleep(agent.run_duration * 2)

        # The run hook should have been called
        assert agent.run_called

        # Stop the agent
        await agent.stop()

        # The agent should be stopped
        assert not agent._is_running
        assert agent._task is None

        # The shutdown hook should have been called
        assert agent.shutdown_called

        # The communicator should have been stopped
        mock_communicator.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_already_running(self, simple_agent: SimpleAgent) -> None:
        """Test that starting an already running agent raises an error."""
        # Start the agent
        await simple_agent.start()

        # Try to start it again
        with pytest.raises(LifecycleError):
            await simple_agent.start()

        # Clean up
        await simple_agent.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, simple_agent: SimpleAgent, mock_communicator: mock.AsyncMock) -> None:
        """Test that stopping a non-running agent is a no-op."""
        # Stop the agent (should be a no-op)
        await simple_agent.stop()

        # The shutdown hook should not have been called
        assert not simple_agent.shutdown_called

        # The communicator should not have been stopped
        mock_communicator.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_in_run(self, simple_agent: SimpleAgent) -> None:
        """Test that exceptions in the run method are propagated."""

        # Override the run method to raise an exception
        async def run_with_exception() -> None:
            raise ValueError("Test exception")

        # Use patch to replace the run method
        with mock.patch.object(simple_agent, "run", new=run_with_exception):
            # Start the agent
            await simple_agent.start()

            # Wait for the exception to propagate
            with pytest.raises(ValueError, match="Test exception"):
                await simple_agent._task

    @pytest.mark.asyncio
    async def test_exception_in_setup(self, simple_agent: SimpleAgent, mock_communicator: mock.AsyncMock) -> None:
        """Test that exceptions in setup() are caught and communicator is still stopped."""
        # Mock the setup method to raise an exception
        mock_communicator.reset_mock()
        mock_communicator.start.reset_mock()
        mock_communicator.stop.reset_mock()

        error_message = "Setup failure"

        async def setup_with_exception() -> None:
            simple_agent.setup_called = True
            raise ValueError(error_message)

        # Replace the setup method
        with mock.patch.object(simple_agent, "setup", new=setup_with_exception):
            # Start the agent - should fail with a LifecycleError
            with pytest.raises(LifecycleError) as exc_info:
                await simple_agent.start()

            # Verify the original exception is included
            assert error_message in str(exc_info.value)

            # Setup should have been called
            assert simple_agent.setup_called

            # Communicator.start should have been called
            mock_communicator.start.assert_called_once()

            # Communicator.stop should have been called to clean up
            mock_communicator.stop.assert_called_once()

            # Agent should not be running
            assert not simple_agent._is_running
            assert simple_agent._task is None

    @pytest.mark.asyncio
    async def test_exception_in_communicator_start(
        self, simple_agent: SimpleAgent, mock_communicator: mock.AsyncMock
    ) -> None:
        """Test that exceptions in communicator.start() are caught and wrapped."""
        # Mock the communicator.start method to raise an exception
        mock_communicator.reset_mock()
        error_message = "Communicator start failure"
        mock_communicator.start.side_effect = RuntimeError(error_message)

        # Start the agent - should fail with a LifecycleError
        with pytest.raises(LifecycleError) as exc_info:
            await simple_agent.start()

        # Verify the original exception is included
        assert error_message in str(exc_info.value)

        # Communicator.start should have been called
        mock_communicator.start.assert_called_once()

        # Setup should not have been called
        assert not simple_agent.setup_called

        # Agent should not be running
        assert not simple_agent._is_running
        assert simple_agent._task is None

    @pytest.mark.asyncio
    async def test_exception_in_shutdown(self, simple_agent: SimpleAgent, mock_communicator: mock.AsyncMock) -> None:
        """Test that exceptions in shutdown() are caught but communicator is still stopped."""
        # Start the agent
        await simple_agent.start()
        assert simple_agent._is_running

        # Reset the mocks to track new calls
        mock_communicator.reset_mock()

        # Mock the shutdown method to raise an exception
        error_message = "Shutdown failure"

        async def shutdown_with_exception() -> None:
            simple_agent.shutdown_called = True
            raise ValueError(error_message)

        # Replace the shutdown method
        with mock.patch.object(simple_agent, "shutdown", new=shutdown_with_exception):
            # Stop the agent - should not raise an exception
            await simple_agent.stop()

            # Shutdown should have been called
            assert simple_agent.shutdown_called

            # Communicator.stop should have been called regardless of shutdown error
            mock_communicator.stop.assert_called_once()

            # Agent should not be running
            assert not simple_agent._is_running
            assert simple_agent._task is None

    @pytest.mark.asyncio
    async def test_exception_in_communicator_stop(
        self, simple_agent: SimpleAgent, mock_communicator: mock.AsyncMock
    ) -> None:
        """Test that exceptions in communicator.stop() are caught and agent is still stopped."""
        # Start the agent
        await simple_agent.start()
        assert simple_agent._is_running

        # Reset the mocks to track new calls
        mock_communicator.reset_mock()

        # Mock the communicator.stop method to raise an exception
        error_message = "Communicator stop failure"
        mock_communicator.stop.side_effect = RuntimeError(error_message)

        # Stop the agent - should not raise an exception
        await simple_agent.stop()

        # Shutdown should have been called
        assert simple_agent.shutdown_called

        # Communicator.stop should have been called
        mock_communicator.stop.assert_called_once()

        # Agent should not be running despite the error
        assert not simple_agent._is_running
        assert simple_agent._task is None

    @pytest.mark.asyncio
    async def test_background_tasks(self, simple_agent: SimpleAgent) -> None:
        """Test that background tasks are properly managed."""
        # Create a flag to track if the background task ran
        background_task_ran = False
        background_task_cancelled = False

        # Define a background task
        async def task_function() -> None:
            nonlocal background_task_ran, background_task_cancelled
            try:
                background_task_ran = True
                # Run indefinitely until cancelled
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                background_task_cancelled = True
                raise

        # Start the agent
        await simple_agent.start()

        # Create a background task - call it directly without storing the reference
        # since we don't need it for this test
        simple_agent.create_background_task(task_function())

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Check that the task ran
        assert background_task_ran
        assert not background_task_cancelled

        # Stop the agent
        await simple_agent.stop()

        # Verify the background task was cancelled
        assert background_task_cancelled

        # Verify the task set is empty
        assert len(simple_agent._background_tasks) == 0

    @pytest.mark.asyncio
    async def test_background_tasks_exception(self, simple_agent: SimpleAgent) -> None:
        """Test that exceptions in background tasks don't affect agent lifecycle."""
        # Create flags to track execution
        task_started = False

        # Define a background task that raises an exception
        async def failing_task() -> None:
            nonlocal task_started
            task_started = True
            await asyncio.sleep(0.1)
            raise ValueError("Background task failure")

        # Start the agent
        await simple_agent.start()

        # Create a background task that will fail
        background_task = simple_agent.create_background_task(failing_task())

        # Let it run and fail
        await asyncio.sleep(0.2)

        # Check that the task ran and failed
        assert task_started
        assert background_task.done()

        # The agent should still be running
        assert simple_agent._is_running

        # The background task should have been removed from the set
        assert background_task not in simple_agent._background_tasks

        # Clean up
        await simple_agent.stop()

    @pytest.mark.asyncio
    async def test_background_task_completion(self, simple_agent: SimpleAgent) -> None:
        """Test that background tasks that complete normally are properly managed."""
        # Create flags to track execution
        task_started = False
        task_completed = False

        # Define a background task that completes normally
        async def completing_task() -> None:
            nonlocal task_started, task_completed
            task_started = True
            await asyncio.sleep(0.1)
            task_completed = True

        # Start the agent
        await simple_agent.start()

        # Create a background task that will complete
        background_task = simple_agent.create_background_task(completing_task())

        # Let it run and complete
        await asyncio.sleep(0.2)

        # Check that the task ran and completed
        assert task_started
        assert task_completed
        assert background_task.done()

        # The background task should have been removed from the set
        assert background_task not in simple_agent._background_tasks

        # The agent should still be running
        assert simple_agent._is_running

        # Verify the task set size has decreased
        assert len(simple_agent._background_tasks) == 0

        # Clean up
        await simple_agent.stop()

    @pytest.mark.asyncio
    async def test_database_compatibility(self) -> None:
        """Test that agent can work with async database connections."""
        # This test uses sqlite as an example
        try:
            import aiosqlite  # type: ignore  # Optional import, test is skipped if not available
        except ImportError:
            pytest.skip("aiosqlite not installed")

        # Create a simple agent with database interaction
        class DbAgent(SimpleAgent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.db = None
                self.db_result = None

            async def setup(self) -> None:
                await super().setup()
                # Connect to an in-memory SQLite database
                self.db = await aiosqlite.connect(":memory:")

                # Create a simple table
                await self.db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
                await self.db.commit()

            async def run(self) -> None:
                # Insert some data
                await self.db.execute("INSERT INTO test (value) VALUES (?)", ("test value",))
                await self.db.commit()

                # Query the data
                async with self.db.execute("SELECT * FROM test") as cursor:
                    self.db_result = await cursor.fetchall()

                await super().run()

            async def shutdown(self) -> None:
                # Close the database connection
                if self.db:
                    await self.db.close()
                await super().shutdown()

        # Create a config with a name
        config = AgentConfig(name="db-agent", communicator_type="mock", service_urls={})

        # Create and run the agent with the config
        agent = DbAgent(config=config)

        try:
            # Start the agent
            await agent.start()

            # Let it run for a bit
            await asyncio.sleep(agent.run_duration * 2)

            # Verify database operations worked
            assert agent.db_result is not None
            assert len(agent.db_result) == 1
            assert agent.db_result[0][1] == "test value"

        finally:
            # Clean up
            await agent.stop()

    @pytest.mark.asyncio
    async def test_subprocess_compatibility(self) -> None:
        """Test that agent can work with async subprocesses."""

        # Create a simple agent with subprocess interaction
        class SubprocessAgent(SimpleAgent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.process_result = None

            async def run(self) -> None:
                # Run a simple echo command
                process = await asyncio.create_subprocess_exec(
                    "echo", "Hello from subprocess", stdout=asyncio.subprocess.PIPE
                )

                # Get the output
                stdout, _ = await process.communicate()
                self.process_result = stdout.decode().strip()

                await super().run()

        # Create a config with a name
        config = AgentConfig(name="subprocess-agent", communicator_type="mock", service_urls={})

        # Create and run the agent with the config
        agent = SubprocessAgent(config=config)

        try:
            # Start the agent
            await agent.start()

            # Let it run for a bit
            await asyncio.sleep(agent.run_duration * 2)

            # Verify subprocess operation worked
            assert agent.process_result == "Hello from subprocess"

        finally:
            # Clean up
            await agent.stop()
