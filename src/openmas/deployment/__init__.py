"""OpenMAS deployment module for automating deployment of multi-agent systems."""

from openmas.deployment.cli import main
from openmas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from openmas.deployment.metadata import DeploymentMetadata

__all__ = ["DeploymentMetadata", "DockerComposeGenerator", "KubernetesGenerator", "main"]
