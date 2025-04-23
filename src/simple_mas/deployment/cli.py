"""Command-line interface for SimpleMas deployment tools."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from simple_mas.deployment.discovery import ComponentDiscovery
from simple_mas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from simple_mas.deployment.metadata import DeploymentMetadata
from simple_mas.deployment.orchestration import ComposeOrchestrator, OrchestrationManifest


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


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="SimpleMas deployment tools", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(title="commands", dest="command", help="Command to run")
    subparsers.required = True

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a SimpleMas deployment metadata file")
    validate_parser.add_argument(
        "--input", "-i", default="simplemas.deploy.yaml", help="Path to the input metadata file"
    )
    validate_parser.set_defaults(func=validate_command)

    # Docker Compose command
    compose_parser = subparsers.add_parser("compose", help="Generate Docker Compose configuration")
    compose_parser.add_argument(
        "--input", "-i", default="simplemas.deploy.yaml", help="Path to the input metadata file"
    )
    compose_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    compose_parser.set_defaults(func=compose_command)

    # Kubernetes command
    k8s_parser = subparsers.add_parser("k8s", help="Generate Kubernetes manifests")
    k8s_parser.add_argument("--input", "-i", default="simplemas.deploy.yaml", help="Path to the input metadata file")
    k8s_parser.add_argument("--output", "-o", default="kubernetes", help="Directory to save the Kubernetes manifests")
    k8s_parser.set_defaults(func=kubernetes_command)

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover SimpleMas components")
    discover_parser.add_argument("--directory", "-d", default=".", help="Directory to search for components")
    discover_parser.add_argument(
        "--pattern", "-p", default="**/simplemas.deploy.yaml", help="Glob pattern to match metadata files"
    )
    discover_parser.set_defaults(func=discover_command)

    # Orchestrate command
    orchestrate_parser = subparsers.add_parser("orchestrate", help="Orchestrate multiple SimpleMas components")
    orchestrate_parser.add_argument("--directory", "-d", default=".", help="Directory to search for components")
    orchestrate_parser.add_argument(
        "--pattern", "-p", default="**/simplemas.deploy.yaml", help="Glob pattern to match metadata files"
    )
    orchestrate_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    orchestrate_parser.add_argument("--validate", "-v", action="store_true", help="Validate component dependencies")
    orchestrate_parser.set_defaults(func=orchestrate_command)

    # Manifest command
    manifest_parser = subparsers.add_parser("manifest", help="Orchestrate from a central manifest file")
    manifest_parser.add_argument(
        "--manifest", "-m", default="simplemas.manifest.yaml", help="Path to the manifest file"
    )
    manifest_parser.add_argument(
        "--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file"
    )
    manifest_parser.set_defaults(func=manifest_command)

    return parser.parse_args(args)


def main() -> int:
    """Run the SimpleMas deployment CLI.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
