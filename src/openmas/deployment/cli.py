"""Command-line interface for OpenMAS deployment tools."""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from openmas.deployment.discovery import ComponentDiscovery
from openmas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from openmas.deployment.metadata import DeploymentMetadata, EnvironmentVar
from openmas.deployment.orchestration import ComposeOrchestrator, OrchestrationManifest


def validate_command(args: argparse.Namespace) -> int:
    """Run the validate command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        metadata_path = Path(args.input)
        metadata = DeploymentMetadata.from_file(metadata_path)

        print(f"✅ Metadata file '{metadata_path}' is valid")
        print(f"Component: {metadata.component.name} ({metadata.component.type})")

        # Count elements in each section
        print(f"Environment variables: {len(metadata.environment)}")
        print(f"Ports: {len(metadata.ports)}")
        print(f"Volumes: {len(metadata.volumes)}")
        print(f"Dependencies: {len(metadata.dependencies)}")

        return 0
    except Exception as e:
        print(f"❌ Error validating metadata: {e}", file=sys.stderr)
        return 1


def compose_command(args: argparse.Namespace) -> int:
    """Run the Docker Compose generation command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        metadata_path = Path(args.input)
        output_path = Path(args.output)

        metadata = DeploymentMetadata.from_file(metadata_path)
        generator = DockerComposeGenerator()

        output_file = generator.save(metadata, output_path)

        print(f"✅ Generated Docker Compose configuration: {output_file}")
        return 0
    except Exception as e:
        print(f"❌ Error generating Docker Compose configuration: {e}", file=sys.stderr)
        return 1


def kubernetes_command(args: argparse.Namespace) -> int:
    """Run the Kubernetes manifests generation command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        metadata_path = Path(args.input)
        output_dir = Path(args.output)

        metadata = DeploymentMetadata.from_file(metadata_path)
        generator = KubernetesGenerator()

        output_files = generator.save(metadata, output_dir)

        print(f"✅ Generated {len(output_files)} Kubernetes manifests in '{output_dir}':")
        for file_path in output_files:
            print(f"  - {file_path.name}")

        return 0
    except Exception as e:
        print(f"❌ Error generating Kubernetes manifests: {e}", file=sys.stderr)
        return 1


def discover_command(args: argparse.Namespace) -> int:
    """Run the component discovery command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        directory = Path(args.directory)
        pattern = args.pattern

        discoverer = ComponentDiscovery()
        components = discoverer.discover_components(directory, pattern)

        print(f"✅ Discovered {len(components)} components in '{directory}':")
        for metadata in components:
            print(f"  - {metadata.component.name} ({metadata.component.type})")
            for dep in metadata.dependencies:
                required = "required" if dep.required else "optional"
                print(f"    - Depends on: {dep.name} ({required})")

        return 0
    except Exception as e:
        print(f"❌ Error discovering components: {e}", file=sys.stderr)
        return 1


def orchestrate_command(args: argparse.Namespace) -> int:
    """Run the orchestration command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        directory = Path(args.directory)
        pattern = args.pattern
        output_path = Path(args.output)

        # Discover components
        discoverer = ComponentDiscovery()

        if args.validate:
            components = discoverer.discover_and_validate(directory, pattern)
        else:
            components = discoverer.discover_components(directory, pattern)

        if not components:
            print(f"❌ No components found in '{directory}' with pattern '{pattern}'")
            return 1

        # Create the orchestrator and generate Docker Compose
        orchestrator = ComposeOrchestrator()
        saved_path = orchestrator.save_compose(components, output_path)

        print(f"✅ Orchestrated Docker Compose configuration for {len(components)} components:")
        for metadata in components:
            print(f"  - {metadata.component.name}")

        print(f"✅ Generated Docker Compose configuration: {saved_path}")
        return 0
    except Exception as e:
        print(f"❌ Error orchestrating components: {e}", file=sys.stderr)
        return 1


def manifest_command(args: argparse.Namespace) -> int:
    """Run the manifest orchestration command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        manifest_path = Path(args.manifest)
        output_path = Path(args.output)

        # Load the manifest
        manifest = OrchestrationManifest(manifest_path)

        # Process components from the manifest
        components = []
        for path in manifest.get_component_paths():
            try:
                metadata = DeploymentMetadata.from_file(path)
                components.append(metadata)
            except Exception as e:
                print(f"Warning: Failed to load component at {path}: {e}")

        if not components:
            print(f"❌ No valid components found in manifest '{manifest_path}'")
            return 1

        # Create the orchestrator and generate Docker Compose
        orchestrator = ComposeOrchestrator()
        saved_path = orchestrator.save_compose(components, output_path)

        print("✅ Orchestrated Docker Compose configuration from manifest:")
        for metadata in components:
            print(f"  - {metadata.component.name}")

        print(f"✅ Generated Docker Compose configuration: {saved_path}")
        return 0
    except Exception as e:
        print(f"❌ Error processing manifest: {e}", file=sys.stderr)
        return 1


