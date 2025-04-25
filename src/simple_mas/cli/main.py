"""Main CLI module for SimpleMAS."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
import yaml

# Import the CLI commands from their respective modules
# The deploy command will be added separately since it's using typer
# from simple_mas.cli.deploy import deploy_cmd
from simple_mas.logging import get_logger

logger = get_logger(__name__)


@click.group()
@click.version_option()
def cli() -> None:
    """Provide CLI tools for managing SimpleMAS projects."""
    pass


# Register the deploy command group - we'll define this separately later
# cli.add_command(deploy_cmd)


@cli.command()
@click.argument("project_name", type=str)
@click.option("--template", "-t", type=str, default=None, help="Template to use for project initialization")
@click.option("--name", type=str, default=None, help="Project name when initializing in current directory")
def init(project_name: str, template: Optional[str], name: Optional[str]) -> None:
    """Initialize a new SimpleMAS project with standard directory structure.

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
        project_path.mkdir(parents=True)

    # Create subdirectories
    subdirs = ["agents", "shared", "extensions", "config", "tests"]
    for subdir in subdirs:
        (project_path / subdir).mkdir(exist_ok=project_path == Path("."))

    # Create README.md
    with open(project_path / "README.md", "w") as f:
        f.write(f"# {display_name}\n\nA SimpleMAS project.\n")

    # Create requirements.txt
    with open(project_path / "requirements.txt", "w") as f:
        f.write("simple-mas>=0.1.0\n")

    # Create simplemas_project.yml
    project_config: Dict[str, Any] = {
        "name": display_name,
        "version": "0.1.0",
        "agents": {},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions"],
        "default_config": {"log_level": "INFO", "communicator_type": "http"},
    }

    # If template is specified, customize the project structure
    if template:
        if template.lower() == "mcp-server":
            # Setup an MCP server template
            agent_dir = project_path / "agents" / "mcp_server"
            agent_dir.mkdir(parents=True, exist_ok=project_path == Path("."))

            # Create agent.py file
            with open(agent_dir / "agent.py", "w") as f:
                f.write(
                    """'''MCP Server Agent.'''

import asyncio
from simple_mas.agent import BaseAgent

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

            # Create simplemas.deploy.yaml file
            with open(agent_dir / "simplemas.deploy.yaml", "w") as f:
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
            if "agents" not in project_config:
                project_config["agents"] = {}
            project_config["agents"]["mcp_server"] = "agents/mcp_server"

    # Write the project configuration file
    with open(project_path / "simplemas_project.yml", "w") as f:
        yaml.dump(project_config, f, default_flow_style=False, sort_keys=False)

    if project_path == Path("."):
        click.echo(f"✅ Created SimpleMAS project '{display_name}'")
        click.echo("Project structure initialized in current directory")
    else:
        click.echo(f"✅ Created SimpleMAS project '{project_path}'")
        click.echo(f"Project structure initialized in '{project_path}'")

    if template:
        click.echo(f"Used template: {template}")

    click.echo("\nNext steps:")
    if project_path != Path("."):
        click.echo(f"  cd {project_name}")
    click.echo("  poetry install simple-mas")
    click.echo("  # Start developing your agents!")


@cli.command()
def validate() -> None:
    """Validate the SimpleMAS project configuration."""
    config_path = Path("simplemas_project.yml")

    if not config_path.exists():
        click.echo("❌ Project configuration file 'simplemas_project.yml' not found")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Basic validation
        required_fields = ["name", "version", "agents"]
        for field in required_fields:
            if field not in config:
                click.echo(f"❌ Missing required field '{field}' in project configuration")
                sys.exit(1)

        # Validate agent paths
        for agent_name, agent_path in config.get("agents", {}).items():
            agent_dir = Path(agent_path)
            if not agent_dir.exists():
                click.echo(f"❌ Agent directory '{agent_path}' for agent '{agent_name}' does not exist")
                sys.exit(1)

            agent_file = agent_dir / "agent.py"
            if not agent_file.exists():
                click.echo(f"❌ Agent file 'agent.py' not found in '{agent_path}'")
                sys.exit(1)

        # Validate shared paths
        for shared_path in config.get("shared_paths", []):
            if not Path(shared_path).exists():
                click.echo(f"❌ Shared directory '{shared_path}' does not exist")
                sys.exit(1)

        # Validate extension paths
        for ext_path in config.get("extension_paths", []):
            if not Path(ext_path).exists():
                click.echo(f"❌ Extension directory '{ext_path}' does not exist")
                sys.exit(1)

        click.echo("✅ Project configuration is valid")
        click.echo(f"Project: {config['name']} v{config['version']}")
        click.echo(f"Agents defined: {len(config.get('agents', {}))}")

    except Exception as e:
        click.echo(f"❌ Error validating project configuration: {e}")
        sys.exit(1)


@cli.command(name="list")
@click.argument("resource_type", type=click.Choice(["agents"]))
def list_resources(resource_type: str) -> None:
    """List resources in the SimpleMAS project.

    RESOURCE_TYPE is the type of resource to list (currently only 'agents' is supported).
    """
    config_path = Path("simplemas_project.yml")

    if not config_path.exists():
        click.echo("❌ Project configuration file 'simplemas_project.yml' not found")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if resource_type == "agents":
            agents = config.get("agents", {})
            if not agents:
                click.echo("No agents defined in the project")
                return

            click.echo("Agents defined in the project:")
            for agent_name, agent_path in agents.items():
                click.echo(f"  - {agent_name}: {agent_path}")

    except Exception as e:
        click.echo(f"❌ Error listing {resource_type}: {e}")
        sys.exit(1)


@cli.command()
@click.argument("agent_name", type=str)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Explicit path to the project directory containing simplemas_project.yml",
)
def run(agent_name: str, project_dir: Optional[Path] = None) -> None:
    """Run an agent from the SimpleMAS project.

    AGENT_NAME is the name of the agent to run.
    """
    import asyncio
    import importlib
    import inspect
    import signal
    import sys

    from simple_mas.agent.base import BaseAgent
    from simple_mas.config import _find_project_root

    # Verify that agent_name is not empty
    if not agent_name:
        click.echo("❌ Agent name cannot be empty")
        sys.exit(1)

    # Find project root
    project_root = _find_project_root(project_dir)
    if not project_root:
        if project_dir:
            click.echo(
                f"❌ Project configuration file 'simplemas_project.yml' not found in specified directory: {project_dir}"
            )
        else:
            click.echo(
                "❌ Project configuration file 'simplemas_project.yml' not found in current or parent directories"
            )
        sys.exit(1)

    # Load project configuration
    try:
        with open(project_root / "simplemas_project.yml", "r") as f:
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

    # Get agent path and shared/extension paths
    agent_path = project_root / agents[agent_name]
    agent_file = agent_path / "agent.py"

    if not agent_file.exists():
        click.echo(f"❌ Agent file '{agent_file}' does not exist")
        sys.exit(1)

    # Get shared and extension paths
    shared_paths = [project_root / path for path in project_config.get("shared_paths", [])]
    extension_paths = [project_root / path for path in project_config.get("extension_paths", [])]

    # Set up PYTHONPATH for imports
    original_sys_path = sys.path.copy()
    sys_path_additions = [str(project_root), str(agent_path.parent)]
    for path in shared_paths + extension_paths:
        if path.exists() and str(path) not in sys_path_additions:
            sys_path_additions.append(str(path))

    # Add to sys.path
    for path in sys_path_additions:
        if path not in sys.path:
            sys.path.insert(0, path)

    # Set environment variables
    os.environ["AGENT_NAME"] = agent_name
    os.environ["SIMPLEMAS_ENV"] = os.environ.get("SIMPLEMAS_ENV", "local")

    # Default error message for import failures
    import_error_msg = (
        f"❌ Failed to import agent module from '{agent_file}'. "
        "Check that all dependencies are installed and the agent code is valid."
    )

    try:
        # Convert agent path to a Python module path
        # First remove the project root from the path
        rel_path = agent_path.relative_to(project_root)
        # Convert to module path (replace / with .)
        module_path = str(rel_path).replace("/", ".").replace("\\", ".")
        module_name = f"{module_path}.agent"

        # Import the agent module
        try:
            agent_module = importlib.import_module(module_name)
        except ImportError as e:
            # Try alternative approach if the first fails
            try:
                # Try with a simpler direct import when inside the agent directory
                agent_module = importlib.import_module("agent")
            except ImportError:
                click.echo(f"{import_error_msg}\nError: {e}")
                sys.exit(1)

        # Find the BaseAgent subclass in the module
        agent_class = None
        for name, obj in inspect.getmembers(agent_module):
            if inspect.isclass(obj) and issubclass(obj, BaseAgent) and obj != BaseAgent:  # Skip BaseAgent itself
                agent_class = obj
                break

        if agent_class is None:
            click.echo(f"❌ No BaseAgent subclass found in '{agent_file}'")
            sys.exit(1)

        # Initialize the agent
        click.echo(f"Starting agent '{agent_name}' ({agent_class.__name__})")
        agent = agent_class(name=agent_name)

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        shutdown_event = asyncio.Event()
        agent_task = None

        def signal_handler() -> None:
            click.echo("Shutting down agent gracefully... (press Ctrl+C again to force exit)")
            shutdown_event.set()
            if agent_task:
                agent_task.cancel()

        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

        # Run the agent lifecycle
        async def run_agent() -> None:
            try:
                # Call the setup method
                click.echo("Setting up agent...")
                await agent.setup()

                # Display guidance message for multiple agents
                all_agent_names = list(agents.keys())
                if len(all_agent_names) > 1:
                    other_agents = [a for a in all_agent_names if a != agent_name]
                    click.echo("\n[SimpleMas CLI] Agent start success.")
                    click.echo(
                        "[SimpleMas CLI] To run other agents in this project, open new terminal windows and use:"
                    )
                    for other_agent in other_agents:
                        click.echo(f"[SimpleMas CLI]     simplemas run {other_agent}")
                    click.echo(f"[SimpleMas CLI] Project agents: {', '.join(all_agent_names)}")
                    click.echo("")

                # Create a task for the run method
                nonlocal agent_task
                agent_task = asyncio.create_task(agent.run())

                # Wait for either the agent to complete or a shutdown signal
                done, pending = await asyncio.wait(
                    [agent_task, asyncio.create_task(shutdown_event.wait())], return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel any pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                # Always shut down the agent
                click.echo("Shutting down agent...")
                await agent.shutdown()
                click.echo("Agent shut down successfully")

            except asyncio.CancelledError:
                click.echo("Agent execution cancelled")
                # Ensure shutdown is called
                await agent.shutdown()
            except Exception as e:
                click.echo(f"❌ Error running agent: {e}")
                # Try to shut down gracefully even if there was an error
                try:
                    await agent.shutdown()
                except Exception as shutdown_error:
                    click.echo(f"❌ Error during agent shutdown: {shutdown_error}")
                raise

        # Run the agent
        try:
            loop.run_until_complete(run_agent())
        except KeyboardInterrupt:
            # Handle the case where the user rapidly presses Ctrl+C multiple times
            click.echo("\nForced exit.")
        except Exception as e:
            click.echo(f"❌ Error: {e}")
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error initializing agent: {e}")
        sys.exit(1)
    finally:
        # Restore original sys.path
        sys.path = original_sys_path


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
    help="Explicit path to the project directory containing simplemas_project.yml",
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
    from simple_mas.config import _find_project_root
    from simple_mas.deployment.generators import DockerfileGenerator

    # Find project root
    project_root = _find_project_root(project_dir)
    if not project_root:
        if project_dir:
            click.echo(
                f"❌ Project configuration file 'simplemas_project.yml' not found in specified directory: {project_dir}"
            )
        else:
            click.echo(
                "❌ Project configuration file 'simplemas_project.yml' not found in current or parent directories"
            )
        sys.exit(1)

    # Load project configuration
    try:
        with open(project_root / "simplemas_project.yml", "r") as f:
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

    # Set entrypoint to use the simplemas CLI to run the agent
    # The DockerfileGenerator will use this command in the CMD directive
    # It needs to be a shell command, not the argument to python
    app_entrypoint = f"-m simple_mas.cli run {agent_name}"

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


def main() -> int:
    """Main entry point for the SimpleMAS CLI tool."""
    try:
        cli()
        return 0
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
