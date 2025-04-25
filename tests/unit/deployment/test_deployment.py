"""Tests for the deployment metadata parser and generator."""

import tempfile
import unittest
from pathlib import Path

import pytest
import yaml

from openmas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from openmas.deployment.metadata import DeploymentMetadata


class TestDeploymentMetadata(unittest.TestCase):
    """Test the deployment metadata parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_metadata = {
            "version": "1.0",
            "component": {"name": "test-agent", "type": "agent", "description": "Test agent"},
            "docker": {"build": {"context": ".", "dockerfile": "Dockerfile"}},
            "environment": [
                {"name": "AGENT_NAME", "value": "${component.name}"},
                {"name": "LOG_LEVEL", "value": "INFO"},
            ],
            "ports": [{"port": 8000, "protocol": "http", "description": "HTTP API"}],
        }

        # Create a temporary file with test metadata
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metadata_path = Path(self.temp_dir.name) / "openmas.deploy.yaml"

        with open(self.metadata_path, "w") as f:
            yaml.safe_dump(self.test_metadata, f)

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_load_metadata(self):
        """Test loading metadata from a file."""
        metadata = DeploymentMetadata.from_file(self.metadata_path)

        assert metadata.version == "1.0"
        assert metadata.component.name == "test-agent"
        assert metadata.component.type == "agent"

        # Test variable substitution
        assert metadata.get_environment_value("AGENT_NAME") == "test-agent"

    def test_validation(self):
        """Test metadata validation."""
        # Create invalid metadata (missing required fields)
        invalid_metadata = {
            "version": "1.0",
            # Missing component section
            "docker": {"build": {"context": "."}},
        }

        invalid_path = Path(self.temp_dir.name) / "invalid.yaml"
        with open(invalid_path, "w") as f:
            yaml.safe_dump(invalid_metadata, f)

        with pytest.raises(ValueError):
            DeploymentMetadata.from_file(invalid_path)


class TestDockerComposeGenerator(unittest.TestCase):
    """Test the Docker Compose generator."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_metadata = {
            "version": "1.0",
            "component": {"name": "test-agent", "type": "agent", "description": "Test agent"},
            "docker": {"build": {"context": ".", "dockerfile": "Dockerfile"}},
            "environment": [
                {"name": "AGENT_NAME", "value": "${component.name}"},
                {"name": "LOG_LEVEL", "value": "INFO"},
                {"name": "API_KEY", "secret": True, "description": "API key"},
            ],
            "ports": [{"port": 8000, "protocol": "http", "description": "HTTP API"}],
            "volumes": [{"name": "data", "path": "/app/data", "description": "Data volume"}],
            "dependencies": [{"name": "other-service", "required": True, "description": "Other service"}],
        }

        # Create a temporary file with test metadata
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metadata_path = Path(self.temp_dir.name) / "openmas.deploy.yaml"

        with open(self.metadata_path, "w") as f:
            yaml.safe_dump(self.test_metadata, f)

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_generate_docker_compose(self):
        """Test generating Docker Compose configuration."""
        metadata = DeploymentMetadata.from_file(self.metadata_path)
        generator = DockerComposeGenerator()

        compose_config = generator.generate(metadata)

        # Verify the generated configuration
        assert "services" in compose_config
        assert "test-agent" in compose_config["services"]

        service = compose_config["services"]["test-agent"]
        assert "build" in service
        assert service["build"]["context"] == "."

        # Check environment variables
        assert "environment" in service
        assert "AGENT_NAME=test-agent" in service["environment"]

        # Check ports
        assert "ports" in service
        assert "8000:8000" in service["ports"]

        # Check volumes
        assert "volumes" in service
        assert "./data:/app/data" in service["volumes"]

        # Check dependencies
        assert "depends_on" in service
        assert "other-service" in service["depends_on"]


class TestKubernetesGenerator(unittest.TestCase):
    """Test the Kubernetes manifest generator."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_metadata = {
            "version": "1.0",
            "component": {"name": "test-agent", "type": "agent", "description": "Test agent"},
            "docker": {
                "build": {"context": ".", "dockerfile": "Dockerfile"},
                "image": "test-agent:latest",  # For K8s we would use a pre-built image
            },
            "environment": [
                {"name": "AGENT_NAME", "value": "${component.name}"},
                {"name": "API_KEY", "secret": True, "description": "API key"},
            ],
            "ports": [{"port": 8000, "protocol": "http", "description": "HTTP API"}],
            "resources": {"cpu": "0.5", "memory": "512Mi"},
            "health_check": {"path": "/health", "port": 8000, "initial_delay_seconds": 10, "period_seconds": 30},
        }

        # Create a temporary file with test metadata
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metadata_path = Path(self.temp_dir.name) / "openmas.deploy.yaml"

        with open(self.metadata_path, "w") as f:
            yaml.safe_dump(self.test_metadata, f)

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_generate_kubernetes_manifests(self):
        """Test generating Kubernetes manifests."""
        metadata = DeploymentMetadata.from_file(self.metadata_path)
        generator = KubernetesGenerator()

        k8s_manifests = generator.generate(metadata)

        # There should be at least a deployment and service
        assert len(k8s_manifests) >= 2

        # Find the deployment
        deployment = next((m for m in k8s_manifests if m["kind"] == "Deployment"), None)
        assert deployment is not None

        # Check deployment properties
        assert deployment["metadata"]["name"] == "test-agent"

        container_spec = deployment["spec"]["template"]["spec"]["containers"][0]
        assert container_spec["image"] == "test-agent:latest"

        # Check environment variables
        env_vars = {env["name"]: env for env in container_spec["env"]}
        assert "AGENT_NAME" in env_vars
        assert env_vars["AGENT_NAME"]["value"] == "test-agent"

        # API_KEY should reference a secret
        assert "API_KEY" in env_vars
        assert "valueFrom" in env_vars["API_KEY"]
        assert "secretKeyRef" in env_vars["API_KEY"]["valueFrom"]

        # Check health check/readiness probe
        assert "readinessProbe" in container_spec
        assert container_spec["readinessProbe"]["httpGet"]["path"] == "/health"

        # Find the service
        service = next((m for m in k8s_manifests if m["kind"] == "Service"), None)
        assert service is not None
        assert service["metadata"]["name"] == "test-agent-service"
