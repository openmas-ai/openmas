"""Deploy OpenMAS components using Docker Compose.

This module provides CLI commands for deploying OpenMAS components.
"""

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Union

import typer  # type: ignore
import yaml

from openmas.deployment.generators import DockerComposeGenerator
from openmas.deployment.metadata import DeploymentMetadata, EnvironmentVar
from openmas.deployment.orchestration import ComposeOrchestrator

if TYPE_CHECKING:
    import typer.models  # type: ignore

# Set up the logger
logger = logging.getLogger("openmas.cli.deploy")

# Create a typer app for the deployment commands
app = typer.Typer(help="Deploy OpenMAS components")

# Create a command group for the click-based CLI integration
deploy_cmd = typer.Typer(help="Deploy OpenMAS components")


def discover_metadata(directory: Union[str, Path]) -> DeploymentMetadata:
    """Discover deployment metadata from a directory.

    Args:
        directory: The directory containing the component

    Returns:
        The deployment metadata
    """
    directory_path = Path(directory)
    metadata_file = directory_path / "openmas.deploy.yaml"

    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found at {metadata_file}")

    return DeploymentMetadata.from_file(metadata_file)


@app.command("inspect")
def inspect_deployment(
    directory: str = typer.Argument(..., help="Directory containing the component to inspect"),
    wide: bool = typer.Option(False, "--wide", "-w", help="Show wide output"),
) -> None:
    """Inspect deployment metadata for a OpenMAS component.

    Args:
        directory: The directory containing the component
        wide: Show wide output
    """
    try:
        metadata = discover_metadata(directory)
        typer.echo(f"Component: {metadata.component.name}")
        typer.echo(f"  Type: {metadata.component.type}")
        typer.echo(f"  Version: {metadata.version}")
        typer.echo(f"  Description: {metadata.component.description}")

        if metadata.environment:
            typer.echo("\nEnvironment Variables:")
            for env in metadata.environment:
                if wide:
                    typer.echo(
                        f"  {env.name}={env.value} " f"{'(secret)' if env.secret else ''} " f"{env.description or ''}"
                    )
                else:
                    typer.echo(f"  {env.name}={env.value}")

        if metadata.ports:
            typer.echo("\nPorts:")
            for port in metadata.ports:
                typer.echo(f"  {port.port}/{'TCP' if port.protocol == 'tcp' else 'UDP'} " f"(published: auto) ")

        if metadata.volumes:
            typer.echo("\nVolumes:")
            for volume in metadata.volumes:
                typer.echo(f"  {volume.name}: {volume.path}")

        if metadata.dependencies:
            typer.echo("\nDependencies:")
            for dep in metadata.dependencies:
                typer.echo(f"  {dep.name} {'(required)' if dep.required else '(optional)'}")

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error inspecting deployment metadata: {e}", err=True)
        sys.exit(1)


@app.command("generate-compose")
def generate_compose(
    directory: str = typer.Argument(..., help="Directory containing the component to deploy"),
    output: str = typer.Option("docker-compose.yaml", "--output", "-o", help="Output file"),
) -> None:
    """Generate a Docker Compose file for deploying a OpenMAS component.

    Args:
        directory: Directory containing the component to deploy
        output: Output file path
    """
    try:
        metadata = discover_metadata(directory)
        generator = DockerComposeGenerator()

        compose_config = generator.generate(metadata)
        with open(output, "w") as f:
            yaml.safe_dump(compose_config, f, sort_keys=False)

        typer.echo(f"Docker Compose configuration saved to {output}")

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error generating Docker Compose file: {e}", err=True)
        sys.exit(1)


