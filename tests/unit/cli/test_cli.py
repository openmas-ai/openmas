"""Tests for the SimpleMas CLI."""

import os
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from simple_mas.cli.main import cli


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
        f.write("from simple_mas.agent import BaseAgent\n\nclass Agent1(BaseAgent):\n    pass\n")

    # Create project config file
    project_config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"agent1": "agents/agent1"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "default_config": {"log_level": "INFO", "communicator_type": "http"},
    }

    with open(project_dir / "simplemas_project.yml", "w") as f:
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
    assert (project_path / "simplemas_project.yml").exists()
    assert (project_path / "README.md").exists()
    assert (project_path / "requirements.txt").exists()

    # Check the project configuration
    with open(project_path / "simplemas_project.yml", "r") as f:
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
    assert (project_path / "agents" / "mcp_server" / "simplemas.deploy.yaml").exists()

    # Check the project configuration
    with open(project_path / "simplemas_project.yml", "r") as f:
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
        assert "Project configuration is valid" in result.output
        assert "Project: test_project" in result.output
        assert "Agents defined: 1" in result.output


def test_validate_missing_config(cli_runner):
    """Test the validate command when the configuration file is missing."""
    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["validate"])

        assert result.exit_code != 0
        assert "Project configuration file 'simplemas_project.yml' not found" in result.output


def test_list_agents_command(cli_runner, temp_project_dir):
    """Test the list agents command."""
    with cli_runner.isolated_filesystem():
        # Copy the temporary project to the isolated filesystem
        os.system(f"cp -r {temp_project_dir}/* .")

        result = cli_runner.invoke(cli, ["list", "agents"])

        assert "Agents defined in the project:" in result.output
        assert "agent1: agents/agent1" in result.output


def test_list_agents_missing_config(cli_runner):
    """Test the list agents command when the configuration file is missing."""
    with cli_runner.isolated_filesystem():
        result = cli_runner.invoke(cli, ["list", "agents"])

        assert result.exit_code != 0
        assert "Project configuration file 'simplemas_project.yml' not found" in result.output


def test_run_command_agent_exists(cli_runner, temp_project_dir):
    """Test the run command with an existing agent."""
    with cli_runner.isolated_filesystem():
        # Copy the temporary project to the isolated filesystem
        os.system(f"cp -r {temp_project_dir}/* .")

        # Need to patch os.environ to check it was set properly
        with patch.dict(os.environ, {}, clear=True), patch("os.environ", new_callable=dict) as mock_environ:
            result = cli_runner.invoke(cli, ["run", "agent1"])

            assert "Running agent 'agent1'" in result.output
            assert mock_environ.get("AGENT_NAME") == "agent1"
            assert "SIMPLEMAS_PROJECT_CONFIG" in mock_environ


def test_run_command_agent_not_found(cli_runner, temp_project_dir):
    """Test the run command with a non-existent agent."""
    with cli_runner.isolated_filesystem():
        # Copy the temporary project to the isolated filesystem
        os.system(f"cp -r {temp_project_dir}/* .")

        result = cli_runner.invoke(cli, ["run", "nonexistent_agent"])

        assert result.exit_code != 0
        assert "Agent 'nonexistent_agent' not found in project configuration" in result.output
