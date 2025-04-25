"""Tests for the OpenMAS CLI deploy module."""

import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner as TyperCliRunner  # type: ignore # noqa

from openmas.cli.deploy import (
    _configure_service_urls,
    _generate_compose_from_project_impl,
    _generate_dockerfile_impl,
    _generate_pip_dockerfile,
    _generate_poetry_dockerfile,
    app,
    discover_metadata,
    process_manifest,
)


@pytest.fixture
def sample_metadata_file():
    """Create a temporary file with deployment metadata."""
    with tempfile.TemporaryDirectory() as temp_dir:
        metadata_path = Path(temp_dir) / "openmas.deploy.yaml"

        metadata = {
            "version": "1.0",
            "component": {"name": "test-agent", "type": "agent", "description": "Test agent for deployment"},
            "docker": {"build": {"context": ".", "dockerfile": "Dockerfile"}},
            "environment": [
                {"name": "AGENT_NAME", "value": "test-agent"},
                {"name": "LOG_LEVEL", "value": "INFO"},
                {"name": "API_KEY", "secret": True, "description": "API key for external service"},
            ],
            "ports": [{"port": 8000, "protocol": "http", "description": "Agent API"}],
            "volumes": [{"name": "data", "path": "/app/data", "description": "Data volume"}],
            "dependencies": [{"name": "database", "required": True, "description": "Database service"}],
        }

        with open(metadata_path, "w") as f:
            yaml.safe_dump(metadata, f)

        yield temp_dir


@pytest.fixture
def sample_project_file():
    """Create a temporary project file with agent configurations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)

        # Create the project YAML file
        project_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {
                "agent1": "agents/agent1",
                "agent2": "agents/agent2",
            },
        }

        project_file = project_dir / "openmas_project.yml"
        with open(project_file, "w") as f:
            yaml.safe_dump(project_data, f)

        # Create agent1 directory with deployment metadata
        agent1_dir = project_dir / "agents" / "agent1"
        agent1_dir.mkdir(parents=True, exist_ok=True)

        agent1_metadata = {
            "version": "1.0",
            "component": {"name": "agent1", "type": "agent", "description": "Agent 1"},
            "docker": {"build": {"context": ".", "dockerfile": "Dockerfile"}},
            "ports": [{"port": 8001, "protocol": "http"}],
        }

        with open(agent1_dir / "openmas.deploy.yaml", "w") as f:
            yaml.safe_dump(agent1_metadata, f)

        # Create agent2 directory with deployment metadata
        agent2_dir = project_dir / "agents" / "agent2"
        agent2_dir.mkdir(parents=True, exist_ok=True)

        agent2_metadata = {
            "version": "1.0",
            "component": {"name": "agent2", "type": "agent", "description": "Agent 2"},
            "docker": {"build": {"context": ".", "dockerfile": "Dockerfile"}},
            "ports": [{"port": 8002, "protocol": "http"}],
        }

        with open(agent2_dir / "openmas.deploy.yaml", "w") as f:
            yaml.safe_dump(agent2_metadata, f)

        yield project_dir


def test_discover_metadata(sample_metadata_file):
    """Test discovering deployment metadata from a directory."""
    metadata = discover_metadata(sample_metadata_file)

    assert metadata.version == "1.0"
    assert metadata.component.name == "test-agent"
    assert metadata.component.type == "agent"
    assert metadata.docker.build.context == "."
    assert len(metadata.environment) == 3
    assert len(metadata.ports) == 1
    assert len(metadata.volumes) == 1
    assert len(metadata.dependencies) == 1


def test_discover_metadata_not_found():
    """Test discovering metadata from a directory where it doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(FileNotFoundError):
            discover_metadata(temp_dir)


def test_inspect_deployment(sample_metadata_file):
    """Test inspecting deployment metadata."""
    runner = TyperCliRunner()
    result = runner.invoke(app, ["inspect", sample_metadata_file])

    assert result.exit_code == 0
    assert "Component: test-agent" in result.stdout
    assert "Type: agent" in result.stdout
    assert "Environment Variables:" in result.stdout
    assert "Ports:" in result.stdout
    assert "Volumes:" in result.stdout
    assert "Dependencies:" in result.stdout


def test_inspect_deployment_wide(sample_metadata_file):
    """Test inspecting deployment metadata with wide output."""
    runner = TyperCliRunner()
    result = runner.invoke(app, ["inspect", sample_metadata_file, "--wide"])

    assert result.exit_code == 0
    assert "Component: test-agent" in result.stdout
    assert "Type: agent" in result.stdout
    assert "Environment Variables:" in result.stdout
    assert "(secret)" in result.stdout  # Check that secret flag appears somewhere in the output
    assert "Ports:" in result.stdout
    assert "Volumes:" in result.stdout
    assert "Dependencies:" in result.stdout


