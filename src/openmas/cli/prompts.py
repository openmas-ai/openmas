"""Prompt management CLI commands for OpenMAS."""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import click

from openmas.config import ConfigLoader, ProjectConfig, _find_project_root


class SimpleTemplateRenderer:
    """A simple template renderer for the CLI."""

    def __init__(self, template: str, input_variables: List[str]) -> None:
        """Initialize the template renderer.

        Args:
            template: The template string
            input_variables: List of variable names used in the template
        """
        self.template = template
        self.input_variables = input_variables

    def format(self, variables: Dict[str, str]) -> str:
        """Format the template with variables.

        Args:
            variables: Dictionary of variable names to values

        Returns:
            The formatted template

        Raises:
            KeyError: If a required variable is missing
        """
        result = self.template
        for var_name in self.input_variables:
            if var_name not in variables:
                raise KeyError(var_name)

            placeholder = f"{{{{{var_name}}}}}"
            result = result.replace(placeholder, variables[var_name])

        return result


def _load_project_config(project_dir: Optional[Path] = None) -> Dict:
    """Load the OpenMAS project configuration.

    Args:
        project_dir: Optional explicit path to the project directory

    Returns:
        The loaded project configuration as a dictionary

    Raises:
        SystemExit: If the project configuration cannot be loaded
    """
    # Find project root
    project_root = _find_project_root(project_dir)
    if not project_root:
        if project_dir:
            click.echo(
                f"❌ Project configuration file 'openmas_project.yml' not found in specified directory: {project_dir}"
            )
        else:
            click.echo("❌ Project configuration file 'openmas_project.yml' not found in current or parent directories")
            click.echo("Hint: Make sure you're running the command from within an OpenMAS project or use --project-dir")
        sys.exit(1)

    # Load and validate project configuration using ConfigLoader
    try:
        config_loader = ConfigLoader()
        config = config_loader.load_yaml_file(project_root / "openmas_project.yml")
        # Validate config with ProjectConfig model
        ProjectConfig(**config)
        return config
    except Exception as e:
        click.echo(f"❌ Error loading project configuration: {e}")
        sys.exit(1)


@click.group()
def prompts() -> None:
    """Manage prompts in an OpenMAS project."""
    pass


@prompts.command(name="list")
@click.option("--agent", help="Filter prompts by agent name")
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Explicit path to the project directory containing openmas_project.yml",
)
def list_prompts(agent: Optional[str] = None, project_dir: Optional[Path] = None) -> None:
    """List all prompts defined in the project, or for a specific agent."""
    # Load project configuration
    config = _load_project_config(project_dir)
    agents_config = config.get("agents", {})

    if agent and agent not in agents_config:
        click.echo(f"❌ Agent '{agent}' not found in project configuration")
        sys.exit(1)

    # Track if any prompts were found
    prompts_found = False

    # Process each agent
    for agent_name, agent_config in agents_config.items():
        # Skip if filtering by agent and this isn't the one we want
        if agent and agent != agent_name:
            continue

        # Skip if the agent config is just a string (no detailed config)
        if isinstance(agent_config, str):
            continue

        # Get prompts for this agent
        prompts = agent_config.get("prompts", [])
        if not prompts:
            continue

        # We found prompts
        prompts_found = True

        # Print agent header
        click.echo(f"\n🤖 Agent: {agent_name}")

        # Display each prompt
        for i, prompt in enumerate(prompts):
            # Extract prompt details
            name = prompt.get("name", "Unnamed prompt")
            template = prompt.get("template", "")
            template_file = prompt.get("template_file", "")
            input_vars = prompt.get("input_variables", [])

            # Print prompt details
            click.echo(f"\n  📝 Prompt: {name}")
            if template:
                # Truncate long templates for display
                if len(template) > 120:
                    template = template[:117] + "..."
                click.echo(f"    Template (inline): {template}")
            elif template_file:
                click.echo(f"    Template file: {template_file}")
            else:
                click.echo("    Template: None")

            if input_vars:
                click.echo(f"    Input variables: {', '.join(input_vars)}")
            else:
                click.echo("    Input variables: None")

    # If no prompts were found
    if not prompts_found:
        if agent:
            click.echo(f"No prompts defined for agent '{agent}'")
        else:
            click.echo("No prompts defined in the project")


