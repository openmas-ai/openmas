"""Tests for the OpenMAS CLI."""

import os
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from openmas.cli.main import cli


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with a basic structure."""
    # Create project directory and basic files
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create subdirectories
    subdirs = ["agents", "shared", "extensions", "config", "tests"]
    for subdir in subdirs:
        (project_dir / subdir).mkdir()

    # Create agent1 directory with agent.py
    agent1_dir = project_dir / "agents" / "agent1"
    agent1_dir.mkdir()
    with open(agent1_dir / "agent.py", "w") as f:
        f.write(
            """from openmas.agent import BaseAgent

class Agent1(BaseAgent):
    async def setup(self):
        self.logger.info("Agent1 setup")
    async def run(self):
        self.logger.info("Agent1 running")
        while True:
            await asyncio.sleep(1)
    async def shutdown(self):
        self.logger.info("Agent1 shutdown")
"""
        )

    # Create a second agent for testing multi-agent guidance message
    agent2_dir = project_dir / "agents" / "agent2"
    agent2_dir.mkdir()
    with open(agent2_dir / "agent.py", "w") as f:
        f.write(
            """from openmas.agent import BaseAgent

class Agent2(BaseAgent):
    async def setup(self):
        pass
    async def run(self):
        while True:
            await asyncio.sleep(1)
    async def shutdown(self):
        pass
