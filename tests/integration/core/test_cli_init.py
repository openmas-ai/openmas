"""Integration tests for the CLI init command."""

import os
import shutil
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from openmas.cli.main import init


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    # Get the temporary directory path
    temp_path = str(tmp_path)

    # Make sure the directory exists
    os.makedirs(temp_path, exist_ok=True)

    # Store the original directory
    try:
        orig_dir = os.getcwd()
    except FileNotFoundError:
        # If current directory doesn't exist, use the temp directory
        orig_dir = temp_path

    # Change to the temporary directory
    os.chdir(temp_path)

    yield tmp_path

    # Change back to the original directory if it exists
    try:
        os.chdir(orig_dir)
    except (FileNotFoundError, OSError):
        # If we can't go back to the original directory, that's ok
        pass

    # Clean up
    if tmp_path.exists():
        try:
            shutil.rmtree(tmp_path)
        except (PermissionError, OSError):
            pass


def test_basic_init(temp_dir):
    """Test basic initialization works."""
    runner = CliRunner()
    result = runner.invoke(init, ["test_project"])

    assert result.exit_code == 0
    assert "OpenMAS project 'test_project' created successfully" in result.output

    # Verify project structure
    project_path = temp_dir / "test_project"
    assert project_path.exists()
    assert (project_path / "openmas_project.yml").exists()

    # Verify __init__.py files are created in the appropriate directories
    assert (project_path / "agents" / "__init__.py").exists()
    assert (project_path / "shared" / "__init__.py").exists()
    assert (project_path / "extensions" / "__init__.py").exists()
    assert (project_path / "tests" / "__init__.py").exists()

    # Verify sample agent directory and __init__.py
    assert (project_path / "agents" / "sample_agent").exists()
    assert (project_path / "agents" / "sample_agent" / "__init__.py").exists()
    assert (project_path / "agents" / "sample_agent" / "agent.py").exists()

    # Verify content of __init__.py files
    with open(project_path / "agents" / "__init__.py") as f:
        assert '"""OpenMAS agents package."""' in f.read()

    with open(project_path / "agents" / "sample_agent" / "__init__.py") as f:
        assert '"""Sample agent package."""' in f.read()


def test_init_existing_directory(temp_dir):
    """Test initializing in an existing directory shows proper error."""
    # Create a directory first
    project_path = temp_dir / "existing_project"
    project_path.mkdir()

    runner = CliRunner()
    result = runner.invoke(init, ["existing_project"])

    assert result.exit_code == 1
    assert "Project directory 'existing_project' already exists" in result.output


def test_init_permission_error(temp_dir):
    """Test permission error during directory creation."""
    runner = CliRunner()

    # Create a patch to simulate permission error
    with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
        result = runner.invoke(init, ["test_project"])

    assert result.exit_code == 1
    assert "Permission denied" in result.output
    assert "Error creating project directory" in result.output


def test_init_permission_error_file_creation(temp_dir):
    """Test permission error during file creation."""
    runner = CliRunner()

    # Create the directory but make file creation fail
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        result = runner.invoke(init, ["test_project"])

    assert result.exit_code == 1
    assert "Permission denied" in result.output
    # The error message depends on where the permission error occurs, which could be
    # during directory creation, __init__.py file creation, or other file creation
    assert any(
        message in result.output
        for message in [
            "Error creating project structure",
            "Error creating project files",
            "Error creating sample agent",
        ]
    )


def test_init_current_dir_permission_error(temp_dir):
    """Test permission error when creating files in current directory."""
    # Create a read-only directory for testing
    read_only_dir = temp_dir / "read_only"
    read_only_dir.mkdir()
    os.chdir(str(read_only_dir))

    # Make a subdirectory read-only to trigger permission error during subdirectory creation
    with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
        runner = CliRunner()
        result = runner.invoke(init, [".", "--name", "test_project"])

    assert result.exit_code == 1
    assert "Permission denied" in result.output
    assert "Error creating project structure" in result.output


def test_init_with_template(temp_dir):
    """Test initialization with template creates __init__.py files."""
    runner = CliRunner()
    result = runner.invoke(init, ["test_project_template", "--template", "mcp-server"])

    assert result.exit_code == 0
    assert "OpenMAS project 'test_project_template' created successfully" in result.output

    # Verify project structure
    project_path = temp_dir / "test_project_template"
    assert project_path.exists()
    assert (project_path / "openmas_project.yml").exists()

    # Verify __init__.py files in the template agent directory
    assert (project_path / "agents" / "mcp_server").exists()
    assert (project_path / "agents" / "mcp_server" / "__init__.py").exists()

    # Verify content of the template agent __init__.py file
    with open(project_path / "agents" / "mcp_server" / "__init__.py") as f:
        assert '"""MCP Server agent package."""' in f.read()
