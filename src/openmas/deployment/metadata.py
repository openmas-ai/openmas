"""Deployment metadata parser for OpenMAS components."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator


class ComponentSpec(BaseModel):
    """Component specification in the deployment metadata."""

    name: str = Field(..., description="Logical name of the component")
    type: str = Field(..., description="Component type (agent, service, etc.)")
    description: str = Field("", description="Description of what this component does")


class DockerBuildSpec(BaseModel):
    """Docker build specification in the deployment metadata."""

    context: str = Field(".", description="Docker build context relative to the metadata file")
    dockerfile: str = Field("Dockerfile", description="Path to Dockerfile relative to context")
    args: List[Dict[str, str]] = Field(default_factory=list, description="Build arguments")


class DockerSpec(BaseModel):
    """Docker specification in the deployment metadata."""

    build: Optional[DockerBuildSpec] = Field(None, description="Docker build configuration")
    image: Optional[str] = Field(None, description="Docker image to use instead of building")

    @field_validator("image", "build", mode="after")
    @classmethod
    def validate_image_or_build(cls, v: Any, info: Any) -> Any:
        """Validate that either image or build is specified."""
        values = info.data
        if "image" in values and values["image"] is not None and "build" in values and values["build"] is not None:
            raise ValueError("Cannot specify both 'image' and 'build'")
        return v


class EnvironmentVar(BaseModel):
    """Environment variable specification in the deployment metadata."""

    name: str = Field(..., description="Name of the environment variable")
    value: Optional[str] = Field(None, description="Value of the environment variable")
    secret: bool = Field(False, description="Whether this is a secret value")
    description: str = Field("", description="Description of the environment variable")


class PortSpec(BaseModel):
    """Port specification in the deployment metadata."""

    port: int = Field(..., description="Port number")
    protocol: str = Field("http", description="Protocol (http, tcp, udp, etc.)")
    description: str = Field("", description="Description of the port")


class VolumeSpec(BaseModel):
    """Volume specification in the deployment metadata."""

    name: str = Field(..., description="Name of the volume")
    path: str = Field(..., description="Path to mount the volume in the container")
    description: str = Field("", description="Description of the volume")


class DependencySpec(BaseModel):
    """Dependency specification in the deployment metadata."""

    name: str = Field(..., description="Name of the dependent component")
    required: bool = Field(True, description="Whether this dependency is required")
    description: str = Field("", description="Description of the dependency")


class ResourceSpec(BaseModel):
    """Resource requirements specification in the deployment metadata."""

    cpu: str = Field("0.1", description="CPU resource requirements")
    memory: str = Field("256Mi", description="Memory resource requirements")
    gpu: bool = Field(False, description="Whether GPU is required")


class HealthCheckSpec(BaseModel):
    """Health check specification in the deployment metadata."""

    path: str = Field("/health", description="Health check endpoint path")
    port: int = Field(..., description="Port to check")
    initial_delay_seconds: int = Field(10, description="Initial delay before starting checks")
    period_seconds: int = Field(30, description="Period between checks")


class DeploymentMetadata(BaseModel):
    """Deployment metadata for OpenMAS components."""

    version: str = Field(..., description="OpenMAS deployment metadata version")
    component: ComponentSpec = Field(..., description="Component specification")
    docker: DockerSpec = Field(..., description="Docker configuration")
    environment: List[EnvironmentVar] = Field(default_factory=list, description="Environment variables")
    ports: List[PortSpec] = Field(default_factory=list, description="Exposed ports")
    volumes: List[VolumeSpec] = Field(default_factory=list, description="Required volumes")
    dependencies: List[DependencySpec] = Field(default_factory=list, description="Component dependencies")
    resources: Optional[ResourceSpec] = Field(None, description="Resource requirements")
    health_check: Optional[HealthCheckSpec] = Field(None, description="Health check configuration")

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> "DeploymentMetadata":
        """Load metadata from a YAML file.

        Args:
            file_path: Path to the metadata file

        Returns:
            Parsed and validated metadata
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Metadata file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        # Validate and process the data
        metadata = cls(**data)

        # Process variable substitutions
        metadata._process_variables()

        return metadata

    def _process_variables(self) -> None:
        """Process variable substitutions in the metadata."""
        # Environment variables that reference component properties
        for env_var in self.environment:
            if env_var.value and "${component." in env_var.value:
                env_var.value = self._substitute_component_vars(env_var.value)

    def _substitute_component_vars(self, value: str) -> str:
        """Substitute component variables in a string.

        Args:
            value: String that may contain component variable references

        Returns:
            String with variables substituted
        """
        if not value:
            return value

        # Match ${component.property} pattern
        pattern = r"\${component\.([a-zA-Z0-9_]+)}"

        def replace_var(match: re.Match[str]) -> str:
            prop_name = match.group(1)
            if hasattr(self.component, prop_name):
                return str(getattr(self.component, prop_name))
            return match.group(0)  # Keep original if not found

        return re.sub(pattern, replace_var, value)

    def get_environment_value(self, name: str) -> Optional[str]:
        """Get the value of an environment variable by name.

        Args:
            name: Name of the environment variable

        Returns:
            Value of the environment variable, or None if not found
        """
        for env_var in self.environment:
            if env_var.name == name:
                return env_var.value
        return None
