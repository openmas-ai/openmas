"""Deploy commands for SimpleMas projects."""

import sys
from pathlib import Path
from typing import List

import click
import yaml

from simple_mas.deployment.discovery import ComponentDiscovery
from simple_mas.deployment.generators import DockerComposeGenerator, KubernetesGenerator
from simple_mas.deployment.metadata import DeploymentMetadata
from simple_mas.deployment.orchestration import ComposeOrchestrator, OrchestrationManifest


@click.group(name="deploy")
def deploy_cmd() -> None:
    """Deployment commands for SimpleMas projects."""
    pass


@deploy_cmd.command(name="validate")
@click.option("--input", "-i", default="simplemas.deploy.yaml", help="Path to the input metadata file")
def validate_metadata(input: str) -> None:
    """Validate a SimpleMas deployment metadata file."""
    try:
        metadata_path = Path(input)
        metadata = DeploymentMetadata.from_file(metadata_path)

        click.echo(f"✅ Metadata file '{metadata_path}' is valid")
        click.echo(f"Component: {metadata.component.name} ({metadata.component.type})")

        # Count elements in each section
        click.echo(f"Environment variables: {len(metadata.environment)}")
        click.echo(f"Ports: {len(metadata.ports)}")
        click.echo(f"Volumes: {len(metadata.volumes)}")
        click.echo(f"Dependencies: {len(metadata.dependencies)}")
    except Exception as e:
        click.echo(f"❌ Error validating metadata: {e}", err=True)
        sys.exit(1)


@deploy_cmd.command(name="compose")
@click.option("--input", "-i", default="simplemas.deploy.yaml", help="Path to the input metadata file")
@click.option("--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file")
def generate_compose(input: str, output: str) -> None:
    """Generate Docker Compose configuration."""
    try:
        metadata_path = Path(input)
        output_path = Path(output)

        metadata = DeploymentMetadata.from_file(metadata_path)
        generator = DockerComposeGenerator()

        output_file = generator.save(metadata, output_path)

        click.echo(f"✅ Generated Docker Compose configuration: {output_file}")
    except Exception as e:
        click.echo(f"❌ Error generating Docker Compose configuration: {e}", err=True)
        sys.exit(1)


@deploy_cmd.command(name="k8s")
@click.option("--input", "-i", default="simplemas.deploy.yaml", help="Path to the input metadata file")
@click.option("--output", "-o", default="kubernetes", help="Directory to save the Kubernetes manifests")
def generate_kubernetes(input: str, output: str) -> None:
    """Generate Kubernetes manifests."""
    try:
        metadata_path = Path(input)
        output_dir = Path(output)

        metadata = DeploymentMetadata.from_file(metadata_path)
        generator = KubernetesGenerator()

        output_files = generator.save(metadata, output_dir)

        click.echo(f"✅ Generated {len(output_files)} Kubernetes manifests in '{output_dir}':")
        for file_path in output_files:
            click.echo(f"  - {file_path.name}")
    except Exception as e:
        click.echo(f"❌ Error generating Kubernetes manifests: {e}", err=True)
        sys.exit(1)


@deploy_cmd.command(name="discover")
@click.option("--directory", "-d", default=".", help="Directory to search for components")
@click.option("--pattern", "-p", default="**/simplemas.deploy.yaml", help="Glob pattern to match metadata files")
def discover_components(directory: str, pattern: str) -> None:
    """Discover SimpleMas components."""
    try:
        directory_path = Path(directory)
        discoverer = ComponentDiscovery()
        components = discoverer.discover_components(directory_path, pattern)

        click.echo(f"✅ Discovered {len(components)} components in '{directory_path}':")
        for metadata in components:
            click.echo(f"  - {metadata.component.name} ({metadata.component.type})")
            for dep in metadata.dependencies:
                required = "required" if dep.required else "optional"
                click.echo(f"    - Depends on: {dep.name} ({required})")
    except Exception as e:
        click.echo(f"❌ Error discovering components: {e}", err=True)
        sys.exit(1)


@deploy_cmd.command(name="orchestrate")
@click.option("--directory", "-d", default=".", help="Directory to search for components")
@click.option("--pattern", "-p", default="**/simplemas.deploy.yaml", help="Glob pattern to match metadata files")
@click.option("--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file")
@click.option("--validate", "-v", is_flag=True, help="Validate component dependencies")
def orchestrate_components(directory: str, pattern: str, output: str, validate: bool) -> None:
    """Orchestrate multiple SimpleMas components."""
    try:
        directory_path = Path(directory)
        pattern_str = pattern
        output_path = Path(output)

        # Discover components
        discoverer = ComponentDiscovery()

        if validate:
            components = discoverer.discover_and_validate(directory_path, pattern_str)
        else:
            components = discoverer.discover_components(directory_path, pattern_str)

        if not components:
            click.echo(f"❌ No components found in '{directory_path}' with pattern '{pattern_str}'", err=True)
            sys.exit(1)

        # Create the orchestrator and generate Docker Compose
        orchestrator = ComposeOrchestrator()
        saved_path = orchestrator.save_compose(components, output_path)

        click.echo(f"✅ Orchestrated Docker Compose configuration for {len(components)} components:")
        for metadata in components:
            click.echo(f"  - {metadata.component.name}")

        click.echo(f"✅ Generated Docker Compose configuration: {saved_path}")
    except Exception as e:
        click.echo(f"❌ Error orchestrating components: {e}", err=True)
        sys.exit(1)


