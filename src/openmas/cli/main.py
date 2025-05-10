"""Main CLI module for OpenMAS."""

import json
import os
import platform
import sys
import traceback
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional

import click
import typer
import yaml
from dotenv import load_dotenv  # type: ignore

from openmas import __version__
from openmas.cli.assets import assets_app
from openmas.cli.prompts import prompts
from openmas.cli.validate import validate_config
from openmas.logging import get_logger

# Import the CLI commands from their respective modules
# The deploy command will be added separately since it's using typer
# from openmas.cli.deploy import deploy_cmd

logger = get_logger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="OpenMAS")
def cli() -> None:
    """Provide CLI tools for managing OpenMAS projects."""
    pass


# Register the deploy command group - we'll define this separately later
# cli.add_command(deploy_cmd)

# Register the prompts command group
cli.add_command(prompts)

# Register the assets command group as an app that uses Typer
try:
    from typer.main import get_command

    cli.add_command(get_command(assets_app), name="assets")
except ImportError:
    logger.warning("Typer not installed, assets commands will not be available")
except Exception as e:
    logger.error(f"Failed to register assets commands: {e}")


@cli.command()
@click.argument("project_name", type=str)
@click.option("--template", "-t", type=str, default=None, help="Template to use for project initialization")
@click.option("--name", type=str, default=None, help="Project name when initializing in current directory")
def init(project_name: str, template: Optional[str], name: Optional[str]) -> None:
    """Initialize a new OpenMAS project with standard directory structure.

    PROJECT_NAME is the name of the project to create or "." for current directory.
    """
    # Handle special case for current directory
    if project_name == ".":
        if not name:
            click.echo("❌ When initializing in the current directory (.), you must provide a project name with --name")
            sys.exit(1)
        project_path = Path(".")
        display_name = name
    else:
        project_path = Path(project_name)
        display_name = project_name

    if project_path.exists() and project_path != Path("."):
        click.echo(f"❌ Project directory '{project_name}' already exists.")
        sys.exit(1)

    # Create main project directory if not using current directory
    if project_path != Path("."):
        try:
            project_path.mkdir(parents=True)
        except (PermissionError, OSError) as e:
            click.echo(f"❌ Error creating project directory: {str(e)}")
            sys.exit(1)

    # Create subdirectories
    subdirs = ["agents", "shared", "extensions", "config", "tests", "packages"]
    try:
        for subdir in subdirs:
            subdir_path = project_path / subdir
            subdir_path.mkdir(exist_ok=project_path == Path("."))

            # Create __init__.py files in Python package directories (exclude config and packages)
            if subdir not in ["config", "packages"]:
                init_file = subdir_path / "__init__.py"
                with open(init_file, "w") as f:
                    f.write(f'"""OpenMAS {subdir} package."""\n')
    except (PermissionError, OSError) as e:
        click.echo(f"❌ Error creating project structure: {str(e)}")
        sys.exit(1)

    # Create project files
    try:
        # Create README.md
        with open(project_path / "README.md", "w") as f:
            f.write(f"# {display_name}\n\nA OpenMAS project.\n")

        # Create requirements.txt
        with open(project_path / "requirements.txt", "w") as f:
            f.write("openmas>=0.1.0\n")

        # Create .gitignore if it doesn't exist
        gitignore_path = project_path / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w") as f:
                f.write("__pycache__/\n*.py[cod]\n*$py.class\n.env\n.venv\nenv/\nvenv/\nENV/\nenv.bak/\nvenv.bak/\n")
                f.write(".pytest_cache/\n.coverage\nhtmlcov/\n.tox/\n.mypy_cache/\n")
                f.write("# OpenMAS specific\npackages/\n")
    except (PermissionError, OSError) as e:
        click.echo(f"❌ Error creating project files: {str(e)}")
        sys.exit(1)

    # Create openmas_project.yml
    project_config: Dict[str, Any] = {
        "name": display_name,
        "version": "0.1.0",
        "agents": {},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "default_config": {"log_level": "INFO", "communicator_type": "http"},
        "dependencies": [],
    }

    # If template is specified, customize the project structure
    if template:
        try:
            if template.lower() == "mcp-server":
                # Setup an MCP server template
                agent_dir = project_path / "agents" / "mcp_server"
                agent_dir.mkdir(parents=True, exist_ok=project_path == Path("."))

                # Create __init__.py file in the agent directory
                with open(agent_dir / "__init__.py", "w") as f:
                    f.write('"""MCP Server agent package."""\n')

                # Create agent.py file
                with open(agent_dir / "agent.py", "w") as f:
                    f.write(
                        """'''MCP Server Agent.'''

import asyncio
from openmas.agent import BaseAgent

class McpServerAgent(BaseAgent):
    '''MCP Server agent implementation.'''

    async def setup(self) -> None:
        '''Set up the MCP server.'''
        # Setup your MCP server here
        pass

    async def run(self) -> None:
        '''Run the MCP server.'''
        # Run your MCP server here
        while True:
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        '''Shut down the MCP server.'''
        # Shutdown your MCP server here
        pass
"""
                    )

                # Create openmas.deploy.yaml file
                with open(agent_dir / "openmas.deploy.yaml", "w") as f:
                    f.write(
                        """version: "1.0"

component:
  name: "mcp-server"
  type: "service"
  description: "MCP server for model access"

docker:
  build:
    context: "."
    dockerfile: "Dockerfile"

environment:
  - name: "AGENT_NAME"
    value: "${component.name}"
  - name: "LOG_LEVEL"
    value: "INFO"
  - name: "COMMUNICATOR_TYPE"
    value: "http"
  - name: "MCP_API_KEY"
    secret: true
    description: "API key for MCP service"

ports:
  - port: 8000
    protocol: "http"
    description: "HTTP API for MCP access"

volumes:
  - name: "data"
    path: "/app/data"
    description: "Data storage"

dependencies: []
"""
                    )

                # Update project config with the agent
                project_config["agents"]["mcp_server"] = "agents/mcp_server"
        except (PermissionError, OSError) as e:
            click.echo(f"❌ Error creating template files: {str(e)}")
            sys.exit(1)
    else:
        # Create a basic sample agent when no template is specified
        try:
            # Setup a basic sample agent
            agent_dir = project_path / "agents" / "sample_agent"
            agent_dir.mkdir(parents=True, exist_ok=project_path == Path("."))

            # Create __init__.py file in the agent directory
            with open(agent_dir / "__init__.py", "w") as f:
                f.write('"""Sample agent package."""\n')

            # Create agent.py file
            with open(agent_dir / "agent.py", "w") as f:
                f.write(
                    """'''Sample Agent.'''

import asyncio
from openmas.agent import BaseAgent

class Agent(BaseAgent):
    '''Sample agent implementation.'''

    async def setup(self) -> None:
        '''Set up the agent.'''
        self.logger.info("Sample agent initializing...")

    async def run(self) -> None:
        '''Run the agent.'''
        self.logger.info("Sample agent running...")

        # Example periodic task
        for i in range(5):
            self.logger.info(f"Sample agent tick {i}...")
            await asyncio.sleep(1)

        self.logger.info("Sample agent completed.")

    async def shutdown(self) -> None:
        '''Clean up when the agent stops.'''
        self.logger.info("Sample agent shutting down...")
"""
                )

            # Update project config with the agent
            project_config["agents"]["sample_agent"] = "agents/sample_agent"
        except (PermissionError, OSError) as e:
            click.echo(f"❌ Error creating sample agent: {str(e)}")
            sys.exit(1)

    # Add dependencies schema comment
    dependencies_comment = """# Dependencies configuration (for external packages)
# Examples:
# dependencies:
#   # - package: <org_or_user>/<package_name>  # Example: From official repo (Not implemented yet)
#   #   version: <version_spec>
#   # - git: <git_url>                         # Example: From Git repo (Implemented)
#   #   revision: <branch_tag_or_commit>       # Optional
#   # - local: <relative_path_to_package>      # Example: From local path (Not implemented yet)
"""

    # Write the project configuration file with comments
    try:
        with open(project_path / "openmas_project.yml", "w") as f:
            yaml.dump(project_config, f, default_flow_style=False, sort_keys=False)
            f.write("\n" + dependencies_comment)
    except (PermissionError, OSError) as e:
        click.echo(f"❌ Error writing project configuration: {str(e)}")
        sys.exit(1)

    # Success message with styling
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        rich_console = Console()

        # Create a styled success message
        success_text = Text()
        success_text.append("✅ ", style="bold green")

        if project_path == Path("."):
            success_text.append(f"OpenMAS project '{display_name}' created successfully!\n\n", style="bold")
            success_text.append("Project structure initialized in current directory")
        else:
            success_text.append(f"OpenMAS project '{project_path}' created successfully!\n\n", style="bold")
            success_text.append(f"Project structure initialized in '{project_path}'")

        if template:
            success_text.append(f"\n\nTemplate: {template}", style="bold blue")

        # Add next steps
        next_steps = Text("\n\nNext steps:", style="bold yellow")
        if project_path != Path("."):
            next_steps.append(f"\n  cd {project_name}")
        next_steps.append("\n  poetry install openmas")
        next_steps.append("\n  # Start developing your agents!")

        success_text.append(next_steps)

        # Display the styled message in a panel
        rich_console.print(Panel(success_text, title="Project Creation Complete", border_style="green"))
    except ImportError:
        # Fallback to plain text if rich is not available
        if project_path == Path("."):
            click.echo(f"✅ Created OpenMAS project '{display_name}'")
            click.echo("Project structure initialized in current directory")
        else:
            click.echo(f"✅ Created OpenMAS project '{project_path}'")
            click.echo(f"Project structure initialized in '{project_path}'")

        if template:
            click.echo(f"Used template: {template}")

        click.echo("\nNext steps:")
        if project_path != Path("."):
            click.echo(f"  cd {project_name}")
        click.echo("  poetry install openmas")
        click.echo("  # Start developing your agents!")


