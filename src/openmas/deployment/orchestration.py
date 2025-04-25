"""Orchestration tools for OpenMAS deployment."""

from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, cast

import yaml

from openmas.deployment.generators import DockerComposeGenerator
from openmas.deployment.metadata import DeploymentMetadata, EnvironmentVar


class ComposeOrchestrator:
    """Orchestrate multiple OpenMAS components into a single Docker Compose configuration."""

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

    def process_project_file(
        self, project_file_path: Path, strict: bool = False, use_project_names: bool = False
    ) -> Tuple[List[DeploymentMetadata], List[str], Dict[str, str]]:
        """Process a OpenMAS project file to extract component metadata.

        Args:
            project_file_path: Path to the project file
            strict: Whether to fail on missing metadata files
            use_project_names: Whether to use project names instead of metadata names

        Returns:
            Tuple of (components list, warning messages, renamed components)
        """
        if not project_file_path.exists():
            raise FileNotFoundError(f"Project file '{project_file_path}' not found")

        # Load the project configuration
        with open(project_file_path, "r") as f:
            project_config = yaml.safe_load(f)

        if not isinstance(project_config, dict):
            raise ValueError(f"Project file '{project_file_path}' has invalid format")

        if "agents" not in project_config or not isinstance(project_config["agents"], dict):
            raise ValueError(f"Project file '{project_file_path}' is missing 'agents' section")

        # Get agent paths from the project configuration
        agent_paths = project_config["agents"]

        # Discover deployment metadata for each agent
        components: List[DeploymentMetadata] = []
        warnings: List[str] = []
        project_root = project_file_path.parent

        # Keep track of renamed components (original_name -> new_name)
        renamed_components: Dict[str, str] = {}

        for agent_name, relative_path in agent_paths.items():
            agent_path = project_root / relative_path
            metadata_path = agent_path / "openmas.deploy.yaml"

            if not metadata_path.exists():
                if strict:
                    raise FileNotFoundError(
                        f"Deployment metadata not found for agent '{agent_name}' at {metadata_path}"
                    )
                else:
                    warnings.append(f"Skipping agent '{agent_name}': metadata file not found at {metadata_path}")
                    continue

            try:
                metadata = DeploymentMetadata.from_file(metadata_path)

                # Override component name if needed to ensure consistency with project config
                if metadata.component.name != agent_name and use_project_names:
                    # Store the original name
                    original_name = metadata.component.name
                    warnings.append(
                        f"Renaming component from '{original_name}' to '{agent_name}' to match project config"
                    )
                    # Store the mapping for dependency resolution
                    renamed_components[original_name] = agent_name
                    metadata.component.name = agent_name

                components.append(metadata)
            except Exception as e:
                if strict:
                    raise ValueError(f"Error parsing metadata for agent '{agent_name}': {e}")
                else:
                    warnings.append(f"Skipping agent '{agent_name}': {e}")

        if not components:
            raise ValueError("No valid components found in the project")

        return components, warnings, renamed_components

    def update_dependencies(self, components: List[DeploymentMetadata], renamed_components: Dict[str, str]) -> None:
        """Update dependencies to use project names instead of metadata names.

        Args:
            components: List of component metadata
            renamed_components: Map of original component names to new names
        """
        for component in components:
            for dependency in component.dependencies:
                if dependency.name in renamed_components:
                    dependency.name = renamed_components[dependency.name]

    def configure_service_urls(self, components: List[DeploymentMetadata]) -> None:
        """Configure SERVICE_URL_* environment variables based on dependencies.

        Args:
            components: List of component metadata
        """
        # Create a mapping of component name to its ports
        component_ports: Dict[str, int] = {}
        for component in components:
            if component.ports:
                # Get the first port for now (we could get more sophisticated later)
                component_ports[component.component.name] = component.ports[0].port

        # Add SERVICE_URL environment variables for each dependency
        for component in components:
            # Extract existing environment variable names
            existing_env_names = {env.name for env in component.environment}

            # Add SERVICE_URL variables for each dependency if not already defined
            for dependency in component.dependencies:
                dep_name = dependency.name
                service_url_var = f"SERVICE_URL_{dep_name.upper().replace('-', '_')}"

                # Skip if this environment variable is already defined
                if service_url_var in existing_env_names:
                    continue

                # Only add if the dependency component exists and has a port
                if dep_name in component_ports:
                    port = component_ports[dep_name]
                    url = f"http://{dep_name}:{port}"

                    # Add the environment variable
                    component.environment.append(
                        EnvironmentVar(
                            name=service_url_var,
                            value=url,
                            secret=False,
                            description=f"URL for {dep_name} service",
                        )
                    )

    def process_project_and_save_compose(
        self,
        project_file: Union[str, Path],
        output_path: Union[str, Path],
        strict: bool = False,
        use_project_names: bool = False,
    ) -> Tuple[Path, List[DeploymentMetadata], List[str]]:
        """Process a project file and generate a Docker Compose configuration.

        Args:
            project_file: Path to the OpenMAS project file
            output_path: Path to save the Docker Compose configuration file
            strict: Whether to fail on missing metadata files
            use_project_names: Whether to use project names instead of metadata names

        Returns:
            Tuple of (path to saved file, components list, warning messages)
        """
        project_file_path = Path(project_file)

        # Process the project file
        components, warnings, renamed_components = self.process_project_file(
            project_file_path, strict, use_project_names
        )

        # If we're using project names, update dependencies to use them
        if use_project_names and renamed_components:
            self.update_dependencies(components, renamed_components)

        # Configure service URLs from dependencies
        self.configure_service_urls(components)

        # Generate and save Docker Compose configuration
        saved_path = self.save_compose(components, output_path)

        return saved_path, components, warnings


class OrchestrationManifest:
    """Central manifest for coordinating OpenMAS component deployment.

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
