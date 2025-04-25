"""Additional tests for the generate_dockerfile command in the OpenMAS CLI."""

from unittest.mock import patch

import pytest

from openmas.cli.deploy import _generate_dockerfile_impl
from openmas.deployment.generators import DockerfileGenerator


@pytest.fixture
def mock_project_dir(tmp_path):
    """Create a mock project directory for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create required directories
    subdirs = ["agents", "shared", "extensions", "config"]
    for subdir in subdirs:
        (project_dir / subdir).mkdir()

    return project_dir


def test_dockerfile_generation_poetry(mock_project_dir, tmp_path):
    """Test that the CLI command generates a Dockerfile with Poetry."""
    # Setup
    dockerfile_path = tmp_path / "Dockerfile.poetry"

    with patch("typer.confirm") as mock_confirm:
        mock_confirm.return_value = True  # Confirm overwrite if file exists

        # Call the implementation function directly
        result = _generate_dockerfile_impl(
            python_version="3.10",
            app_entrypoint="app.py",
            requirements_file="requirements.txt",
            use_poetry=True,
            port=8000,
            output=str(dockerfile_path),
        )

        # Verify
        assert result == 0
        assert dockerfile_path.exists()

        # Check content contains Poetry-specific elements
        content = dockerfile_path.read_text()
        assert "RUN pip install --no-cache-dir poetry" in content
        assert "COPY pyproject.toml poetry.lock*" in content
        assert "RUN poetry install" in content
        assert 'CMD ["poetry", "run", "python", "app.py"]' in content


def test_dockerfile_generation_custom_python(mock_project_dir, tmp_path):
    """Test that the CLI command generates a Dockerfile with custom Python version."""
    # Setup
    dockerfile_path = tmp_path / "Dockerfile.custom_python"
    custom_python_version = "3.11"

    with patch("typer.confirm") as mock_confirm:
        mock_confirm.return_value = True  # Confirm overwrite if file exists

        # Call the implementation function directly
        result = _generate_dockerfile_impl(
            python_version=custom_python_version,
            app_entrypoint="main.py",
            requirements_file="requirements.txt",
            use_poetry=False,
            port=9000,
            output=str(dockerfile_path),
        )

        # Verify
        assert result == 0
        assert dockerfile_path.exists()

        # Check content contains the custom Python version
        content = dockerfile_path.read_text()
        assert f"FROM python:{custom_python_version}-slim" in content
        assert "COPY requirements.txt" in content
        assert "RUN pip install --no-cache-dir -r requirements.txt" in content
        assert "EXPOSE 9000" in content
        assert 'CMD ["python", "main.py"]' in content


def test_dockerfile_generator_direct_usage():
    """Test the DockerfileGenerator class directly."""
    generator = DockerfileGenerator()

    # Test pip-based Dockerfile generation
    pip_dockerfile = generator.generate_pip_dockerfile(
        python_version="3.9", app_entrypoint="server.py", requirements_file="requirements.txt", port=8080
    )

    assert "FROM python:3.9-slim" in pip_dockerfile
    assert "COPY requirements.txt" in pip_dockerfile
    assert "EXPOSE 8080" in pip_dockerfile
    assert 'CMD ["python", "server.py"]' in pip_dockerfile

    # Test poetry-based Dockerfile generation
    poetry_dockerfile = generator.generate_poetry_dockerfile(python_version="3.10", app_entrypoint="app.py", port=5000)

    assert "FROM python:3.10-slim" in poetry_dockerfile
    assert "RUN pip install --no-cache-dir poetry" in poetry_dockerfile
    assert "COPY pyproject.toml poetry.lock*" in poetry_dockerfile
    assert "EXPOSE 5000" in poetry_dockerfile
    assert 'CMD ["poetry", "run", "python", "app.py"]' in poetry_dockerfile


def test_dockerfile_generation_file_exists(tmp_path):
    """Test handling the case where the output file already exists."""
    # Create a file that already exists
    dockerfile_path = tmp_path / "existing_dockerfile"
    dockerfile_path.write_text("EXISTING CONTENT")

    # Test with user confirming overwrite
    with patch("typer.confirm") as mock_confirm:
        mock_confirm.return_value = True  # User confirms overwrite

        result = _generate_dockerfile_impl(
            python_version="3.10",
            app_entrypoint="app.py",
            requirements_file="requirements.txt",
            use_poetry=False,
            port=8000,
            output=str(dockerfile_path),
        )

        assert result == 0
        assert "EXISTING CONTENT" not in dockerfile_path.read_text()
        assert "FROM python:3.10-slim" in dockerfile_path.read_text()

    # Reset the file
    dockerfile_path.write_text("EXISTING CONTENT")

    # Test with user declining overwrite
    with patch("typer.confirm") as mock_confirm:
        mock_confirm.return_value = False  # User declines overwrite

        result = _generate_dockerfile_impl(
            python_version="3.10",
            app_entrypoint="app.py",
            requirements_file="requirements.txt",
            use_poetry=False,
            port=8000,
            output=str(dockerfile_path),
        )

        assert result == 1  # Should return non-zero for abort
        assert "EXISTING CONTENT" in dockerfile_path.read_text()  # Original content preserved
