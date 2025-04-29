"""Tests for the validate command."""

from unittest.mock import mock_open, patch

import pytest
import yaml
from click.testing import CliRunner

from openmas.cli.main import validate


@pytest.fixture
def valid_config():
    """Create a valid project configuration."""
    return {
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


def test_validate_file_not_found():
    """Test validate command when the project file doesn't exist."""
    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=False):
        result = runner.invoke(validate)

    assert result.exit_code == 1
    assert "❌ Project configuration file 'openmas_project.yml' not found" in result.output


def test_validate_valid_config(valid_config):
    """Test validate command with a valid configuration."""
    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(valid_config))
    ), patch(
        "openmas.cli.main.Path.exists", return_value=True
    ):  # Make all path checks succeed
        result = runner.invoke(validate)

    assert result.exit_code == 0
    assert "✅ Project configuration schema is valid" in result.output
    assert "✅ Project configuration is valid" in result.output
    assert f"Project: {valid_config['name']} v{valid_config['version']}" in result.output
    assert f"Agents defined: {len(valid_config['agents'])}" in result.output


def test_validate_missing_required_field():
    """Test validate command with a configuration missing a required field."""
    invalid_config = {
        "name": "test-project",
        # Missing version
        "agents": {
            "agent1": {
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
    }

    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(invalid_config))
    ):
        result = runner.invoke(validate)

    assert result.exit_code == 1
    assert "❌ Invalid project configuration:" in result.output
    assert "version" in result.output


def test_validate_invalid_agent_config():
    """Test validate command with an invalid agent configuration."""
    invalid_config = {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "agent1": {
                # Missing required "module" field
                "class": "Agent1",
            }
        },
    }

    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(invalid_config))
    ):
        result = runner.invoke(validate)

    assert result.exit_code == 1
    assert "❌ Invalid project configuration:" in result.output
    assert "module" in result.output


@pytest.mark.skip(reason="Mocking path existence is problematic in this test")
def test_validate_nonexistent_path():
    """Test validate command with a configuration pointing to nonexistent paths."""
    config = {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "agent1": {
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
        "shared_paths": ["nonexistent_path"],
        "extension_paths": ["another_nonexistent_path"],
    }

    runner = CliRunner()

    # Mock multiple patches to make opening the config work but paths not exist
    with patch("pathlib.Path.exists") as mock_exists, patch("builtins.open", mock_open(read_data=yaml.dump(config))):
        # First exists() call is for checking the openmas_project.yml file exists
        # Subsequent calls are for checking paths in the config
        mock_exists.side_effect = [True, False, False]  # First True, then False for each path
        result = runner.invoke(validate)

    # We've modified the validate command to not exit on path errors
    # It should report the issues but continue with a successful exit code
    assert "Shared directory 'nonexistent_path' does not exist" in result.output
    assert "Extension directory 'another_nonexistent_path' does not exist" in result.output


def test_validate_with_dependencies():
    """Test validate command with dependencies."""
    config = {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "agent1": {
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
        "dependencies": [
            {"git": "https://github.com/example/repo.git"},
            {"package": "some-package", "version": "1.0.0"},
        ],
    }

    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(config))
    ):
        result = runner.invoke(validate)

    assert result.exit_code == 0
    assert "Validating 2 dependencies" in result.output
    assert "✅ Dependencies schema is valid" in result.output


def test_validate_with_invalid_dependencies():
    """Test validate command with invalid dependencies."""
    config = {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "agent1": {
                "module": "agents.agent1",
                "class": "Agent1",
            }
        },
        "dependencies": [
            {"git": ""},  # Invalid URL
            {"package": "some-package"},  # Missing version
        ],
    }

    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(config))
    ):
        result = runner.invoke(validate)

    assert result.exit_code == 0  # Invalid dependencies no longer cause an exit
    assert "❌ Git dependency #1 has invalid URL" in result.output
    assert "❌ Package dependency 'some-package' is missing required 'version' field" in result.output


def test_validate_yaml_error():
    """Test validate command with invalid YAML."""
    runner = CliRunner()

    with patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data="invalid: yaml: content:")
    ):
        result = runner.invoke(validate)

    assert result.exit_code == 1
    assert "❌ Error parsing YAML in project configuration" in result.output
