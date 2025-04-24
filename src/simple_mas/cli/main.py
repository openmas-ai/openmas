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
def init(project_name: str, template: Optional[str]) -> None:
    """Initialize a new SimpleMAS project with standard directory structure.

    PROJECT_NAME is the name of the project to create.
    """
    project_path = Path(project_name)

    if project_path.exists():
        click.echo(f"❌ Project directory '{project_name}' already exists.")
        sys.exit(1)

    # Create main project directory
    project_path.mkdir(parents=True)

    # Create subdirectories
    subdirs = ["agents", "shared", "extensions", "config", "tests"]
    for subdir in subdirs:
        (project_path / subdir).mkdir()

    # Create README.md
    with open(project_path / "README.md", "w") as f:
        f.write(f"# {project_name}\n\nA SimpleMAS project.\n")

    # Create requirements.txt
    with open(project_path / "requirements.txt", "w") as f:
        f.write("simple-mas>=0.1.0\n")

    # Create simplemas_project.yml
    project_config: Dict[str, Any] = {
        "name": project_name,
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
            agent_dir.mkdir(parents=True)

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

    click.echo(f"✅ Created SimpleMAS project '{project_name}'")
    click.echo(f"Project structure initialized in '{project_path}'")
    if template:
        click.echo(f"Used template: {template}")
    click.echo("\nNext steps:")
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
def run(agent_name: str) -> None:
    """Run an agent from the SimpleMAS project.

    AGENT_NAME is the name of the agent to run.
    """
    config_path = Path("simplemas_project.yml")

    if not config_path.exists():
        click.echo("❌ Project configuration file 'simplemas_project.yml' not found")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        agents = config.get("agents", {})
        if agent_name not in agents:
            click.echo(f"❌ Agent '{agent_name}' not found in project configuration")
            sys.exit(1)

        agent_path = agents[agent_name]
        agent_file = Path(agent_path) / "agent.py"

        if not agent_file.exists():
            click.echo(f"❌ Agent file '{agent_file}' does not exist")
            sys.exit(1)

        # Set agent name environment variable
        os.environ["AGENT_NAME"] = agent_name

        # Apply default config from the project configuration
        if "default_config" in config:
            # This environment variable will be picked up by the enhanced load_config
            os.environ["SIMPLEMAS_PROJECT_CONFIG"] = yaml.dump(config)

        click.echo(f"Running agent '{agent_name}'")
        # Execute the agent file
        # In a real implementation, this would use importlib to load and run the agent module
        # For now, we'll just print a message
        click.echo(f"Agent would be executed from file: {agent_file}")

    except Exception as e:
        click.echo(f"❌ Error running agent '{agent_name}': {e}")
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
