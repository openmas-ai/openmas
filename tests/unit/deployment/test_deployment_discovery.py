"""Tests for the deployment discovery module."""

import tempfile
import unittest
from pathlib import Path

import yaml

from openmas.deployment.discovery import ComponentDiscovery
from openmas.deployment.metadata import DeploymentMetadata
from openmas.deployment.orchestration import ComposeOrchestrator


class TestComponentDiscovery(unittest.TestCase):
    """Test the component discovery mechanism."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory structure with test metadata files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        # Create agent1 directory and metadata
        self.agent1_dir = self.root_dir / "agent1"
        self.agent1_dir.mkdir(parents=True)
        self.agent1_metadata = {
            "version": "1.0",
            "component": {"name": "agent1", "type": "agent", "description": "Agent 1"},
            "docker": {"build": {"context": "."}},
            "environment": [{"name": "AGENT_NAME", "value": "${component.name}"}],
            "ports": [{"port": 8000, "protocol": "http"}],
            "dependencies": [{"name": "agent2", "required": True}],
        }

        with open(self.agent1_dir / "openmas.deploy.yaml", "w") as f:
            yaml.safe_dump(self.agent1_metadata, f)

        # Create agent2 directory and metadata
        self.agent2_dir = self.root_dir / "agent2"
        self.agent2_dir.mkdir(parents=True)
        self.agent2_metadata = {
            "version": "1.0",
            "component": {"name": "agent2", "type": "agent", "description": "Agent 2"},
            "docker": {"build": {"context": "."}},
            "environment": [{"name": "AGENT_NAME", "value": "${component.name}"}],
            "ports": [{"port": 8001, "protocol": "http"}],
        }

        with open(self.agent2_dir / "openmas.deploy.yaml", "w") as f:
            yaml.safe_dump(self.agent2_metadata, f)

        # Create a subdirectory with another agent
        self.nested_dir = self.root_dir / "nested" / "subdir"
        self.nested_dir.mkdir(parents=True)
        self.nested_metadata = {
            "version": "1.0",
            "component": {"name": "nested-agent", "type": "agent", "description": "Nested Agent"},
            "docker": {"build": {"context": "."}},
            "environment": [],
            "ports": [],
        }

        with open(self.nested_dir / "openmas.deploy.yaml", "w") as f:
            yaml.safe_dump(self.nested_metadata, f)

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_discover_components(self):
        """Test discovering components from directories."""
        discoverer = ComponentDiscovery()
        components = discoverer.discover_components(self.root_dir)

        # Should find all three components
        assert len(components) == 3

        # Check component names
        component_names = set(c.component.name for c in components)
        assert component_names == {"agent1", "agent2", "nested-agent"}

        # Check that dependency information is preserved
        agent1 = next(c for c in components if c.component.name == "agent1")
        assert len(agent1.dependencies) == 1
        assert agent1.dependencies[0].name == "agent2"

    def test_discover_with_pattern(self):
        """Test discovering components with a glob pattern."""
        discoverer = ComponentDiscovery()
        components = discoverer.discover_components(self.root_dir, pattern="**/openmas.deploy.yaml")

        # Should find all three components
        assert len(components) == 3

        # Test with a more specific pattern
        components = discoverer.discover_components(self.root_dir, pattern="agent*/openmas.deploy.yaml")

        # Should find only agent1 and agent2
        assert len(components) == 2
        component_names = set(c.component.name for c in components)
        assert component_names == {"agent1", "agent2"}


class TestComposeOrchestrator(unittest.TestCase):
    """Test the Docker Compose orchestrator."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory structure with test metadata files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        # Create metadata for two agents
        self.agent1_metadata = DeploymentMetadata(
            version="1.0",
            component={"name": "agent1", "type": "agent", "description": "Agent 1"},
            docker={"build": {"context": "./agent1"}},
            environment=[
                {"name": "AGENT_NAME", "value": "agent1"},
                {"name": "SERVICE_URL_AGENT2", "value": "http://agent2:8001", "description": "URL for agent2"},
            ],
            ports=[{"port": 8000, "protocol": "http"}],
            dependencies=[{"name": "agent2", "required": True}],
        )

        self.agent2_metadata = DeploymentMetadata(
            version="1.0",
            component={"name": "agent2", "type": "agent", "description": "Agent 2"},
            docker={"build": {"context": "./agent2"}},
            environment=[
                {"name": "AGENT_NAME", "value": "agent2"},
                {"name": "SERVICE_URL_AGENT1", "value": "http://agent1:8000", "description": "URL for agent1"},
            ],
            ports=[{"port": 8001, "protocol": "http"}],
        )

        self.components = [self.agent1_metadata, self.agent2_metadata]

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_generate_orchestrated_compose(self):
        """Test generating an orchestrated Docker Compose file."""
        orchestrator = ComposeOrchestrator()
        compose_config = orchestrator.generate_compose(self.components)

        # Check the Docker Compose structure
        assert "version" in compose_config
        assert "services" in compose_config
        assert len(compose_config["services"]) == 2

        # Check both services are included
        assert "agent1" in compose_config["services"]
        assert "agent2" in compose_config["services"]

        # Check service dependencies
        assert "depends_on" in compose_config["services"]["agent1"]
        assert "agent2" in compose_config["services"]["agent1"]["depends_on"]

        # Check environment variables in agent1
        agent1_env = compose_config["services"]["agent1"]["environment"]
        assert any(
            "SERVICE_URL_AGENT2=http://agent2:8001" in env or env == "SERVICE_URL_AGENT2=http://agent2:8001"
            for env in agent1_env
        )

        # Check environment variables in agent2
        agent2_env = compose_config["services"]["agent2"]["environment"]
        assert any(
            "SERVICE_URL_AGENT1=http://agent1:8000" in env or env == "SERVICE_URL_AGENT1=http://agent1:8000"
            for env in agent2_env
        )

    def test_save_orchestrated_compose(self):
        """Test saving an orchestrated Docker Compose file."""
        orchestrator = ComposeOrchestrator()
        output_path = self.root_dir / "docker-compose.yml"

        saved_path = orchestrator.save_compose(self.components, output_path)

        # Check file was created
        assert saved_path.exists()

        # Load and check content
        with open(saved_path, "r") as f:
            compose_data = yaml.safe_load(f)

        assert "services" in compose_data
        assert "agent1" in compose_data["services"]
        assert "agent2" in compose_data["services"]
