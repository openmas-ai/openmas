"""Tests for the CLI init command."""

import os
import shutil

import pytest
from click.testing import CliRunner

from openmas.cli.main import init


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    yield tmp_path
    # Clean up
    if tmp_path.exists():
        shutil.rmtree(tmp_path)


def test_init_new_project(temp_dir):
    """Test initializing a new project in a new directory."""
    os.chdir(temp_dir)
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Use an absolute path to create the project in our temp_dir
        project_name = "test_project"
        project_path = temp_dir / project_name

        result = runner.invoke(init, [str(project_path)])
        assert result.exit_code == 0
        assert "OpenMAS project" in result.output
        assert "Project Creation Complete" in result.output

        # Check that the project directory was created
        assert project_path.exists()

        # Check that the necessary files and directories were created
        assert (project_path / "openmas_project.yml").exists()
        assert (project_path / "README.md").exists()
        assert (project_path / "requirements.txt").exists()
        assert (project_path / "agents").exists()
        assert (project_path / "shared").exists()
        assert (project_path / "extensions").exists()
        assert (project_path / "config").exists()
        assert (project_path / "tests").exists()


def test_init_current_directory_with_name(temp_dir):
    """Test initializing a project in the current directory with --name option."""
    # Use the temp_dir as our working directory
    os.chdir(temp_dir)
    runner = CliRunner()

    result = runner.invoke(init, [".", "--name", "current_dir_project"])
    assert result.exit_code == 0
    assert "OpenMAS project 'current_dir_project' created successfully" in result.output
    assert "Project structure initialized in current directory" in result.output

    # Check that files were created in the current directory
    assert (temp_dir / "openmas_project.yml").exists()
    assert (temp_dir / "README.md").exists()
    assert (temp_dir / "requirements.txt").exists()
    assert (temp_dir / "agents").exists()
    assert (temp_dir / "shared").exists()
    assert (temp_dir / "extensions").exists()
    assert (temp_dir / "config").exists()
    assert (temp_dir / "tests").exists()


def test_init_current_directory_without_name(temp_dir):
    """Test initializing in current directory without name fails."""
    os.chdir(temp_dir)
    runner = CliRunner()

    result = runner.invoke(init, ["."])
    assert result.exit_code == 1
    assert (
        "When initializing in the current directory (.), you must provide a project name with --name" in result.output
    )


def test_init_existing_project_directory(temp_dir):
    """Test initializing in an existing directory fails."""
    os.chdir(temp_dir)
    runner = CliRunner()

    # Create a directory that already exists
    existing_dir = temp_dir / "existing_project"
    existing_dir.mkdir()

    # Try to initialize in that directory
    result = runner.invoke(init, ["existing_project"])
    assert result.exit_code == 1
    assert "Project directory 'existing_project' already exists" in result.output


def test_init_with_template(temp_dir):
    """Test initializing a project with a template."""
    os.chdir(temp_dir)
    runner = CliRunner()

    # Use absolute path
    project_name = "template_project"
    project_path = temp_dir / project_name

    result = runner.invoke(init, [str(project_path), "--template", "mcp-server"])
    assert result.exit_code == 0
    assert "OpenMAS project" in result.output
    assert "created successfully" in result.output
    assert "Template: mcp-server" in result.output

    # Check that the template-specific files were created
    assert (project_path / "agents" / "mcp_server").exists()
    assert (project_path / "agents" / "mcp_server" / "agent.py").exists()
    assert (project_path / "agents" / "mcp_server" / "openmas.deploy.yaml").exists()
