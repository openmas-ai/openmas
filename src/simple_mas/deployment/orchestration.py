"""Orchestration tools for SimpleMas deployment."""

from pathlib import Path
from typing import Any, Dict, List, Union, cast

import yaml

from simple_mas.deployment.generators import DockerComposeGenerator
from simple_mas.deployment.metadata import DeploymentMetadata


class ComposeOrchestrator:
    """Orchestrate multiple SimpleMas components into a single Docker Compose configuration."""

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self.generator = DockerComposeGenerator()

    def generate_compose(self, components: List[DeploymentMetadata]) -> Dict[str, Any]:
        """Generate a Docker Compose configuration for multiple components.

        Args:
            components: List of component metadata

        Returns:
            Docker Compose configuration as a dictionary
        """
        # Initialize Docker Compose structure
        compose_config: Dict[str, Any] = {"version": "3", "services": {}}

        # Add each component as a service
        for component in components:
            service_config = self._generate_service_config(component)
            service_name = component.component.name
            compose_config["services"][service_name] = service_config

        # Add networking between components
        self._configure_networking(compose_config, components)

        # Add shared volumes if needed
        self._configure_shared_volumes(compose_config, components)

        return compose_config

    def _generate_service_config(self, metadata: DeploymentMetadata) -> Dict[str, Any]:
        """Generate service configuration for a component.

        This uses the DockerComposeGenerator for individual components.

        Args:
            metadata: Component metadata

        Returns:
            Service configuration for Docker Compose
        """
        # Use the existing generator to create a Docker Compose for this component
        compose_config = self.generator.generate(metadata)

        # Extract just the service configuration for this component
        service_name = metadata.component.name
        service_config = compose_config["services"][service_name]

        return cast(Dict[str, Any], service_config)

    def _configure_networking(self, compose_config: Dict[str, Any], components: List[DeploymentMetadata]) -> None:
        """Configure networking between components.

        This ensures service URLs are correctly set and dependencies are captured.

        Args:
            compose_config: Docker Compose configuration to modify
            components: List of component metadata
        """
        # Create a mapping from component name to ports
        component_ports: Dict[str, int] = {}
        for component in components:
            if component.ports:
                # Get the first port for now (we could get more sophisticated later)
                component_ports[component.component.name] = component.ports[0].port

        # Configure dependencies in the compose file
        for component in components:
            service_name = component.component.name
            service_config = compose_config["services"][service_name]

            # Set up dependencies in depends_on
            if component.dependencies:
                if "depends_on" not in service_config:
                    service_config["depends_on"] = []

                for dependency in component.dependencies:
                    if dependency.required:
                        # Add to depends_on if not already there
                        depends_on = cast(List[str], service_config["depends_on"])
                        if dependency.name not in depends_on:
                            depends_on.append(dependency.name)

    def _configure_shared_volumes(self, compose_config: Dict[str, Any], components: List[DeploymentMetadata]) -> None:
        """Configure shared volumes between components.

        Args:
            compose_config: Docker Compose configuration to modify
            components: List of component metadata
        """
        # For now, we just create a top-level volumes section
        # if any components define volumes
        has_volumes = any(component.volumes for component in components)

        if has_volumes:
            # Add a top-level volumes configuration if it doesn't exist
            if "volumes" not in compose_config:
                compose_config["volumes"] = {}

            # For each component with volumes, create named volumes
            for component in components:
                for volume_spec in component.volumes:
                    volume_name = f"{component.component.name}-{volume_spec.name}"
                    compose_config["volumes"][volume_name] = {"driver": "local"}

                    # Update the service configuration to use the named volume
                    service_name = component.component.name
                    service_config = compose_config["services"][service_name]

                    if "volumes" not in service_config:
                        service_config["volumes"] = []

                    # Remove any existing volume definition for this path
                    volumes_list = cast(List[str], service_config["volumes"])
                    service_config["volumes"] = [v for v in volumes_list if not v.endswith(volume_spec.path)]

                    # Add the named volume
                    volumes_list = cast(List[str], service_config["volumes"])
                    volumes_list.append(f"{volume_name}:{volume_spec.path}")

    def save_compose(self, components: List[DeploymentMetadata], output_path: Union[str, Path]) -> Path:
        """Generate and save a Docker Compose file for multiple components.

        Args:
            components: List of component metadata
            output_path: Path to save the Docker Compose file

        Returns:
            Path to the saved file
        """
        compose_config = self.generate_compose(components)

        path = Path(output_path)
        with open(path, "w") as f:
            yaml.safe_dump(compose_config, f, sort_keys=False)

        return path


class OrchestrationManifest:
    """Central manifest for coordinating SimpleMas component deployment.

    This class handles parsing and processing a central manifest file that
    describes how multiple components should be orchestrated together.
    """

    def __init__(self, manifest_path: Union[str, Path]) -> None:
        """Initialize the manifest from a file.

        Args:
            manifest_path: Path to the manifest file
        """
        self.path = Path(manifest_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Manifest file not found: {self.path}")

        # Load the manifest
        with open(self.path, "r") as f:
            self.manifest: Dict[str, Any] = yaml.safe_load(f)

        # Validate basic structure
        if not isinstance(self.manifest, dict):
            raise ValueError("Manifest must be a dictionary")

        if "components" not in self.manifest:
            raise ValueError("Manifest must have a 'components' section")

    def get_components(self) -> List[Dict[str, Any]]:
        """Get the component definitions from the manifest.

        Returns:
            List of component definitions
        """
        components_list = self.manifest.get("components", [])
        return cast(List[Dict[str, Any]], components_list)

    def get_component_paths(self) -> List[Path]:
        """Get the paths to component metadata files.

        Returns:
            List of paths to component metadata files
        """
        base_dir = self.path.parent

        # Extract paths from the manifest
        paths: List[Path] = []
        for component in self.get_components():
            if "path" in component:
                component_path = base_dir / component["path"]
                paths.append(component_path)

        return paths
