"""Command-line interface for SimpleMas deployment tools."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from simple_mas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from simple_mas.deployment.metadata import DeploymentMetadata


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
