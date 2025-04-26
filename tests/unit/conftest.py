"""Common fixtures for unit tests."""

import json
import os
from unittest import mock

import pytest
import yaml

from openmas.agent import BaseAgent
from openmas.config import AgentConfig


@pytest.fixture
def config():
    """Create a basic AgentConfig for testing."""
    return AgentConfig(
        name="test-agent",
        communicator_type="mock",
        service_urls={"service1": "mock://service1"},
    )


@pytest.fixture
def mock_communicator():
    """Create a mock communicator with standard methods."""
    communicator = mock.AsyncMock()
    communicator.agent_name = "test-agent"
    communicator.start = mock.AsyncMock()
    communicator.stop = mock.AsyncMock()
    communicator.send_request = mock.AsyncMock(return_value={"result": "success"})
    communicator.send_notification = mock.AsyncMock()
    communicator.register_handler = mock.AsyncMock()
    communicator._is_started = False
    return communicator


class SimpleAgent(BaseAgent):
    """A simple agent implementation for testing."""

    def __init__(self, config: AgentConfig):
        """Initialize the agent with a config."""
        # Pass the config directly to the parent class, ensuring it won't try to load from env
        super().__init__(config=config)
        # Default test values
        self.run_duration = 0.1
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False

    async def setup(self) -> None:
        """Setup the agent."""
        self.setup_called = True
        await super().setup()

    async def run(self) -> None:
        """Run the agent's main logic."""
        self.run_called = True
        await super().run()

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.shutdown_called = True
        await super().shutdown()


@pytest.fixture
def simple_agent(config, mock_communicator):
    """Create a simple agent with mocked components."""
    agent = SimpleAgent(config)
    agent.set_communicator(mock_communicator)
    return agent


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client for testing HTTP communication."""
    with mock.patch("httpx.AsyncClient", autospec=True) as mock_client_class:
        mock_client = mock.AsyncMock()
        mock_client_class.return_value = mock_client

        # Mock standard response
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.text = json.dumps({"result": "success"})

        # Set up default return values for common methods
        mock_client.get.return_value = mock_response
        mock_client.post.return_value = mock_response
        mock_client.put.return_value = mock_response
        mock_client.delete.return_value = mock_response

        # Mock the context manager
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        yield mock_client


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with a basic OpenMAS structure.

    This fixture creates a standardized project structure with:
    - openmas_project.yml
    - .env file
    - config directory with default.yml and local.yml
    - agents directory with basic structure
    - shared directory
    - extensions directory

    Returns:
        Path: The path to the created project directory.
    """
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directories
    (project_dir / "agents").mkdir(exist_ok=True)
    (project_dir / "agents" / "agent1").mkdir(exist_ok=True)
    (project_dir / "agents" / "agent2").mkdir(exist_ok=True)
    (project_dir / "shared").mkdir(exist_ok=True)
    (project_dir / "extensions").mkdir(exist_ok=True)

    config_dir = project_dir / "config"
    config_dir.mkdir(exist_ok=True)

    # Create config files
    with open(config_dir / "default.yml", "w") as f:
        yaml.dump(
            {
                "log_level": "INFO",
                "communicator_type": "http",
            },
            f,
        )

    with open(config_dir / "local.yml", "w") as f:
        yaml.dump({"local_key": "local_value"}, f)

    # Create .env file
    with open(project_dir / ".env", "w") as f:
        f.write("ENV_VAR=env_value\n")

    # Create project config file
    project_config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"agent1": "agents/agent1", "agent2": "agents/agent2"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "default_config": {"log_level": "INFO", "communicator_type": "http"},
    }

    with open(project_dir / "openmas_project.yml", "w") as f:
        yaml.dump(project_config, f)

    return project_dir


@pytest.fixture
def mock_env_vars():
    """Fixture to manage environment variables for tests.

    This fixture provides utility functions to set, get, and clear environment variables
    in a safer way that restores the original state after the test.

    Returns:
        dict: A dictionary with utility functions for managing environment variables.
    """
    original_env = os.environ.copy()

    def set_var(name, value):
        os.environ[name] = value

    def get_var(name, default=None):
        return os.environ.get(name, default)

    def clear_var(name):
        if name in os.environ:
            del os.environ[name]

    def reset_all():
        os.environ.clear()
        os.environ.update(original_env)

    # Create and return the utility dictionary
    env_utils = {
        "set": set_var,
        "get": get_var,
        "clear": clear_var,
        "reset": reset_all,
    }

    yield env_utils

    # Restore original environment
    reset_all()