@cli.command()
def validate() -> None:
    """Validate the OpenMAS project configuration."""
    exit_code = validate_config()
    if exit_code != 0:
        sys.exit(exit_code)


@cli.command(name="list")
@click.argument("resource_type", type=click.Choice(["agents"]))
def list_resources(resource_type: str) -> None:
    """List resources in the OpenMAS project.

    RESOURCE_TYPE is the type of resource to list (currently only 'agents' is supported).
    """
    config_path = Path("openmas_project.yml")

    if not config_path.exists():
        click.echo("❌ Project configuration file 'openmas_project.yml' not found")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if resource_type == "agents":
            agents = config.get("agents", {})
            if not agents:
                click.echo("No agents defined in the project")
                return

            click.echo(f"Agents in project '{config.get('name', 'undefined')}':")
            for agent_name, agent_path in agents.items():
                click.echo(f"  {agent_name}: {agent_path}")
    except Exception as e:
        click.echo(f"❌ Error listing resources: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Explicit path to the project directory containing openmas_project.yml",
)
@click.option(
    "--clean",
    is_flag=True,
    help="Clean the packages directory before installing dependencies",
)
def deps(project_dir: Optional[Path] = None, clean: bool = False) -> None:
    """Install external dependencies defined in openmas_project.yml.

    Currently supports Git repositories.
    """
    import shutil
    import subprocess

    from openmas.config import _find_project_root

    # Find project root
    project_root = _find_project_root(project_dir)
    if not project_root:
        if project_dir:
            click.echo(
                f"❌ Project configuration file 'openmas_project.yml' not found in specified directory: {project_dir}"
            )
        else:
            click.echo("❌ Project configuration file 'openmas_project.yml' not found in current or parent directories")
        sys.exit(1)

    # Load project configuration
    try:
        with open(project_root / "openmas_project.yml", "r") as f:
            project_config = yaml.safe_load(f)
    except Exception as e:
        click.echo(f"❌ Error loading project configuration: {e}")
        sys.exit(1)

    # Get dependencies from project configuration
    dependencies = project_config.get("dependencies", [])
    if not dependencies:
        click.echo("No dependencies defined in the project configuration")
        return

    # Create or clean the packages directory
    packages_dir = project_root / "packages"
    if clean and packages_dir.exists():
        click.echo("Cleaning packages directory...")
        shutil.rmtree(packages_dir)

    packages_dir.mkdir(exist_ok=True)

    # Process dependencies
    for dep in dependencies:
        # Handle git dependencies
        if "git" in dep:
            git_url = dep["git"]
            revision = dep.get("revision")

            # Extract repo name from URL
            repo_name = git_url.rstrip("/").split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]

            target_dir = packages_dir / repo_name

            click.echo(f"Installing git package '{repo_name}' from {git_url}...")

            # Clone the repository
            try:
                if target_dir.exists():
                    # If the directory exists, update the repository
                    click.echo("  Repository already exists, pulling latest changes...")
                    subprocess.run(
                        ["git", "pull", "origin"],
                        cwd=str(target_dir),
                        check=True,
                        capture_output=True,
                    )
                else:
                    # Otherwise, clone the repository
                    subprocess.run(
                        ["git", "clone", git_url, str(target_dir)],
                        check=True,
                        capture_output=True,
                    )

                # Checkout the specific revision if specified
                if revision:
                    click.echo(f"  Checking out revision: {revision}")
                    subprocess.run(
                        ["git", "checkout", revision],
                        cwd=str(target_dir),
                        check=True,
                        capture_output=True,
                    )

                click.echo(f"✅ Successfully installed '{repo_name}'")
            except subprocess.SubprocessError as e:
                click.echo(f"❌ Error installing git package '{repo_name}': {e}")
                continue

        # Handle package dependencies (not yet implemented)
        elif "package" in dep:
            click.echo(f"⚠️ Package dependencies not implemented yet: {dep['package']}")

        # Handle local dependencies (not yet implemented)
        elif "local" in dep:
            click.echo(f"⚠️ Local dependencies not implemented yet: {dep['local']}")

        # Handle unknown dependency types
        else:
            click.echo(f"⚠️ Unknown dependency type: {dep}")

    click.echo(f"Installed {len(dependencies)} dependencies")


