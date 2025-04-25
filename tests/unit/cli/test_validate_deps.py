"""Tests for the validate command with dependencies in the OpenMAS CLI."""

from unittest.mock import mock_open, patch

import pytest
import yaml
from click.testing import CliRunner

from openmas.cli.main import cli


@pytest.fixture
def mock_project_dir(tmp_path):
    """Create a mock project directory for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create required directories
    subdirs = ["agents", "shared", "extensions", "config"]
    for subdir in subdirs:
        (project_dir / subdir).mkdir()

    # Create a sample agent
    agent_dir = project_dir / "agents" / "test_agent"
    agent_dir.mkdir()

    with open(agent_dir / "agent.py", "w") as f:
        f.write("# Test agent file")

    return project_dir


def test_validate_valid_dependencies(mock_project_dir):
    """Test validation with valid dependencies."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": [
            {"git": "https://github.com/example/repo.git"},
            {"git": "https://github.com/example/other-repo.git", "revision": "main"},
            {"package": "org/package", "version": "1.0.0"},
            {"local": "path/to/local/package"},
        ],
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert result.exit_code == 0
            assert "Dependencies schema is valid" in result.stdout


def test_validate_invalid_dependency_type(mock_project_dir):
    """Test validation with an invalid dependency type."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": [{"invalid_type": "https://github.com/example/repo.git"}],
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert "Dependency #1 must have exactly one type" in result.stdout


def test_validate_multiple_dependency_types(mock_project_dir):
    """Test validation with multiple dependency types in one entry."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": [{"git": "https://github.com/example/repo.git", "package": "org/pkg"}],
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert "Dependency #1 must have exactly one type" in result.stdout


def test_validate_invalid_git_url(mock_project_dir):
    """Test validation with an invalid Git URL."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": [{"git": ""}],  # Empty URL
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert "Git dependency #1 has invalid URL" in result.stdout


def test_validate_missing_package_version(mock_project_dir):
    """Test validation with a package dependency missing a version."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": [{"package": "org/package"}],  # Missing version
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert "Package dependency 'org/package' is missing required 'version' field" in result.stdout


def test_validate_non_dict_dependency(mock_project_dir):
    """Test validation with a non-dictionary dependency."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": ["not-a-dict"],
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert "Dependency #1 is not a dictionary" in result.stdout


def test_validate_invalid_local_path(mock_project_dir):
    """Test validation with an invalid local dependency path."""
    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "dependencies": [{"local": ""}],  # Empty path
    }

    # Run validation with mocked file operations
    runner = CliRunner()
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config))):
            result = runner.invoke(cli, ["validate"])
            assert "Local dependency #1 has invalid path" in result.stdout