def generate_compose_from_project_command(args: argparse.Namespace) -> int:
    """Run the generate-compose command that reads openmas_project.yml.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        project_file = Path(args.project_file)
        output_path = Path(args.output)

        if not project_file.exists():
            print(f"❌ Project file '{project_file}' not found", file=sys.stderr)
            return 1

        # Load the project configuration
        with open(project_file, "r") as f:
            project_config = yaml.safe_load(f)

        if not isinstance(project_config, dict):
            print(f"❌ Project file '{project_file}' has invalid format", file=sys.stderr)
            return 1

        if "agents" not in project_config or not isinstance(project_config["agents"], dict):
            print(f"❌ Project file '{project_file}' is missing 'agents' section", file=sys.stderr)
            return 1

        # Get agent paths from the project configuration
        agent_paths = project_config["agents"]

        # Discover deployment metadata for each agent
        components = []
        project_root = project_file.parent

        # Keep track of renamed components (original_name -> new_name)
        renamed_components = {}

        for agent_name, relative_path in agent_paths.items():
            agent_path = project_root / relative_path
            metadata_path = agent_path / "openmas.deploy.yaml"

            if not metadata_path.exists():
                if args.strict:
                    print(
                        f"❌ Deployment metadata not found for agent '{agent_name}' at {metadata_path}", file=sys.stderr
                    )
                    return 1
                else:
                    print(f"⚠️ Skipping agent '{agent_name}': metadata file not found at {metadata_path}")
                    continue

            try:
                metadata = DeploymentMetadata.from_file(metadata_path)

                # Override component name if needed to ensure consistency with project config
                if metadata.component.name != agent_name and args.use_project_names:
                    # Print a warning about renaming
                    original_name = metadata.component.name
                    print(f"⚠️ Renaming component from '{original_name}' " f"to '{agent_name}' to match project config")
                    # Store the mapping for dependency resolution
                    renamed_components[metadata.component.name] = agent_name
                    metadata.component.name = agent_name

                components.append(metadata)
            except Exception as e:
                if args.strict:
                    print(f"❌ Error parsing metadata for agent '{agent_name}': {e}", file=sys.stderr)
                    return 1
                else:
                    print(f"⚠️ Skipping agent '{agent_name}': {e}")

        if not components:
            print("❌ No valid components found in the project", file=sys.stderr)
            return 1

        # If we're using project names, update dependencies to use them
        if args.use_project_names and renamed_components:
            _update_dependencies(components, renamed_components)

        # Process service URLs from dependencies
        _configure_service_urls(components)

        # Generate Docker Compose configuration
        orchestrator = ComposeOrchestrator()
        saved_path = orchestrator.save_compose(components, output_path)

        print(f"✅ Generated Docker Compose configuration for {len(components)} components:")
        for metadata in components:
            print(f"  - {metadata.component.name}")

        print(f"✅ Generated Docker Compose configuration: {saved_path}")
        return 0
    except Exception as e:
        print(f"❌ Error generating Docker Compose from project: {e}", file=sys.stderr)
        return 1


def _update_dependencies(components: List[DeploymentMetadata], renamed_components: Dict[str, str]) -> None:
    """Update dependencies to use project names instead of metadata names.

    Args:
        components: List of component metadata to update
        renamed_components: Map of original names to project names
    """
    for component in components:
        for dependency in component.dependencies:
            if dependency.name in renamed_components:
                dependency.name = renamed_components[dependency.name]


def _configure_service_urls(components: List[DeploymentMetadata]) -> None:
    """Configure SERVICE_URL_* environment variables based on dependencies.

    This function adds environment variables that follow the SERVICE_URL_<COMPONENT_NAME>
    convention based on dependencies declared in the component metadata.

    Args:
        components: List of component metadata to process
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


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="OpenMAS deployment tools", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(title="commands", dest="command", help="Command to run")
    subparsers.required = True

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a OpenMAS deployment metadata file")
    validate_parser.add_argument("--input", "-i", default="openmas.deploy.yaml", help="Path to the input metadata file")
    validate_parser.set_defaults(func=validate_command)

    # Docker Compose command
    compose_parser = subparsers.add_parser("compose", help="Generate Docker Compose configuration")
    compose_parser.add_argument("--input", "-i", default="openmas.deploy.yaml", help="Path to the input metadata file")
    compose_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    compose_parser.set_defaults(func=compose_command)

    # Kubernetes command
    k8s_parser = subparsers.add_parser("k8s", help="Generate Kubernetes manifests")
    k8s_parser.add_argument("--input", "-i", default="openmas.deploy.yaml", help="Path to the input metadata file")
    k8s_parser.add_argument("--output", "-o", default="kubernetes", help="Directory to save the Kubernetes manifests")
    k8s_parser.set_defaults(func=kubernetes_command)

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover OpenMAS components")
    discover_parser.add_argument("--directory", "-d", default=".", help="Directory to search for components")
    discover_parser.add_argument(
        "--pattern", "-p", default="**/openmas.deploy.yaml", help="Glob pattern to match metadata files"
    )
    discover_parser.set_defaults(func=discover_command)

    # Orchestrate command
    orchestrate_parser = subparsers.add_parser("orchestrate", help="Orchestrate multiple OpenMAS components")
    orchestrate_parser.add_argument("--directory", "-d", default=".", help="Directory to search for components")
    orchestrate_parser.add_argument(
        "--pattern", "-p", default="**/openmas.deploy.yaml", help="Glob pattern to match metadata files"
    )
    orchestrate_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    orchestrate_parser.add_argument("--validate", "-v", action="store_true", help="Validate component dependencies")
    orchestrate_parser.set_defaults(func=orchestrate_command)

    # Manifest command
    manifest_parser = subparsers.add_parser("manifest", help="Orchestrate from a central manifest file")
    manifest_parser.add_argument("--manifest", "-m", default="openmas.manifest.yaml", help="Path to the manifest file")
    manifest_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    manifest_parser.set_defaults(func=manifest_command)

    # Generate Docker Compose from OpenMAS project
    generate_compose_parser = subparsers.add_parser(
        "generate-compose", help="Generate Docker Compose configuration from OpenMAS project"
    )
    generate_compose_parser.add_argument(
        "--project-file", "-p", default="openmas_project.yml", help="Path to the OpenMAS project file"
    )
    generate_compose_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    generate_compose_parser.add_argument(
        "--strict", "-s", action="store_true", help="Fail if any agent is missing deployment metadata"
    )
    generate_compose_parser.add_argument(
        "--use-project-names",
        "-n",
        action="store_true",
        help="Use agent names from project file instead of names in metadata",
    )
    generate_compose_parser.set_defaults(func=generate_compose_from_project_command)

    return parser.parse_args(args)


def main() -> int:
    """Run the OpenMAS deployment CLI.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
