"""Tests for the CLI utilities module."""

import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml
from pydantic import ValidationError

from openmas.cli.utils import load_project_config
from openmas.config import ProjectConfig


@pytest.fixture
def mock_project_config_data():
    """Create a mock project configuration dictionary."""
    return {
        "name": "test-project",
        "version": "0.1.0",
        "agents": {
            "test_agent": "agents/test_agent",
        },
        "assets": [
            {
                "name": "model",
                "version": "1.0.0",
                "source": {
                    "type": "http",
                    "url": "https://example.com/model.bin",
                },
            }
        ],
    }


@pytest.fixture
def mock_project_config(mock_project_config_data):
    """Create a mock ProjectConfig instance."""
    return ProjectConfig.model_validate(mock_project_config_data)


def patch_path_exists(paths_exist):
    """Create a patched version of Path.exists that returns True for specified paths."""
    orig_exists = Path.exists

    def _patched_exists(self):
        path_str = str(self)
        if path_str in paths_exist:
            return True
        return orig_exists(self)

    return _patched_exists


@patch("openmas.cli.utils.open", new_callable=mock_open)
@patch("openmas.cli.utils.yaml.safe_load")
@patch("openmas.cli.utils.ProjectConfig.model_validate")
def test_load_project_config_from_env(
    mock_validate, mock_yaml_load, mock_file, mock_project_config, mock_project_config_data
):
    """Test loading the project configuration from the environment variable."""
    # Setup mocks
    mock_yaml_load.return_value = mock_project_config_data
    mock_validate.return_value = mock_project_config

    env_path = "/path/to/openmas_project.yml"
    # Patch Path.exists to return True for our file
    with patch.object(Path, "exists", return_value=True):
        # Set environment variable
        with patch.dict(os.environ, {"OPENMAS_PROJECT_PATH": env_path}):
            # Call the function
            result = load_project_config()

            # Verify the result
            assert result == mock_project_config
            # Check that the file was opened correctly (match the Path object)
            mock_file.assert_called_once()
            call_args = mock_file.call_args[0]
            assert str(call_args[0]) == env_path
            assert call_args[1] == "r"


@patch("openmas.cli.utils.open", new_callable=mock_open)
@patch("openmas.cli.utils.yaml.safe_load")
@patch("openmas.cli.utils.ProjectConfig.model_validate")
def test_load_project_config_from_explicit_path(
    mock_validate, mock_yaml_load, mock_file, mock_project_config, mock_project_config_data
):
    """Test loading the project configuration from an explicit path."""
    # Setup mocks
    mock_yaml_load.return_value = mock_project_config_data
    mock_validate.return_value = mock_project_config

    explicit_path = "/explicit/path"
    project_file = f"{explicit_path}/openmas_project.yml"

    # Patch Path.exists to return True for our file
    with patch.object(Path, "exists", return_value=True):
        # Call the function with an explicit path
        result = load_project_config(Path(explicit_path))

        # Verify the result
        assert result == mock_project_config
        # Check that the file was opened correctly (match the Path object)
        mock_file.assert_called_once()
        call_args = mock_file.call_args[0]
        assert str(call_args[0]) == project_file
        assert call_args[1] == "r"


@patch("openmas.cli.utils.Path.cwd")
@patch("openmas.cli.utils.open", new_callable=mock_open)
@patch("openmas.cli.utils.yaml.safe_load")
@patch("openmas.cli.utils.ProjectConfig.model_validate")
def test_load_project_config_from_current_dir(
    mock_validate, mock_yaml_load, mock_file, mock_cwd, mock_project_config, mock_project_config_data
):
    """Test loading the project configuration from the current directory."""
    # Setup mocks
    current_dir = "/current/dir"
    mock_cwd.return_value = Path(current_dir)
    mock_yaml_load.return_value = mock_project_config_data
    mock_validate.return_value = mock_project_config

    project_file = f"{current_dir}/openmas_project.yml"

    # Create a patched version of Path.exists
    patched_exists = patch_path_exists([project_file])

    # Apply the patch
    with patch.object(Path, "exists", patched_exists):
        # Call the function
        result = load_project_config()

        # Verify the result
        assert result == mock_project_config
        # Check that the file was opened correctly (match the Path object)
        mock_file.assert_called_once()
        call_args = mock_file.call_args[0]
        assert str(call_args[0]) == project_file
        assert call_args[1] == "r"


@patch("openmas.cli.utils.Path.cwd")
@patch("openmas.cli.utils.open", new_callable=mock_open)
@patch("openmas.cli.utils.yaml.safe_load")
@patch("openmas.cli.utils.ProjectConfig.model_validate")
def test_load_project_config_from_parent_dir(
    mock_validate, mock_yaml_load, mock_file, mock_cwd, mock_project_config, mock_project_config_data
):
    """Test loading the project configuration from a parent directory."""
    # Setup mocks
    current_dir = "/current/dir"
    parent_dir = "/current"
    mock_cwd.return_value = Path(current_dir)
    mock_yaml_load.return_value = mock_project_config_data
    mock_validate.return_value = mock_project_config

    _ = f"{current_dir}/openmas_project.yml"
    parent_project_file = f"{parent_dir}/openmas_project.yml"

    # Create a patched version of Path.exists that only returns True for the parent dir's file
    def patched_exists(self):
        path_str = str(self)
        return path_str == parent_project_file

    # Apply the patch
    with patch.object(Path, "exists", patched_exists):
        # Call the function
        result = load_project_config()

        # Verify the result
        assert result == mock_project_config
        # Check that the file was opened correctly (match the Path object)
        mock_file.assert_called_once()
        call_args = mock_file.call_args[0]
        assert str(call_args[0]) == parent_project_file
        assert call_args[1] == "r"


@patch("openmas.cli.utils.Path.cwd")
def test_load_project_config_file_not_found(mock_cwd):
    """Test handling of a missing project configuration file."""
    # Setup mocks
    mock_cwd.return_value = Path("/current/dir")

    # Patch Path.exists to always return False
    with patch.object(Path, "exists", return_value=False):
        # Call the function and expect an exception
        with pytest.raises(FileNotFoundError):
            load_project_config()


@patch("openmas.cli.utils.open", new_callable=mock_open)
@patch("openmas.cli.utils.yaml.safe_load")
def test_load_project_config_yaml_error(mock_yaml_load, mock_file):
    """Test handling of YAML parsing errors."""
    # Setup mocks
    mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML")

    # Patch Path.exists to return True
    with patch.object(Path, "exists", return_value=True):
        # Call the function and expect an exception
        with pytest.raises(ValueError) as excinfo:
            load_project_config(Path("/explicit/path"))

        assert "Failed to parse openmas_project.yml" in str(excinfo.value)


@patch("openmas.cli.utils.open", new_callable=mock_open)
@patch("openmas.cli.utils.yaml.safe_load")
@patch("openmas.cli.utils.ProjectConfig.model_validate")
def test_load_project_config_validation_error(mock_validate, mock_yaml_load, mock_file):
    """Test handling of configuration validation errors."""
    # Setup mocks
    mock_yaml_load.return_value = {"name": "test-project"}  # Missing required fields
    mock_validate.side_effect = ValidationError.from_exception_data(
        title="ValidationError",
        line_errors=[{"type": "missing", "loc": ("agents",), "input": {"name": "test-project"}}],
    )

    # Patch Path.exists to return True
    with patch.object(Path, "exists", return_value=True):
        # Call the function and expect an exception
        with pytest.raises(ValueError) as excinfo:
            load_project_config(Path("/explicit/path"))

        assert "Invalid configuration in openmas_project.yml" in str(excinfo.value)