def process_manifest(
    manifest_path: str,
    output: str = "docker-compose.yaml",
) -> int:
    """Process a manifest file and generate a Docker Compose configuration.

    Args:
        manifest_path: Path to the manifest file
        output: Output file path

    Returns:
        0 for success, non-zero for failure
    """
    try:
        from openmas.deployment.orchestration import OrchestrationManifest

        # Load and validate the manifest
        manifest = OrchestrationManifest(manifest_path)

        # Get the components
        component_paths = manifest.get_component_paths()
        if not component_paths:
            typer.echo("Error: No components found in manifest", err=True)
            return 1

        # Discover metadata
        components: List[DeploymentMetadata] = []
        for path in component_paths:
            metadata_path = path / "openmas.deploy.yaml"
            if not metadata_path.exists():
                typer.echo(f"Warning: Metadata file not found at {metadata_path}", err=True)
                continue

            try:
                metadata = DeploymentMetadata.from_file(metadata_path)
                components.append(metadata)
            except Exception as e:
                typer.echo(f"Error loading metadata from {metadata_path}: {e}", err=True)
                return 1

        if not components:
            typer.echo("Error: No valid components found in manifest", err=True)
            return 1

        # Generate the orchestrated Docker Compose file
        orchestrator = ComposeOrchestrator()
        orchestrator.save_compose(components, output)

        typer.echo(f"Docker Compose configuration saved to {output}")
        return 0

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        return 1
    except Exception as e:
        typer.echo(f"Error processing manifest: {e}", err=True)
        return 1


@app.command("process-manifest")
def process_manifest_command(
    manifest_path: str = typer.Argument(..., help="Path to the manifest file"),
    output: str = typer.Option("docker-compose.yaml", "--output", "-o", help="Output file"),
) -> None:
    """Process a manifest file and generate a Docker Compose configuration.

    Args:
        manifest_path: Path to the manifest file
        output: Output file path
    """
    exit_code = process_manifest(manifest_path, output)
    if exit_code != 0:
        sys.exit(exit_code)


def _generate_compose_from_project_impl(
    project_file: str,
    output: str,
    strict: bool,
    use_project_names: bool,
) -> int:
    """Implement the functionality to generate a Docker Compose configuration from a OpenMAS project file.

    Args:
        project_file: Path to the project file
        output: Output file path
        strict: Fail if any agent doesn't have metadata
        use_project_names: Use agent names from project file instead of metadata

    Returns:
        0 for success, non-zero for failure
    """
    try:
        # Check if the project file exists
        project_path = Path(project_file)
        if not project_path.exists():
            logger.error(f"Project file not found: {project_file}")
            return 1

        # Create the orchestrator
        orchestrator = ComposeOrchestrator()

        try:
            # Process the project file to get metadata
            components, warnings, renamed_components = orchestrator.process_project_file(
                project_path, strict, use_project_names
            )

            # Configure service URLs (this is important for the tests to pass)
            components = _configure_service_urls(components)

            # Save the Docker Compose file
            orchestrator.save_compose(components, output)

            # Output any warnings
            for warning in warnings:
                logger.warning(warning)
                typer.echo(f"Warning: {warning}", err=True)

            typer.echo(f"Docker Compose configuration with {len(components)} components saved to {output}")
            return 0

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            typer.echo(f"Error: {e}", err=True)
            return 1
        except ValueError as e:
            logger.error(f"Invalid project configuration: {e}")
            typer.echo(f"Error: {e}", err=True)
            return 1

    except Exception as e:
        logger.error(f"Error generating Docker Compose file: {e}")
        typer.echo(f"Error generating Docker Compose file: {e}", err=True)
        return 1


@app.command("generate-compose-from-project")
def generate_compose_from_project(
    project_file: str = typer.Argument(..., help="Path to the project file"),
    output: str = typer.Option("docker-compose.yaml", "--output", "-o", help="Output file"),
    strict: bool = typer.Option(False, "--strict", help="Fail if any agent doesn't have metadata"),
    use_project_names: bool = typer.Option(
        True,
        "--use-project-names/--use-metadata-names",
        help="Use agent names from project file instead of metadata",
    ),
) -> None:
    """Generate a Docker Compose configuration from a OpenMAS project file.

    Args:
        project_file: Path to the project file
        output: Output file path
        strict: Fail if any agent doesn't have metadata
        use_project_names: Use agent names from project file instead of metadata
    """
    # Call the implementation function and handle the exit code
    exit_code = _generate_compose_from_project_impl(
        project_file=project_file, output=output, strict=strict, use_project_names=use_project_names
    )

    if exit_code != 0:
        sys.exit(exit_code)