@cli.command()
@click.argument("agent_name", type=str)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Explicit path to the project directory containing openmas_project.yml",
)
@click.option(
    "--env",
    type=str,
    help="Environment name to use for configuration (sets OPENMAS_ENV)",
)
def run(agent_name: str, project_dir: Optional[Path] = None, env: Optional[str] = None) -> None:
    """Run an agent from the OpenMAS project.

    AGENT_NAME is the name of the agent to run.
    """
    from openmas.cli.run import run_project

    try:
        run_project(agent_name, project_dir, env)
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("agent_name", type=str)
@click.option(
    "--output-file",
    type=str,
    default="Dockerfile",
    help="Name of the output Dockerfile",
)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Explicit path to the project directory containing openmas_project.yml",
)
@click.option(
    "--python-version",
    type=str,
    default="3.10",
    help="Python version to use",
)
@click.option(
    "--use-poetry",
    is_flag=True,
    help="Use Poetry for dependency management instead of pip requirements.txt",
)
def generate_dockerfile(
    agent_name: str,
    output_file: str,
    project_dir: Optional[Path] = None,
    python_version: str = "3.10",
    use_poetry: bool = False,
) -> None:
    """Generate a Dockerfile for an agent.

    AGENT_NAME is the name of the agent to generate a Dockerfile for.
    """
    from openmas.config import _find_project_root
    from openmas.deployment.generators import DockerfileGenerator

    # Find project root
    project_root = _find_project_root(project_dir)
    if not project_root:
        if project_dir:
            click.echo(
                f"❌ Project configuration file 'openmas_project.yml' not found in specified directory: {project_dir}"
            )
        else:
            click.echo("❌ Project configuration file 'openmas_project.yml' not found in current or parent directories")
        sys.exit(1)

    # Load project configuration
    try:
        with open(project_root / "openmas_project.yml", "r") as f:
            project_config = yaml.safe_load(f)
    except Exception as e:
        click.echo(f"❌ Error loading project configuration: {e}")
        sys.exit(1)

    # Find the agent in the project configuration
    agents = project_config.get("agents", {})
    if agent_name not in agents:
        click.echo(f"❌ Agent '{agent_name}' not found in project configuration")
        all_agents = list(agents.keys())
        if all_agents:
            click.echo(f"Available agents: {', '.join(all_agents)}")
        sys.exit(1)

    # Get agent path
    agent_path = agents[agent_name]

    # Ensure agent path exists
    agent_dir = project_root / agent_path
    if not agent_dir.exists():
        click.echo(f"❌ Agent directory for '{agent_name}' not found at '{agent_path}'")
        sys.exit(1)

    # Use the DockerfileGenerator
    generator = DockerfileGenerator()

    # Set entrypoint to use the openmas CLI to run the agent
    # The DockerfileGenerator will use this command in the CMD directive
    # It needs to be a shell command, not the argument to python
    app_entrypoint = f"-m openmas.cli run {agent_name}"

    # Determine requirements file path
    requirements_file = "requirements.txt"

    try:
        # Generate the Dockerfile
        output_path = Path(output_file)
        generator.save(
            output_path=output_path,
            python_version=python_version,
            app_entrypoint=app_entrypoint,
            requirements_file=requirements_file,
            use_poetry=use_poetry,
            port=8000,  # Default port, not crucial for agent
        )

        click.echo(f"✅ Generated Dockerfile for agent '{agent_name}' at '{output_path}'")
        click.echo("\nBuild the Docker image with:")
        click.echo(f"  docker build -t {project_config['name'].lower()}-{agent_name} -f {output_file} .")
        click.echo("\nRun the Docker container with:")
        click.echo(f"  docker run --name {agent_name} {project_config['name'].lower()}-{agent_name}")
    except Exception as e:
        click.echo(f"❌ Error generating Dockerfile: {e}")
        sys.exit(1)


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output information in JSON format")
def info(output_json: bool = False) -> None:
    """Show information about the OpenMAS installation.

    This command displays the OpenMAS version, Python version,
    and information about installed optional modules.
    """
    # Gather system information
    info_data: Dict[str, Any] = {
        "version": __version__,
        "python_version": f"{platform.python_version()} ({platform.python_implementation()})",
        "platform": platform.platform(),
        "modules": {
            # Indicate which modules are included in the base package
            "base": True,
            "http": True,
            # Check if optional modules are available using version detection
            "mcp": False,
            "grpc": False,
            "mqtt": False,
        },
    }

    # Try to safely determine if optional modules are available
    try:
        # Check for extras using importlib.metadata
        dist = metadata.distribution("openmas")
        if dist:
            # Check extras
            modules_dict = info_data["modules"]
            if isinstance(modules_dict, dict):
                # Check requires_dist attribute for extras
                requires_dist = getattr(dist, "requires_dist", []) or []
                requires_str = " ".join(requires_dist)

                if "mcp" in requires_str:
                    modules_dict["mcp"] = True
                if "grpc" in requires_str:
                    modules_dict["grpc"] = True
                if "mqtt" in requires_str:
                    modules_dict["mqtt"] = True
    except Exception:
        # If we can't determine extras, that's fine - just use defaults
        pass

    # Output in requested format
    if output_json:
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"OpenMAS version: {info_data['version']}")
        click.echo(f"Python version: {info_data['python_version']}")
        click.echo(f"Platform: {info_data['platform']}")
        click.echo("\nOptional modules:")

        modules_dict = info_data["modules"]
        if isinstance(modules_dict, dict):
            for module_name, is_installed in modules_dict.items():
                status = "✓" if is_installed else "✗"
                click.echo(f"  {module_name:10} {status}")

        click.echo("\nFor more information, visit: https://docs.openmas.ai/")


def main() -> int:
    """Main entry point for the OpenMAS CLI tool."""
    try:
        # Load .env file if it exists in the current working directory (project root)
        dotenv_path = Path(os.getcwd()) / ".env"
        if dotenv_path.exists() and dotenv_path.is_file():
            load_dotenv(dotenv_path=str(dotenv_path), override=True)
            logger.info(f"Loaded environment variables from: {dotenv_path}")
        else:
            # Check common alternative: .env in parent if CWD is a subdir
            alt_dotenv_path = Path(os.getcwd()).parent / ".env"
            if alt_dotenv_path.exists() and alt_dotenv_path.is_file():
                load_dotenv(dotenv_path=str(alt_dotenv_path), override=True)
                logger.info(f"Loaded environment variables from: {alt_dotenv_path}")
            else:
                logger.debug("No .env file found in current or parent directory.")

        cli()
        return 0
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
