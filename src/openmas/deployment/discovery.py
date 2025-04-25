"""Component discovery for OpenMAS deployment tools."""

from pathlib import Path
from typing import List, Union

from openmas.deployment.metadata import DeploymentMetadata


class ComponentDiscovery:
    """Discover OpenMAS components in a directory structure."""

    def discover_components(
        self, directory: Union[str, Path], pattern: str = "**/openmas.deploy.yaml"
    ) -> List[DeploymentMetadata]:
        """Discover deployment metadata files in the given directory.

        Args:
            directory: Root directory to start discovery from
            pattern: Glob pattern to match deployment metadata files

        Returns:
            List of parsed DeploymentMetadata objects
        """
        root_dir = Path(directory).resolve()
        if not root_dir.exists() or not root_dir.is_dir():
            raise ValueError(f"Invalid directory: {root_dir}")

        # Find all metadata files matching the pattern
        metadata_files = list(root_dir.glob(pattern))

        # Parse each metadata file
        components: List[DeploymentMetadata] = []
        for metadata_file in metadata_files:
            try:
                metadata = DeploymentMetadata.from_file(metadata_file)
                components.append(metadata)
            except Exception as e:
                print(f"Warning: Failed to parse {metadata_file}: {e}")

        return components

    def discover_and_validate(
        self, directory: Union[str, Path], pattern: str = "**/openmas.deploy.yaml"
    ) -> List[DeploymentMetadata]:
        """Discover deployment metadata files and validate component references.

        This method discovers components and ensures that all dependencies
        reference valid component names.

        Args:
            directory: Root directory to start discovery from
            pattern: Glob pattern to match deployment metadata files

        Returns:
            List of validated DeploymentMetadata objects

        Raises:
            ValueError: If a component references a dependency that doesn't exist
        """
        # Discover components
        components = self.discover_components(directory, pattern)

        # Create a mapping of component names for validation
        component_names = {comp.component.name for comp in components}

        # Validate dependencies
        for component in components:
            for dependency in component.dependencies:
                if dependency.required and dependency.name not in component_names:
                    raise ValueError(
                        f"Component '{component.component.name}' has a required dependency "
                        f"'{dependency.name}' that doesn't exist in the discovered components."
                    )

        return components
