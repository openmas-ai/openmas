"""SimpleMas deployment module for automating deployment of multi-agent systems."""

from simple_mas.deployment.cli import main
from simple_mas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from simple_mas.deployment.metadata import DeploymentMetadata

__all__ = ["DeploymentMetadata", "DockerComposeGenerator", "KubernetesGenerator", "main"]