def _configure_service_urls(components: List[DeploymentMetadata]) -> List[DeploymentMetadata]:
    """Configure SERVICE_URL_* environment variables based on dependencies.

    This function adds environment variables that follow the SERVICE_URL_<COMPONENT_NAME>
    convention based on dependencies declared in the component metadata.

    Args:
        components: List of component metadata to process

    Returns:
        The list of components with updated environment variables
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

    return components


def _generate_pip_dockerfile(
    python_version: str,
    app_entrypoint: str,
    requirements_file: str,
    port: int = 8000,
) -> str:
    """Generate a Dockerfile using pip for dependencies.

    Args:
        python_version: Python version to use
        app_entrypoint: Entry point script for the application
        requirements_file: Path to requirements.txt file
        port: Port to expose in the container

    Returns:
        Generated Dockerfile content
    """
    return f"""FROM python:{python_version}-slim

WORKDIR /app

# Copy requirements file and install dependencies
COPY {requirements_file} .
RUN pip install --no-cache-dir -r {requirements_file}

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    AGENT_PORT={port}

# Expose port
EXPOSE {port}

# Run the application
CMD ["python", "{app_entrypoint}"]
"""


def _generate_poetry_dockerfile(
    python_version: str,
    app_entrypoint: str,
    port: int = 8000,
) -> str:
    """Generate a Dockerfile for a Poetry-based project.

    Args:
        python_version: Python version to use
        app_entrypoint: Entry point script
        port: Port to expose in the container

    Returns:
        Dockerfile content
    """
    dockerfile = f"""FROM python:{python_version}-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy pyproject.toml and lockfile
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-dev

# Copy application code
COPY . .

# Expose the port
EXPOSE {port}
ENV AGENT_PORT={port}

# Run the application
CMD ["poetry", "run", "python", "{app_entrypoint}"]
"""
    return dockerfile


def _generate_dockerfile_impl(
    python_version: str,
    app_entrypoint: str,
    requirements_file: str,
    use_poetry: bool,
    port: int,
    output: str,
) -> int:
    """Implementation of the generate-dockerfile command.

    Args:
        python_version: Python version to use
        app_entrypoint: Entry point script
        requirements_file: Path to requirements.txt file
        use_poetry: Use Poetry for dependency management
        port: Port to expose in the container
        output: Output file path

    Returns:
        0 for success, non-zero for failure
    """
    try:
        # Check if the output file exists
        output_path = Path(output)
        if output_path.exists():
            # If the file exists, ask for confirmation before overwriting
            confirm = typer.confirm(f"File {output} already exists. Overwrite?", default=False)
            if not confirm:
                typer.echo("Aborted.")
                return 1

        # Generate the Dockerfile
        if use_poetry:
            dockerfile = _generate_poetry_dockerfile(
                python_version=python_version,
                app_entrypoint=app_entrypoint,
                port=port,
            )
        else:
            dockerfile = _generate_pip_dockerfile(
                python_version=python_version,
                app_entrypoint=app_entrypoint,
                requirements_file=requirements_file,
                port=port,
            )

        # Write the Dockerfile
        with open(output_path, "w") as f:
            f.write(dockerfile)

        typer.echo(f"Dockerfile saved to {output}")
        return 0
    except Exception as e:
        typer.echo(f"Error generating Dockerfile: {e}", err=True)
        return 1


@app.command("generate-dockerfile")
def generate_dockerfile(
    python_version: str = typer.Option("3.10", "--python-version", help="Python version to use"),
    app_entrypoint: str = typer.Option("agent.py", "--app-entrypoint", help="Entry point script"),
    requirements_file: str = typer.Option(
        "requirements.txt", "--requirements-file", help="Path to requirements.txt file"
    ),
    use_poetry: bool = typer.Option(False, "--use-poetry", help="Use Poetry for dependency management"),
    port: int = typer.Option(8000, "--port", help="Port to expose in the container"),
    output: str = typer.Option("Dockerfile", "--output", "-o", help="Output file path"),
) -> None:
    """Generate a Dockerfile for a OpenMAS component.

    Args:
        python_version: Python version to use
        app_entrypoint: Entry point script
        requirements_file: Path to requirements.txt file
        use_poetry: Use Poetry for dependency management
        port: Port to expose in the container
        output: Output file path
    """
    exit_code = _generate_dockerfile_impl(python_version, app_entrypoint, requirements_file, use_poetry, port, output)
    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    app()
