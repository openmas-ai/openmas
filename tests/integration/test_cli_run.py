"""Integration tests for the OpenMAS CLI run command."""

import os
import subprocess
import sys

import pytest
import yaml


@pytest.fixture
def sample_project(tmp_path):
    """Create a sample OpenMAS project for integration testing."""
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    # Create standard directories
    (project_dir / "agents").mkdir()
    (project_dir / "shared").mkdir()
    (project_dir / "extensions").mkdir()
    (project_dir / "config").mkdir()

    # Create a simple agent
    agent_dir = project_dir / "agents" / "simple_agent"
    agent_dir.mkdir()

    # Write a simple agent implementation
    agent_file = agent_dir / "agent.py"
    agent_file.write_text(
        """
import asyncio
import os
from openmas.agent import BaseAgent


class SimpleAgent(BaseAgent):
    \"\"\"A simple agent that just prints a message and exits.\"\"\"

    async def setup(self):
        \"\"\"Set up the agent.\"\"\"
        print(f"Setting up {self.name}")
        print(f"Config loaded: log_level={self.config.log_level}")
        print(f"Environment: {os.environ.get('OPENMAS_ENV', 'unknown')}")

    async def run(self):
        \"\"\"Run the agent.\"\"\"
        print(f"Running {self.name}")
        # Just run once for testing
        await asyncio.sleep(0.1)
        print(f"Agent {self.name} completed successfully")

    async def shutdown(self):
        \"\"\"Shut down the agent.\"\"\"
        print(f"Shutting down {self.name}")
"""
    )

    # Create a simple shared utility module
    shared_dir = project_dir / "shared"
    utils_file = shared_dir / "utils.py"
    utils_file.write_text(
        """
\"\"\"Shared utilities for the project.\"\"\"

def get_greeting(name):
    \"\"\"Get a greeting message.\"\"\"
    return f"Hello, {name}!"
"""
    )

    # Create a project configuration file
    project_config = {
        "name": "sample_project",
        "version": "0.1.0",
        "agents": {"simple_agent": "agents/simple_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "default_config": {"log_level": "INFO", "communicator_type": "http"},
    }

    with open(project_dir / "openmas_project.yml", "w") as f:
        yaml.dump(project_config, f)

    # Create environment-specific configuration files
    default_config = {"log_level": "INFO"}

    test_config = {"log_level": "DEBUG"}

    with open(project_dir / "config" / "default.yml", "w") as f:
        yaml.dump(default_config, f)

    with open(project_dir / "config" / "test.yml", "w") as f:
        yaml.dump(test_config, f)

    return project_dir


@pytest.mark.integration
def test_cli_run_command_integration(sample_project):
    """Test the CLI run command with a real project structure."""
    # Skip if CI environment to avoid subprocess issues
    if os.environ.get("CI") == "true":
        pytest.skip("Skipping in CI environment")

    # Save current directory
    original_dir = os.getcwd()

    try:
        # Change to the project directory
        os.chdir(sample_project)

        # Run the command with subprocess to simulate real CLI usage
        # We need to use a timeout to ensure the test doesn't hang
        cmd = [sys.executable, "-m", "openmas.cli", "run", "simple_agent", "--env", "test"]

        # Use subprocess.run with timeout
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # 10 second timeout

        # Check return code
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check output contains expected strings
        assert "Using project root:" in result.stdout
        assert "Using environment: test" in result.stdout
        assert "Setting up simple_agent" in result.stdout
        assert "Config loaded: log_level=DEBUG" in result.stdout
        assert "Running simple_agent" in result.stdout
        assert "Agent simple_agent completed successfully" in result.stdout
        assert "Shutting down simple_agent" in result.stdout

    except subprocess.TimeoutExpired:
        pytest.fail("Command timed out")
    finally:
        # Restore original directory
        os.chdir(original_dir)


@pytest.mark.integration
def test_cli_run_missing_agent_integration(sample_project):
    """Test the CLI run command with a non-existent agent."""
    # Skip if CI environment to avoid subprocess issues
    if os.environ.get("CI") == "true":
        pytest.skip("Skipping in CI environment")

    # Save current directory
    original_dir = os.getcwd()

    try:
        # Change to the project directory
        os.chdir(sample_project)

        # Run the command with subprocess to simulate real CLI usage
        cmd = [sys.executable, "-m", "openmas.cli", "run", "nonexistent_agent"]

        # Use subprocess.run
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)  # 5 second timeout

        # Check return code (should fail)
        assert result.returncode != 0

        # Check output contains expected error message
        assert "Agent 'nonexistent_agent' not found in project configuration" in result.stdout
        assert "Available agents: simple_agent" in result.stdout

    except subprocess.TimeoutExpired:
        pytest.fail("Command timed out")
    finally:
        # Restore original directory
        os.chdir(original_dir)
