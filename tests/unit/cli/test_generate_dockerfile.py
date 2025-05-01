"""Tests for the generate_dockerfile CLI command."""

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from openmas.cli.main import generate_dockerfile


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory with a OpenMAS project."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create config with an agent
    config_content = """
name: test_project
version: 0.1.0
agents:
  test_agent: agents/test_agent
shared_paths:
- shared
extension_paths:
- extensions
"""
    project_config = project_dir / "openmas_project.yml"
    project_config.write_text(config_content)

    # Create agent directory
    agent_dir = project_dir / "agents" / "test_agent"
    agent_dir.mkdir(parents=True)

    # Create agent.py
    agent_file = agent_dir / "agent.py"
    agent_file.write_text("# Test agent\n")

    # Create requirements.txt
    req_file = project_dir / "requirements.txt"
    req_file.write_text("openmas>=0.1.0\n")

    yield project_dir

    # Clean up
    if project_dir.exists():
        shutil.rmtree(project_dir)


def test_generate_dockerfile(temp_project_dir):
    """Test generating a Dockerfile for an agent."""
    os.chdir(temp_project_dir)

    with patch("openmas.deployment.generators.DockerfileGenerator") as mock_generator:
        mock_save = MagicMock()
        mock_generator.return_value.save = mock_save

        runner = CliRunner()
        result = runner.invoke(generate_dockerfile, ["test_agent"])

        assert result.exit_code == 0
        assert "Generated Dockerfile for agent 'test_agent'" in result.output

        # Verify DockerfileGenerator.save was called with correct args
        mock_save.assert_called_once()
        call_args = mock_save.call_args[1]
        assert call_args["python_version"] == "3.10"
        assert call_args["app_entrypoint"] == "-m openmas.cli run test_agent"
        assert call_args["requirements_file"] == "requirements.txt"
        assert call_args["use_poetry"] is False
        assert call_args["port"] == 8000


def test_generate_dockerfile_agent_not_found(temp_project_dir):
    """Test generating a Dockerfile for a non-existent agent."""
    os.chdir(temp_project_dir)

    runner = CliRunner()
    result = runner.invoke(generate_dockerfile, ["nonexistent_agent"])

    assert result.exit_code == 1
    assert "Agent 'nonexistent_agent' not found" in result.output


def test_generate_dockerfile_with_options(temp_project_dir):
    """Test generating a Dockerfile with custom options."""
    os.chdir(temp_project_dir)

    with patch("openmas.deployment.generators.DockerfileGenerator") as mock_generator:
        mock_save = MagicMock()
        mock_generator.return_value.save = mock_save

        runner = CliRunner()
        result = runner.invoke(
            generate_dockerfile,
            ["test_agent", "--output-file", "custom-dockerfile", "--python-version", "3.11", "--use-poetry"],
        )

        assert result.exit_code == 0

        # Verify DockerfileGenerator.save was called with correct args
        mock_save.assert_called_once()
        call_args = mock_save.call_args[1]
        assert call_args["output_path"] == Path("custom-dockerfile")
        assert call_args["python_version"] == "3.11"
        assert call_args["use_poetry"] is True
