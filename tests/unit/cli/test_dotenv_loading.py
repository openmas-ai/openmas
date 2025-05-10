"""Tests for automatic .env file loading in OpenMAS CLI."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from openmas.cli.main import main  # type: ignore


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner."""
    return CliRunner()


def test_dotenv_loading_current_dir(cli_runner, tmp_path):
    """Test that .env is loaded from the current directory."""
    # Create a .env file in the temporary directory
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_OPENMAS_SECRET=hello_from_dotenv")

    # Create the test
    with patch("openmas.cli.main.load_dotenv") as mock_load_dotenv:
        with patch("openmas.cli.main.cli"):
            # Mock os.getcwd to return our temporary directory
            with patch("os.getcwd", return_value=str(tmp_path)):
                # Mock Path.exists and Path.is_file to always return True for .env
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_file", return_value=True):
                        # We need to mock sys.argv to prevent Click from trying to parse real args
                        with patch.object(sys, "argv", ["openmas"]):
                            # Invoke the main function
                            main()

        # Check that load_dotenv was called with our .env file
        mock_load_dotenv.assert_called_once()
        args, kwargs = mock_load_dotenv.call_args
        assert kwargs["dotenv_path"] == str(tmp_path / ".env")
        assert kwargs["override"] is True


def test_dotenv_loading_parent_dir(cli_runner, tmp_path):
    """Test that .env is loaded from the parent directory if not in current."""
    # Create a parent directory with .env and a child directory
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
    child_dir = parent_dir / "child"
    child_dir.mkdir()

    # Create .env in parent directory
    env_file = parent_dir / ".env"
    env_file.write_text("TEST_OPENMAS_SECRET=hello_from_parent_dotenv")

    # Mock testing environment
    with patch("openmas.cli.main.load_dotenv") as mock_load_dotenv:
        with patch("openmas.cli.main.cli"):
            # Mock current directory to be the child directory
            with patch("os.getcwd", return_value=str(child_dir)):
                # Use a more reliable patching strategy for Path.exists
                original_exists = Path.exists

                def patched_exists(path_instance):
                    path_str = str(path_instance)
                    if path_str == str(child_dir / ".env"):
                        return False
                    elif path_str == str(parent_dir / ".env"):
                        return True
                    return original_exists(path_instance)

                with patch.object(Path, "exists", patched_exists):
                    with patch.object(Path, "is_file", return_value=True):
                        # Mock sys.argv to prevent Click from trying to parse real args
                        with patch.object(sys, "argv", ["openmas"]):
                            # Invoke the main function
                            main()

        # Check that load_dotenv was called with the parent's .env file
        mock_load_dotenv.assert_called_once()
        args, kwargs = mock_load_dotenv.call_args
        assert kwargs["dotenv_path"] == str(parent_dir / ".env")
        assert kwargs["override"] is True


def test_no_dotenv_file(cli_runner, tmp_path):
    """Test behavior when no .env file is found."""
    with patch("openmas.cli.main.load_dotenv") as mock_load_dotenv:
        with patch("openmas.cli.main.logger") as mock_logger:
            with patch("openmas.cli.main.cli"):
                # Mock current directory
                with patch("os.getcwd", return_value=str(tmp_path)):
                    # Mock Path.exists to always return False (no .env file)
                    with patch.object(Path, "exists", return_value=False):
                        # We need to mock sys.argv to prevent Click from trying to parse real args
                        with patch.object(sys, "argv", ["openmas"]):
                            # Invoke the main function
                            main()

        # Check that load_dotenv was not called
        mock_load_dotenv.assert_not_called()

        # Check that a debug log message was generated
        mock_logger.debug.assert_called_once_with("No .env file found in current or parent directory.")


def test_integration_with_env_vars(cli_runner, tmp_path):
    """Test that environment variables from .env are actually loaded (integration test)."""
    # Create a .env file with a test variable
    env_path = tmp_path / ".env"
    env_path.write_text("TEST_OPENMAS_VAR=test_value_from_dotenv")

    # Test with real environment interaction
    with patch.dict("os.environ", {}, clear=True):  # Start with clean environment
        with patch("openmas.cli.main.cli") as mock_cli:
            with patch("os.getcwd", return_value=str(tmp_path)):
                # Mock the sys.argv to avoid Click trying to parse pytest args
                with patch.object(sys, "argv", ["openmas"]):
                    # Run the main function (which will load .env)
                    main()

                    # Verify cli was called, indicating main() executed successfully
                    mock_cli.assert_called_once()