"""
        )

    # Create a shared module
    shared_dir = project_dir / "shared"
    shared_module_dir = shared_dir / "utils"
    shared_module_dir.mkdir()
    with open(shared_module_dir / "__init__.py", "w") as f:
        f.write("")
    with open(shared_module_dir / "helpers.py", "w") as f:
        f.write('def say_hello(): return "Hello from shared module"')

    # Create config files
    config_dir = project_dir / "config"
    with open(config_dir / "default.yml", "w") as f:
        f.write("default_key: default_value\n")
    with open(config_dir / "local.yml", "w") as f:
        f.write("local_key: local_value\n")

    # Create a .env file
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


def test_init_command(cli_runner, tmp_path):
    """Test the init command."""
    project_path = tmp_path / "new_project"

    # Directly invoke the CLI without sys.exit
    cli_runner.invoke(cli, ["init", str(project_path)])

    # Check that the directory structure was created
    assert project_path.exists()
    assert (project_path / "agents").exists()
    assert (project_path / "shared").exists()
    assert (project_path / "extensions").exists()
    assert (project_path / "config").exists()
    assert (project_path / "tests").exists()
    assert (project_path / "openmas_project.yml").exists()
    assert (project_path / "README.md").exists()
    assert (project_path / "requirements.txt").exists()

    # Check the project configuration
    with open(project_path / "openmas_project.yml", "r") as f:
        config = yaml.safe_load(f)

    # The name is the path when using the Click CliRunner in testing
    assert "name" in config
    assert "version" in config
    assert config["version"] == "0.1.0"
    assert "default_config" in config
    assert config["default_config"]["log_level"] == "INFO"
    assert config["default_config"]["communicator_type"] == "http"


def test_init_command_with_template(cli_runner, tmp_path):
    """Test the init command with the mcp-server template."""
    project_path = tmp_path / "mcp_project"

    cli_runner.invoke(cli, ["init", str(project_path), "--template", "mcp-server"])

    # Check that the MCP server agent was created
    assert (project_path / "agents" / "mcp_server").exists()
    assert (project_path / "agents" / "mcp_server" / "agent.py").exists()
    assert (project_path / "agents" / "mcp_server" / "openmas.deploy.yaml").exists()

    # Check the project configuration
    with open(project_path / "openmas_project.yml", "r") as f:
        config = yaml.safe_load(f)

    assert "agents" in config
    assert "mcp_server" in config["agents"]
    assert config["agents"]["mcp_server"] == "agents/mcp_server"


def test_init_existing_directory(cli_runner, tmp_path):
    """Test init command with an existing directory."""
    project_path = tmp_path / "existing_project"
    project_path.mkdir()

    result = cli_runner.invoke(cli, ["init", str(project_path)])

    assert result.exit_code != 0
    # The assertion below needs to check for a partial match since the full path is variable
    assert "already exists" in result.output


def test_validate_command(cli_runner, temp_project_dir):
    """Test the validate command in a valid project."""
    with cli_runner.isolated_filesystem():
        # Copy the temporary project to the isolated filesystem
        os.system(f"cp -r {temp_project_dir}/* .")

        result = cli_runner.invoke(cli, ["validate"])

        # When the project is valid, we should see these messages
        assert "Project configuration 'openmas_project.yml' is valid" in result.output
        assert "Project: test_project" in result.output
        assert "Agents defined: 2" in result.output


def test_validate_missing_config(cli_runner):
    """Test the validate command when the configuration file is missing."""
    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["validate"])

        assert result.exit_code != 0
        assert "Project configuration file 'openmas_project.yml' not found" in result.output


def test_list_agents_command(cli_runner, temp_project_dir):
    """Test the list agents command."""
    with cli_runner.isolated_filesystem():
        # Copy the temporary project to the isolated filesystem
        os.system(f"cp -r {temp_project_dir}/* .")

        result = cli_runner.invoke(cli, ["list", "agents"])

        assert "Agents in project 'test_project':" in result.output
        assert "agent1: agents/agent1" in result.output
        assert "agent2: agents/agent2" in result.output


def test_list_agents_missing_config(cli_runner):
    """Test the list agents command when the configuration file is missing."""
    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["list", "agents"])

        assert result.exit_code != 0
        assert "Project configuration file 'openmas_project.yml' not found" in result.output


class MockBaseAgent:
    """Mock BaseAgent class for testing."""

    def __init__(self, name=None, **kwargs):
        self.name = name
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False
        self.logger = MagicMock()

    async def setup(self):
        self.setup_called = True

    async def run(self):
        self.run_called = True
        # Just return immediately for testing
        return

    async def shutdown(self):
        self.shutdown_called = True


@patch("importlib.import_module")
@patch("openmas.agent.base.BaseAgent", MockBaseAgent)
@patch("openmas.config._find_project_root")
@patch("openmas.cli.run._find_project_root")
@patch("openmas.communication.discover_communicator_extensions")
@patch("openmas.communication.discover_local_communicators")
def test_run_command_with_project_dir(
    mock_discover_local,
    mock_discover_ext,
    mock_cli_find_root,
    mock_find_root,
    mock_import,
    cli_runner,
    temp_project_dir,
):
    """Test the run command with the --project-dir parameter."""
    mock_find_root.return_value = temp_project_dir
    mock_cli_find_root.return_value = temp_project_dir

    # Setup a mock module that contains a BaseAgent subclass
    mock_agent_class = type("Agent1", (MockBaseAgent,), {})
    mock_module = MagicMock()
    mock_module.Agent1 = mock_agent_class
    mock_import.return_value = mock_module

    # Run the command with project-dir flag
    cli_runner.invoke(cli, ["run", "agent1", "--project-dir", str(temp_project_dir)])

    # Verify that the project-dir parameter is respected
    mock_cli_find_root.assert_called_with(temp_project_dir)
    mock_import.assert_any_call("agents.agent1")


@patch("openmas.config._find_project_root")
@patch("openmas.cli.run._find_project_root")
@patch("pathlib.Path.cwd")
def test_run_command_with_invalid_project_dir(mock_cwd, mock_cli_find_root, mock_find_root, cli_runner, tmp_path):
    """Test the run command with an invalid --project-dir."""
    # Simulate a case where the project directory doesn't contain openmas_project.yml
    mock_find_root.return_value = None
    mock_cli_find_root.return_value = None
    mock_cwd.return_value = tmp_path

    # Create a temporary directory that doesn't have a openmas_project.yml
    invalid_dir = tmp_path / "invalid_dir"
    invalid_dir.mkdir()

    # Run the command with the invalid project directory
    result = cli_runner.invoke(cli, ["run", "agent1", "--project-dir", str(invalid_dir)])

    # Verify that the command failed with the correct error message
    assert result.exit_code != 0
    assert "Project configuration file 'openmas_project.yml' not found" in result.output