@patch("yaml.safe_dump")
@patch("builtins.open", new_callable=MagicMock)
@patch("openmas.cli.deploy.DockerComposeGenerator")
@patch("openmas.cli.deploy.discover_metadata")
def test_generate_compose(mock_discover, mock_generator, mock_open, mock_yaml_dump, sample_metadata_file):
    """Test generating Docker Compose configuration."""
    # Set up mocks
    mock_metadata = MagicMock()
    mock_discover.return_value = mock_metadata

    mock_compose = {"version": "3", "services": {}}
    mock_generator.return_value.generate.return_value = mock_compose

    runner = TyperCliRunner()
    result = runner.invoke(app, ["generate-compose", sample_metadata_file])

    assert result.exit_code == 0
    assert "Docker Compose configuration saved to" in result.stdout
    mock_discover.assert_called_once_with(sample_metadata_file)
    mock_generator.return_value.generate.assert_called_once_with(mock_metadata)
    mock_yaml_dump.assert_called_once_with(mock_compose, mock_open().__enter__(), sort_keys=False)


@patch("openmas.cli.deploy.ComposeOrchestrator")
@patch("openmas.deployment.orchestration.OrchestrationManifest")
def test_process_manifest(mock_manifest_class, mock_orchestrator):
    """Test processing a manifest file."""
    # Setup mocks
    # Create mock metadata objects and component paths
    metadata1 = MagicMock()
    metadata1.component.name = "component1"
    component_path = Path("/path/to/component1")

    # Mock returns
    mock_manifest_class.return_value.get_component_paths.return_value = [component_path]

    # Mock DeploymentMetadata.from_file
    with patch("openmas.deployment.metadata.DeploymentMetadata.from_file") as mock_from_file:
        with patch("pathlib.Path.exists", return_value=True):  # Mock exists check on metadata file
            mock_from_file.return_value = metadata1

            # Call the function
            result = process_manifest("manifest.yaml", "docker-compose.yaml")

            # Check the result
            assert result == 0

            # Verify calls
            mock_manifest_class.assert_called_once_with("manifest.yaml")
            mock_from_file.assert_called_once()
            mock_orchestrator.return_value.save_compose.assert_called_once_with([metadata1], "docker-compose.yaml")


@patch("openmas.cli.deploy.typer.confirm")
@patch("builtins.open", new_callable=MagicMock)
@patch("pathlib.Path.exists")
def test_generate_dockerfile_impl_file_exists(mock_exists, mock_open, mock_confirm):
    """Test generating a Dockerfile when the file already exists."""
    # Set up mocks
    mock_exists.return_value = True
    mock_confirm.return_value = True  # Simulate user confirming to overwrite
    mock_file = mock_open.return_value.__enter__.return_value

    # Call the function with correct parameters
    result = _generate_dockerfile_impl(
        python_version="3.10",
        app_entrypoint="agent.py",
        requirements_file="requirements.txt",
        use_poetry=False,
        port=8000,
        output="Dockerfile",
    )

    # Verify the result
    assert result == 0
    mock_confirm.assert_called_once()
    mock_file.write.assert_called_once()
    assert "FROM python:3.10-slim" in mock_file.write.call_args[0][0]


@patch("openmas.cli.deploy.typer.confirm")
@patch("builtins.open", new_callable=MagicMock)
@patch("pathlib.Path.exists")
def test_generate_dockerfile_impl_abort(mock_exists, mock_open, mock_confirm):
    """Test aborting Dockerfile generation when the user declines to overwrite."""
    # Set up mocks
    mock_exists.return_value = True
    mock_confirm.return_value = False  # Simulate user declining to overwrite

    # Call the function
    result = _generate_dockerfile_impl(
        python_version="3.10",
        app_entrypoint="agent.py",
        requirements_file="requirements.txt",
        use_poetry=False,
        port=8000,
        output="Dockerfile",
    )

    # Verify the result
    assert result == 1
    mock_confirm.assert_called_once()
    mock_open.assert_not_called()


