"""Tests for the Dockerfile generation command."""

import os
import tempfile
from unittest.mock import patch

from simple_mas.cli.deploy import _generate_dockerfile_impl, _generate_pip_dockerfile, _generate_poetry_dockerfile


class TestDockerfileGeneration:
    """Test the Dockerfile generation functionality."""

    def test_generate_pip_dockerfile(self):
        """Test generating a Dockerfile with pip dependencies."""
        dockerfile = _generate_pip_dockerfile(
            python_version="3.10",
            app_entrypoint="agent.py",
            requirements_file="requirements.txt",
            port=8000,
        )

        # Check that essential elements are present
        assert "FROM python:3.10-slim" in dockerfile
        assert "COPY requirements.txt ." in dockerfile
        assert "RUN pip install --no-cache-dir -r requirements.txt" in dockerfile
        assert "EXPOSE 8000" in dockerfile
        assert 'CMD ["python", "agent.py"]' in dockerfile
        assert "AGENT_PORT=8000" in dockerfile

    def test_generate_poetry_dockerfile(self):
        """Test generating a Dockerfile with Poetry dependencies."""
        dockerfile = _generate_poetry_dockerfile(
            python_version="3.10",
            app_entrypoint="agent.py",
            port=8000,
        )

        # Check that essential elements are present
        assert "FROM python:3.10-slim" in dockerfile
        assert "RUN pip install --no-cache-dir poetry" in dockerfile
        assert "COPY pyproject.toml poetry.lock* ./" in dockerfile
        assert "RUN poetry install --no-dev" in dockerfile
        assert "EXPOSE 8000" in dockerfile
        assert 'CMD ["poetry", "run", "python", "agent.py"]' in dockerfile
        assert "AGENT_PORT=8000" in dockerfile

    @patch("builtins.open")
    @patch("pathlib.Path.exists")
    @patch("typer.confirm")
    def test_generate_dockerfile_command_file_exists(self, mock_confirm, mock_exists, mock_open):
        """Test the generate-dockerfile command when output file exists."""
        # Setup mocks
        mock_exists.return_value = True
        mock_confirm.return_value = True

        # Run command directly (not using CliRunner)
        result = _generate_dockerfile_impl(
            python_version="3.11",
            app_entrypoint="main.py",
            requirements_file="requirements.txt",
            use_poetry=False,
            port=8000,
            output="Dockerfile",
        )

        # Check that confirmation was requested
        mock_confirm.assert_called_once()
        # Check that file was written
        mock_open.assert_called_once()
        # Check exit code
        assert result == 0

    @patch("builtins.open")
    @patch("pathlib.Path.exists")
    def test_generate_dockerfile_command_new_file(self, mock_exists, mock_open):
        """Test the generate-dockerfile command when output file doesn't exist."""
        # Setup mocks
        mock_exists.return_value = False

        # Run command directly (not using CliRunner)
        result = _generate_dockerfile_impl(
            python_version="3.11",
            app_entrypoint="main.py",
            requirements_file="requirements.txt",
            use_poetry=False,
            port=8000,
            output="Dockerfile",
        )

        # Check that file was written without confirmation
        mock_open.assert_called_once()
        # Check exit code
        assert result == 0

    @patch("builtins.open")
    @patch("pathlib.Path.exists")
    def test_generate_dockerfile_command_with_poetry(self, mock_exists, mock_open):
        """Test the generate-dockerfile command with Poetry option."""
        # Setup mocks
        mock_exists.return_value = False

        # Run command directly (not using CliRunner)
        result = _generate_dockerfile_impl(
            python_version="3.11",
            app_entrypoint="main.py",
            requirements_file="requirements.txt",
            use_poetry=True,
            port=8000,
            output="Dockerfile",
        )

        # Check that file was written
        mock_open.assert_called_once()
        # Check exit code
        assert result == 0

    def test_generate_dockerfile_end_to_end(self):
        """Test the generate-dockerfile command with actual file writing."""
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "Dockerfile")

            # Run command directly (not using CliRunner)
            result = _generate_dockerfile_impl(
                python_version="3.11",
                app_entrypoint="agent.py",
                requirements_file="requirements.txt",
                use_poetry=False,
                port=8000,
                output=output_path,
            )

            # Check exit code
            assert result == 0

            # Check that file was created
            assert os.path.exists(output_path)

            # Check file contents
            with open(output_path, "r") as f:
                content = f.read()
                assert "FROM python:3.11-slim" in content
                assert 'CMD ["python", "agent.py"]' in content
