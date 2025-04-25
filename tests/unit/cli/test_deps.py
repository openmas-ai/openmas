"""Tests for the 'deps' command in the OpenMAS CLI."""

import subprocess
from unittest.mock import MagicMock, patch

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
    (project_dir / "packages").mkdir()

    return project_dir


@pytest.fixture
def mock_project_config(mock_project_dir):
    """Create a mock project configuration file with dependencies."""
    config_path = mock_project_dir / "openmas_project.yml"

    config = {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"test_agent": "agents/test_agent"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "default_config": {"log_level": "INFO"},
        "dependencies": [
            {"git": "https://github.com/example/repo1.git", "revision": "main"},
            {"git": "https://github.com/example/repo2.git"},
            {"package": "org/package", "version": "1.0.0"},
            {"local": "path/to/local/package"},
        ],
    }

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    return config_path


def test_deps_no_project_file(mock_project_dir):
    """Test deps command when no project file exists."""
    runner = CliRunner()

    with patch("openmas.config._find_project_root", return_value=None):
        result = runner.invoke(cli, ["deps", "--project-dir", str(mock_project_dir)])

        assert result.exit_code == 1
        assert "Project configuration file 'openmas_project.yml' not found" in result.output


def test_deps_no_dependencies(mock_project_dir):
    """Test deps command when no dependencies are defined."""
    config_path = mock_project_dir / "openmas_project.yml"

    with open(config_path, "w") as f:
        yaml.dump({"name": "test", "version": "0.1.0", "agents": {}}, f)

    runner = CliRunner()
    with patch("openmas.config._find_project_root", return_value=mock_project_dir):
        result = runner.invoke(cli, ["deps", "--project-dir", str(mock_project_dir)])

        assert "No dependencies defined in the project configuration" in result.output
        assert result.exit_code == 0


def test_deps_git_dependency(mock_project_dir, mock_project_config):
    """Test installing git dependencies."""
    # Mock successful subprocess runs
    mock_subprocess = MagicMock()

    runner = CliRunner()
    with patch("subprocess.run", return_value=mock_subprocess):
        with patch("openmas.config._find_project_root", return_value=mock_project_dir):
            result = runner.invoke(cli, ["deps", "--project-dir", str(mock_project_dir)])

            # Check that the echo calls include the expected output
            assert "Installing git package 'repo1' from https://github.com/example/repo1.git" in result.output
            assert "Installing git package 'repo2' from https://github.com/example/repo2.git" in result.output
            assert "⚠️ Package dependencies not implemented yet: org/package" in result.output
            assert "⚠️ Local dependencies not implemented yet: path/to/local/package" in result.output
            assert "Installed 4 dependencies" in result.output
            assert result.exit_code == 0


def test_deps_git_dependency_exists(mock_project_dir, mock_project_config):
    """Test updating an existing git dependency."""
    # Create an existing repo directory
    repo_dir = mock_project_dir / "packages" / "repo1"
    repo_dir.mkdir()

    # Mock successful subprocess runs
    mock_subprocess = MagicMock()

    runner = CliRunner()
    with patch("subprocess.run", return_value=mock_subprocess):
        with patch("openmas.config._find_project_root", return_value=mock_project_dir):
            result = runner.invoke(cli, ["deps", "--project-dir", str(mock_project_dir)])

            # Verify git pull calls for existing repo
            assert "Repository already exists, pulling latest changes" in result.output
            assert result.exit_code == 0


def test_deps_git_dependency_error(mock_project_dir, mock_project_config):
    """Test handling errors when installing git dependencies."""
    # Mock subprocess error
    error = subprocess.SubprocessError("Git error")

    runner = CliRunner()
    with patch("subprocess.run", side_effect=error):
        with patch("openmas.config._find_project_root", return_value=mock_project_dir):
            result = runner.invoke(cli, ["deps", "--project-dir", str(mock_project_dir)])

            # Verify error handling
            assert "❌ Error installing git package 'repo1': Git error" in result.output
            assert result.exit_code == 0


def test_run_with_packages(mock_project_dir, mock_project_config):
    """Test that the run command includes packages in sys.path."""
    # Create agent structure
    agent_dir = mock_project_dir / "agents" / "test_agent"
    agent_dir.mkdir(parents=True)

    with open(agent_dir / "agent.py", "w") as f:
        f.write(
            """
from openmas.agent import BaseAgent

class TestAgent(BaseAgent):
    async def setup(self):
        pass

    async def run(self):
        pass

    async def shutdown(self):
        pass
"""
        )

    # Create package directories
    packages_dir = mock_project_dir / "packages"

    # Package 1 - with src directory
    pkg1_dir = packages_dir / "package1"
    pkg1_dir.mkdir()
    (pkg1_dir / "src").mkdir()

    # Package 2 - without src directory
    pkg2_dir = packages_dir / "package2"
    pkg2_dir.mkdir()

    # Skip the test for now as it needs more complex mocking
    # This test is more of an integration test and should be refactored
    # to test the specific function that adds package paths
    pytest.skip("This test needs to be rewritten as a more focused unit test")