def test_generate_pip_dockerfile():
    """Test generating a Dockerfile using pip for dependencies."""
    dockerfile = _generate_pip_dockerfile(
        python_version="3.10",
        app_entrypoint="agent.py",
        requirements_file="requirements.txt",
        port=8000,
    )

    assert "FROM python:3.10-slim" in dockerfile
    assert "COPY requirements.txt ." in dockerfile
    assert "RUN pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert 'CMD ["python", "agent.py"]' in dockerfile
    assert "AGENT_PORT=8000" in dockerfile


def test_generate_poetry_dockerfile():
    """Test generating a Dockerfile using Poetry for dependencies."""
    dockerfile = _generate_poetry_dockerfile(
        python_version="3.10",
        app_entrypoint="agent.py",
        port=8000,
    )

    assert "FROM python:3.10-slim" in dockerfile
    assert "RUN pip install --no-cache-dir poetry" in dockerfile
    assert "COPY pyproject.toml poetry.lock* ./" in dockerfile
    assert "RUN poetry install" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert 'CMD ["poetry", "run", "python", "agent.py"]' in dockerfile
    assert "AGENT_PORT=8000" in dockerfile


def test_configure_service_urls():
    """Test configuring service URLs between components."""
    # Setup test components
    component1 = MagicMock()
    component1.component.name = "agent1"
    component1.ports = [MagicMock(port=8001, protocol="http")]
    component1.environment = []

    # Create a dependency mock with a proper name attribute
    dependency1 = MagicMock()
    dependency1.name = "agent2"
    component1.dependencies = [dependency1]

    component2 = MagicMock()
    component2.component.name = "agent2"
    component2.ports = [MagicMock(port=8002, protocol="http")]
    component2.environment = []

    # Create a dependency mock with a proper name attribute
    dependency2 = MagicMock()
    dependency2.name = "agent1"
    component2.dependencies = [dependency2]

    components = [component1, component2]

    # Call the function
    result = _configure_service_urls(components)

    # Check the results
    assert len(result) == 2

    # At this point, the function should have added SERVICE_URL environment variables
    # to each component
    for component in result:
        if component.component.name == "agent1":
            # Check that agent1 has a SERVICE_URL for agent2
            env_vars = [e for e in component.environment if "SERVICE_URL" in e.name]
            assert len(env_vars) >= 1
            # Check the URL is correct
            agent2_env_var = next((e for e in env_vars if "AGENT2" in e.name), None)
            assert agent2_env_var is not None
            assert agent2_env_var.value == "http://agent2:8002"
        elif component.component.name == "agent2":
            # Check that agent2 has a SERVICE_URL for agent1
            env_vars = [e for e in component.environment if "SERVICE_URL" in e.name]
            assert len(env_vars) >= 1
            # Check the URL is correct
            agent1_env_var = next((e for e in env_vars if "AGENT1" in e.name), None)
            assert agent1_env_var is not None
            assert agent1_env_var.value == "http://agent1:8001"


@patch("openmas.cli.deploy.ComposeOrchestrator")
def test_generate_compose_from_project_impl(mock_orchestrator):
    """Test generating Docker Compose configuration from a project file."""
    # Create a sample project file
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)

        # Create the project YAML file
        project_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {
                "agent1": "agents/agent1",
                "agent2": "agents/agent2",
            },
        }

        project_file = project_dir / "openmas_project.yml"
        with open(project_file, "w") as f:
            yaml.safe_dump(project_data, f)

        # Set up the ComposeOrchestrator mock
        # Setup the mock to return components and other data
        metadata1 = MagicMock()
        metadata1.component.name = "agent1"
        metadata2 = MagicMock()
        metadata2.component.name = "agent2"
        components = [metadata1, metadata2]
        warnings: List[str] = []
        renamed: Dict[str, str] = {}

        mock_orchestrator.return_value.process_project_file.return_value = (components, warnings, renamed)
        mock_orchestrator.return_value.save_compose.return_value = Path("docker-compose.yaml")

        # Mock _configure_service_urls to return the same components
        with patch("openmas.cli.deploy._configure_service_urls") as mock_configure_urls:
            mock_configure_urls.return_value = components

            # Call the function
            result = _generate_compose_from_project_impl(
                project_file=str(project_file), output="docker-compose.yaml", strict=False, use_project_names=True
            )

            # Verify the function executed successfully
            assert result == 0

            # Verify that process_project_file was called with correct args
            mock_orchestrator.return_value.process_project_file.assert_called_once()

            # Verify that save_compose was called
            mock_orchestrator.return_value.save_compose.assert_called_once_with(components, "docker-compose.yaml")

            # Verify that _configure_service_urls was called
            mock_configure_urls.assert_called_once_with(components)