@prompts.command(name="render")
@click.argument("agent_name", type=str)
@click.argument("prompt_name", type=str)
@click.option(
    "--var",
    "variables",
    type=str,
    multiple=True,
    help="Variables for the prompt in the format key=value. Can be specified multiple times.",
)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Explicit path to the project directory containing openmas_project.yml",
)
def render_prompt(agent_name: str, prompt_name: str, variables: List[str], project_dir: Optional[Path] = None) -> None:
    """Render a specific prompt for an agent with provided variables.

    AGENT_NAME is the name of the agent containing the prompt.
    PROMPT_NAME is the name of the prompt to render.
    """
    # Load project configuration
    config = _load_project_config(project_dir)
    agents_config = config.get("agents", {})

    # Validate agent exists
    if agent_name not in agents_config:
        click.echo(f"❌ Agent '{agent_name}' not found in project configuration")
        sys.exit(1)

    agent_config = agents_config[agent_name]

    # Handle string-only agent configs
    if isinstance(agent_config, str):
        click.echo(f"❌ Agent '{agent_name}' has no detailed configuration (string-only reference)")
        sys.exit(1)

    # Get prompts for this agent
    prompts_config = agent_config.get("prompts", [])
    if not prompts_config:
        click.echo(f"❌ No prompts defined for agent '{agent_name}'")
        sys.exit(1)

    # Find the specified prompt
    prompt_config = None
    for p in prompts_config:
        if p.get("name") == prompt_name:
            prompt_config = p
            break

    if not prompt_config:
        click.echo(f"❌ Prompt '{prompt_name}' not found for agent '{agent_name}'")
        sys.exit(1)

    # Parse variables from command line options
    parsed_vars: Dict[str, str] = {}
    for var in variables:
        try:
            key, value = var.split("=", 1)
            parsed_vars[key.strip()] = value.strip()
        except ValueError:
            click.echo(f"❌ Invalid variable format: {var}. Expected format: key=value")
            sys.exit(1)

    # Get prompt template and template content
    template_content = ""
    if "template" in prompt_config:
        template_content = prompt_config["template"]
    elif "template_file" in prompt_config:
        # Get prompt directory
        prompts_dir = agent_config.get("prompts_dir", "prompts")
        project_root = _find_project_root(project_dir)
        if not project_root:
            click.echo("❌ Project root not found")
            sys.exit(1)

        # Read template from file
        template_file = project_root / prompts_dir / prompt_config["template_file"]
        if not template_file.exists():
            click.echo(f"❌ Template file not found: {template_file}")
            sys.exit(1)

        try:
            with open(template_file, "r") as f:
                template_content = f.read()
        except Exception as e:
            click.echo(f"❌ Error reading template file: {e}")
            sys.exit(1)
    else:
        click.echo("❌ Prompt has neither 'template' nor 'template_file' defined")
        sys.exit(1)

    # Create PromptTemplate and render it
    try:
        input_variables = prompt_config.get("input_variables", [])
        prompt_template = SimpleTemplateRenderer(template=template_content, input_variables=input_variables)

        # Display required variables if none provided
        if not parsed_vars and input_variables:
            click.echo(f"Required variables for prompt '{prompt_name}':")
            for var in input_variables:
                click.echo(f"  {var}")
            click.echo("\nUse --var key=value to provide values for variables")
            return

        # Render the prompt
        try:
            rendered_prompt = prompt_template.format(parsed_vars)
            click.echo("\n=== Rendered Prompt ===\n")
            click.echo(rendered_prompt)
            click.echo("\n======================\n")
        except KeyError as e:
            var_name = str(e).strip("'")
            click.echo(f"❌ Missing required variable: {var_name}")
            click.echo(f"Required variables: {', '.join(input_variables)}")
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error rendering prompt: {e}")
        sys.exit(1)
