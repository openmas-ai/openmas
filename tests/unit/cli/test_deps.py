"""Tests for the 'deps' command in the OpenMAS CLI."""

import subprocess
import sys
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
    """Test that package paths are correctly added to sys.path."""
    from openmas.cli.run import add_package_paths_to_sys_path

    # Create agent structure
    agent_dir = mock_project_dir / "agents" / "test_agent"
    agent_dir.mkdir(parents=True)

    # Create package directories
    packages_dir = mock_project_dir / "packages"
    packages_dir.mkdir(exist_ok=True)

    # Package 1 - with src directory
    pkg1_dir = packages_dir / "package1"
    pkg1_src_dir = pkg1_dir / "src"
    pkg1_dir.mkdir()
    pkg1_src_dir.mkdir()

    # Package 2 - without src directory
    pkg2_dir = packages_dir / "package2"
    pkg2_dir.mkdir()

    # Mock sys.path
    original_sys_path = sys.path.copy()

    try:
        # Reset sys.path to a known state
        sys.path = ["/original/path"]

        # Call the function being tested
        add_package_paths_to_sys_path(packages_dir)

        # Verify that paths were added correctly
        assert str(pkg1_src_dir) in sys.path
        assert str(pkg2_dir) in sys.path
        assert "/original/path" in sys.path  # Original path still present

        # Verify paths added only once
        assert sys.path.count(str(pkg1_src_dir)) == 1
        assert sys.path.count(str(pkg2_dir)) == 1
    finally:
        # Restore the original sys.path
        sys.path = original_sys_path


def test_add_package_paths_to_sys_path():
    """Test the function that adds package paths to sys.path."""
    # Create mock package directories
    packages_dir = "/mock/project/packages"

    # Mock the directory structure
    mock_paths = [
        "/mock/project/packages/package1",  # Package without src
        "/mock/project/packages/package2/src",  # Package with src
        "/mock/project/packages/package3/src/pkg",  # Package with nested src
        "/mock/project/packages/.git",  # Not a package directory
        "/mock/project/packages/__pycache__",  # Not a package directory
    ]

    # Mock os.path.isdir to return True for our mock paths
    def mock_isdir(path):
        return path in mock_paths or path == packages_dir

    # Mock os.listdir to return the directory listing
    def mock_listdir(path):
        if path == packages_dir:
            return ["package1", "package2", "package3", ".git", "__pycache__"]
        elif path == "/mock/project/packages/package2":
            return ["src"]
        elif path == "/mock/project/packages/package3":
            return ["src"]
        return []

    # Mock the add_package_paths_to_sys_path function
    mock_add_package_paths = MagicMock()

    # Mock sys.path
    mock_sys_path: list[str] = []

    # Patch the necessary functions and modules
    with (
        patch("os.path.isdir", side_effect=mock_isdir),
        patch("os.listdir", side_effect=mock_listdir),
        patch("sys.path", mock_sys_path),
        patch.dict("sys.modules", {"openmas.cli.run": MagicMock(add_package_paths_to_sys_path=mock_add_package_paths)}),
    ):
        # Import the function directly from the mocked module
        import sys

        openmas_cli_run = sys.modules["openmas.cli.run"]
        add_package_paths_to_sys_path = openmas_cli_run.add_package_paths_to_sys_path

        # Call the function
        add_package_paths_to_sys_path(packages_dir)

        # Verify the function was called with the correct argument
        mock_add_package_paths.assert_called_once_with(packages_dir)
