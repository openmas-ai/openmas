"""Integration tests for the validate command."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for testing."""
    try:
        old_cwd = os.getcwd()
    except FileNotFoundError:
        # Use a fallback directory if current directory doesn't exist
        old_cwd = tempfile.gettempdir()

    with tempfile.TemporaryDirectory() as tmp_dir:
        os.chdir(tmp_dir)
        yield Path(tmp_dir)
        try:
            os.chdir(old_cwd)
        except (FileNotFoundError, PermissionError):
            # If we can't change back to the original directory, that's fine for tests
            pass


def test_validate_valid_config(temp_test_dir):
    """Test the validate command with a valid configuration."""
    # Create a valid configuration file
    config = {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "agent1": {
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
        "shared_paths": [],
        "extension_paths": [],
    }

    # Create directories to make paths valid
    (temp_test_dir / "agents").mkdir()
    (temp_test_dir / "agents" / "agent1").mkdir()
    with open(temp_test_dir / "agents" / "agent1" / "agent.py", "w") as f:
        f.write("class Agent1: pass")

    # Write the configuration file
    with open("openmas_project.yml", "w") as f:
        yaml.dump(config, f)

    # Run the validate command
    result = subprocess.run(["openmas", "validate"], capture_output=True, text=True)

    # Check the result
    assert result.returncode == 0
    assert "✅ Project configuration schema is valid" in result.stdout
    assert "✅ Agent 'agent1' found at" in result.stdout
    assert "✅ Project configuration 'openmas_project.yml' is valid" in result.stdout
    assert "Project: test-project v0.1.0" in result.stdout


def test_validate_missing_config(temp_test_dir):
    """Test the validate command with a missing configuration file."""
    # Run the validate command without creating the config file
    result = subprocess.run(["openmas", "validate"], capture_output=True, text=True)

    # Check the result
    assert result.returncode == 1
    assert "❌ Project configuration file 'openmas_project.yml' not found" in result.stdout


def test_validate_invalid_yaml(temp_test_dir):
    """Test the validate command with invalid YAML."""
    # Write an invalid YAML file
    with open("openmas_project.yml", "w") as f:
        f.write("invalid: yaml: content:")

    # Run the validate command
    result = subprocess.run(["openmas", "validate"], capture_output=True, text=True)

    # Check the result
    assert result.returncode == 1
    assert "❌ Error parsing YAML file" in result.stdout


def test_validate_missing_required_field(temp_test_dir):
    """Test the validate command with a configuration missing a required field."""
    # Create an invalid configuration file (missing version)
    config = {
        "name": "test-project",
        # Missing version
        "agents": {
            "agent1": {
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
    }

    # Write the configuration file
    with open("openmas_project.yml", "w") as f:
        yaml.dump(config, f)

    # Run the validate command
    result = subprocess.run(["openmas", "validate"], capture_output=True, text=True)

    # Check the result
    assert result.returncode == 1
    assert "❌ Invalid project configuration" in result.stdout
    assert "version" in result.stdout


def test_validate_invalid_agent_name(temp_test_dir):
    """Test the validate command with an invalid agent name."""
    # Create a configuration with an invalid agent name (contains invalid characters)
    config = {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "agent@1": {  # @ is not allowed in agent names
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
    }

    # Write the configuration file
    with open("openmas_project.yml", "w") as f:
        yaml.dump(config, f)

    # Run the validate command
    result = subprocess.run(["openmas", "validate"], capture_output=True, text=True)

    # Check the result
    assert result.returncode == 1
    assert "❌ Invalid project configuration" in result.stdout
    assert "agent name" in result.stdout.lower() or "Invalid agent" in result.stdout