@deploy_cmd.command(name="manifest")
@click.option("--manifest", "-m", default="simplemas.manifest.yaml", help="Path to the manifest file")
@click.option("--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file")
def process_manifest(manifest: str, output: str) -> None:
    """Orchestrate from a central manifest file."""
    try:
        manifest_path = Path(manifest)
        output_path = Path(output)

        # Load the manifest
        manifest_obj = OrchestrationManifest(manifest_path)

        # Process components from the manifest
        components = []
        for path in manifest_obj.get_component_paths():
            try:
                metadata = DeploymentMetadata.from_file(path)
                components.append(metadata)
            except Exception as e:
                click.echo(f"Warning: Failed to load component at {path}: {e}")

        if not components:
            click.echo(f"❌ No valid components found in manifest '{manifest_path}'", err=True)
            sys.exit(1)

        # Create the orchestrator and generate Docker Compose
        orchestrator = ComposeOrchestrator()
        saved_path = orchestrator.save_compose(components, output_path)

        click.echo("✅ Orchestrated Docker Compose configuration from manifest:")
        for metadata in components:
            click.echo(f"  - {metadata.component.name}")

        click.echo(f"✅ Generated Docker Compose configuration: {saved_path}")
    except Exception as e:
        click.echo(f"❌ Error processing manifest: {e}", err=True)
        sys.exit(1)


# Testing helper functions - these are not exposed in the CLI but used for testing
def _generate_compose_from_project_impl(project_file: str, output: str, strict: bool, use_project_names: bool) -> int:
    """Implementation of generate_compose_from_project that can be called directly in tests."""
    try:
        project_file_path = Path(project_file)
        output_path = Path(output)

        if not project_file_path.exists():
            click.echo(f"❌ Project file '{project_file_path}' not found", err=True)
            return 1

        # Load the project configuration
        with open(project_file_path, "r") as f:
            project_config = yaml.safe_load(f)

        if not isinstance(project_config, dict):
            click.echo(f"❌ Project file '{project_file_path}' has invalid format", err=True)
            return 1

        if "agents" not in project_config or not isinstance(project_config["agents"], dict):
            click.echo(f"❌ Project file '{project_file_path}' is missing 'agents' section", err=True)
            return 1

        # Get agent paths from the project configuration
        agent_paths = project_config["agents"]

        # Discover deployment metadata for each agent
        components = []
        project_root = project_file_path.parent

        # Keep track of renamed components (original_name -> new_name)
        renamed_components = {}

        for agent_name, relative_path in agent_paths.items():
            agent_path = project_root / relative_path
            metadata_path = agent_path / "simplemas.deploy.yaml"

            if not metadata_path.exists():
                if strict:
                    click.echo(f"❌ Deployment metadata not found for agent '{agent_name}' at {metadata_path}", err=True)
                    return 1
                else:
                    click.echo(f"⚠️ Skipping agent '{agent_name}': metadata file not found at {metadata_path}")
                    continue

            try:
                metadata = DeploymentMetadata.from_file(metadata_path)

                # Override component name if needed to ensure consistency with project config
                if metadata.component.name != agent_name and use_project_names:
                    # Print a warning about renaming
                    original_name = metadata.component.name
                    click.echo(
                        f"⚠️ Renaming component from '{original_name}' " f"to '{agent_name}' to match project config"
                    )
                    # Store the mapping for dependency resolution
                    renamed_components[metadata.component.name] = agent_name
                    metadata.component.name = agent_name

                components.append(metadata)
            except Exception as e:
                if strict:
                    click.echo(f"❌ Error parsing metadata for agent '{agent_name}': {e}", err=True)
                    return 1
                else:
                    click.echo(f"⚠️ Skipping agent '{agent_name}': {e}")

        if not components:
            click.echo("❌ No valid components found in the project", err=True)
            return 1

        # If we're using project names, update dependencies to use them
        if use_project_names and renamed_components:
            _update_dependencies(components, renamed_components)

        # Process service URLs from dependencies
        _configure_service_urls(components)

        # Generate Docker Compose configuration
        orchestrator = ComposeOrchestrator()
        saved_path = orchestrator.save_compose(components, output_path)

        click.echo(f"✅ Generated Docker Compose configuration for {len(components)} components:")
        for metadata in components:
            click.echo(f"  - {metadata.component.name}")

        click.echo(f"✅ Generated Docker Compose configuration: {saved_path}")
        return 0
    except Exception as e:
        click.echo(f"❌ Error generating Docker Compose from project: {e}", err=True)
        return 1


@deploy_cmd.command(name="generate-compose")
@click.option("--project-file", "-p", default="simplemas_project.yml", help="Path to the SimpleMas project file")
@click.option("--output", "-o", default="docker-compose.yml", help="Path to save the Docker Compose configuration file")
@click.option("--strict", "-s", is_flag=True, help="Fail if any agent is missing deployment metadata")
@click.option(
    "--use-project-names",
    "-n",
    is_flag=True,
    help="Use agent names from project file instead of names in metadata",
)
def generate_compose_from_project(project_file: str, output: str, strict: bool, use_project_names: bool) -> None:
    """Generate Docker Compose configuration from SimpleMas project."""
    result = _generate_compose_from_project_impl(project_file, output, strict, use_project_names)
    if result != 0:
        sys.exit(result)


def _update_dependencies(components: List[DeploymentMetadata], renamed_components: dict) -> None:
    """Update dependencies to use project names instead of metadata names."""
    for component in components:
        for dependency in component.dependencies:
            if dependency.name in renamed_components:
                dependency.name = renamed_components[dependency.name]


def _configure_service_urls(components: List[DeploymentMetadata]) -> None:
    """Configure SERVICE_URL_* environment variables based on dependencies."""
    from simple_mas.deployment.metadata import EnvironmentVar

    # Create a mapping of component name to its ports
    component_ports = {}
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
