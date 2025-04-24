"""Tests for the generate-compose command of the deployment CLI."""

import tempfile
import unittest
from pathlib import Path

import yaml

from simple_mas.deployment.cli import generate_compose_from_project_command


class TestGenerateComposeFromProject(unittest.TestCase):
    """Test generating Docker Compose configurations from SimpleMas project files."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for the test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        # Create a SimpleMas project file
        self.project_file = self.root_dir / "simplemas_project.yml"
        self.project_config = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {
                "agent1": "agents/agent1",
                "agent2": "agents/agent2",
                "agent3": "agents/agent3",
            },
            "shared_paths": ["shared"],
            "extension_paths": ["extensions"],
            "default_config": {
                "log_level": "INFO",
                "communicator_type": "http",
            },
        }

        # Create project structure
        (self.root_dir / "agents").mkdir()
        (self.root_dir / "agents" / "agent1").mkdir()
        (self.root_dir / "agents" / "agent2").mkdir()
        (self.root_dir / "agents" / "agent3").mkdir()
        (self.root_dir / "shared").mkdir()
        (self.root_dir / "extensions").mkdir()

        # Create metadata for agent1
        self.agent1_metadata = {
            "version": "1.0",
            "component": {"name": "agent1", "type": "agent", "description": "Agent 1"},
            "docker": {"build": {"context": "."}},
            "environment": [
                {"name": "AGENT_NAME", "value": "agent1"},
                {"name": "LOG_LEVEL", "value": "INFO"},
            ],
            "ports": [{"port": 8000, "protocol": "http", "description": "HTTP API"}],
            "dependencies": [
                {"name": "agent2", "required": True, "description": "Required dependency"},
                {"name": "different-name", "required": False, "description": "Optional dependency"},
            ],
        }

        # Create metadata for agent2
        self.agent2_metadata = {
            "version": "1.0",
            "component": {"name": "agent2", "type": "agent", "description": "Agent 2"},
            "docker": {"build": {"context": "."}},
            "environment": [
                {"name": "AGENT_NAME", "value": "agent2"},
                {"name": "LOG_LEVEL", "value": "INFO"},
            ],
            "ports": [{"port": 8001, "protocol": "http", "description": "HTTP API"}],
            "dependencies": [],
        }

        # Create metadata for agent3
        self.agent3_metadata = {
            "version": "1.0",
            "component": {"name": "different-name", "type": "agent", "description": "Agent 3"},
            "docker": {"build": {"context": "."}},
            "environment": [
                {"name": "AGENT_NAME", "value": "${component.name}"},
                {"name": "LOG_LEVEL", "value": "INFO"},
            ],
            "ports": [{"port": 8002, "protocol": "http", "description": "HTTP API"}],
            "dependencies": [],
        }

        # Write the files
        with open(self.project_file, "w") as f:
            yaml.safe_dump(self.project_config, f)

        with open(self.root_dir / "agents" / "agent1" / "simplemas.deploy.yaml", "w") as f:
            yaml.safe_dump(self.agent1_metadata, f)

        with open(self.root_dir / "agents" / "agent2" / "simplemas.deploy.yaml", "w") as f:
            yaml.safe_dump(self.agent2_metadata, f)

        with open(self.root_dir / "agents" / "agent3" / "simplemas.deploy.yaml", "w") as f:
            yaml.safe_dump(self.agent3_metadata, f)

        # Docker Compose output path
        self.output_path = self.root_dir / "docker-compose.yml"

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_generate_compose_from_project(self):
        """Test generating Docker Compose file from SimpleMas project."""

        # Mock command-line arguments
        class Args:
            project_file = str(self.project_file)
            output = str(self.output_path)
            strict = False
            use_project_names = False

        # Run the command
        result = generate_compose_from_project_command(Args())

        # Check success
        assert result == 0
        assert self.output_path.exists()

        # Load and verify Docker Compose file
        with open(self.output_path, "r") as f:
            compose_data = yaml.safe_load(f)

        # Check basic structure
        assert "version" in compose_data
        assert "services" in compose_data
        assert len(compose_data["services"]) == 3

        # Check service names
        assert "agent1" in compose_data["services"]
        assert "agent2" in compose_data["services"]
        assert "different-name" in compose_data["services"]  # Uses name from metadata

        # Check dependencies
        assert "depends_on" in compose_data["services"]["agent1"]
        assert "agent2" in compose_data["services"]["agent1"]["depends_on"]

        # Check SERVICE_URL environment variables in agent1
        agent1_env = compose_data["services"]["agent1"]["environment"]

        # Check that SERVICE_URL_AGENT2 was added
        assert any(
            env == "SERVICE_URL_AGENT2=http://agent2:8001" or "SERVICE_URL_AGENT2=http://agent2:8001" in env
            for env in agent1_env
        )

        # Check that SERVICE_URL_DIFFERENT_NAME was added
        assert any(
            env == "SERVICE_URL_DIFFERENT_NAME=http://different-name:8002"
            or "SERVICE_URL_DIFFERENT_NAME=http://different-name:8002" in env
            for env in agent1_env
        )

    def test_generate_compose_with_use_project_names(self):
        """Test using project names instead of metadata names."""

        # Mock command-line arguments
        class Args:
            project_file = str(self.project_file)
            output = str(self.output_path)
            strict = False
            use_project_names = True

        # Run the command
        result = generate_compose_from_project_command(Args())

        # Check success
        assert result == 0
        assert self.output_path.exists()

        # Load and verify Docker Compose file
        with open(self.output_path, "r") as f:
            compose_data = yaml.safe_load(f)

        # Check all services use project names
        assert "agent1" in compose_data["services"]
        assert "agent2" in compose_data["services"]
        assert "agent3" in compose_data["services"]  # Now uses name from project file
        assert "different-name" not in compose_data["services"]

        # Check SERVICE_URL environment variables in agent1
        agent1_env = compose_data["services"]["agent1"]["environment"]

        # Check SERVICE_URL for agent3 uses the project name
        assert any(
            env == "SERVICE_URL_AGENT3=http://agent3:8002" or "SERVICE_URL_AGENT3=http://agent3:8002" in env
            for env in agent1_env
        )

    def test_generate_compose_strict_mode(self):
        """Test generating with strict mode when metadata is missing."""
        # Remove metadata file for agent2
        (self.root_dir / "agents" / "agent2" / "simplemas.deploy.yaml").unlink()

        # Mock command-line arguments
        class Args:
            project_file = str(self.project_file)
            output = str(self.output_path)
            strict = True
            use_project_names = False

        # Run the command, should fail in strict mode
        result = generate_compose_from_project_command(Args())
        assert result == 1
        assert not self.output_path.exists()

        # Try again without strict mode, should succeed but skip agent2
        Args.strict = False
        result = generate_compose_from_project_command(Args())
        assert result == 0
        assert self.output_path.exists()

        # Load and verify Docker Compose file
        with open(self.output_path, "r") as f:
            compose_data = yaml.safe_load(f)

        # Should only have agent1 and agent3
        assert len(compose_data["services"]) == 2
        assert "agent1" in compose_data["services"]
        assert "different-name" in compose_data["services"]
        assert "agent2" not in compose_data["services"]
