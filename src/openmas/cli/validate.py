"""Validate OpenMAS project configuration."""

import re
from pathlib import Path
from typing import List, Set, cast

import click
from pydantic import ValidationError

from openmas.config import AgentConfigEntry, ConfigLoader, ProjectConfig
from openmas.exceptions import ConfigurationError


def validate_prompt_configs(agent_name: str, agent_config: AgentConfigEntry, project_root: Path) -> List[str]:
    """Validate prompt configurations for an agent.

    Args:
        agent_name: Name of the agent
        agent_config: Agent configuration object
        project_root: Root of the project

    Returns:
        List of validation errors (empty if valid)
    """
    errors: List[str] = []

    if not agent_config.prompts:
        return errors

    # Determine the prompts directory path
    prompts_dir = project_root
    if agent_config.prompts_dir:
        prompts_dir = project_root / agent_config.prompts_dir

    # Track prompt names to check for uniqueness
    prompt_names: Set[str] = set()

    for i, prompt_config in enumerate(agent_config.prompts):
        # Check for duplicate prompt names
        if prompt_config.name in prompt_names:
            errors.append(f"❌ Agent '{agent_name}': Duplicate prompt name '{prompt_config.name}'")
        else:
            prompt_names.add(prompt_config.name)

        # Check for template_file existence if specified
        if prompt_config.template_file:
            template_path = prompts_dir / prompt_config.template_file
            if not template_path.exists():
                errors.append(
                    f"❌ Agent '{agent_name}': Prompt template file '{prompt_config.template_file}' "
                    f"not found in {prompts_dir}"
                )

        # Basic sanity check for variables in inline template
        if prompt_config.template and prompt_config.input_variables:
            for var in prompt_config.input_variables:
                # Check if variable placeholder appears in the template
                # Look for patterns like {{var}} or {{ var }} with flexible whitespace
                var_pattern = r"\{\{\s*" + re.escape(var) + r"\s*\}\}"
                if not re.search(var_pattern, prompt_config.template):
                    errors.append(
                        f"⚠️ Agent '{agent_name}': Variable '{var}' is listed in input_variables "
                        f"but not found in the template for prompt '{prompt_config.name}'"
                    )

    return errors


def validate_sampling_config(agent_name: str, agent_config: AgentConfigEntry) -> List[str]:
    """Validate sampling configuration for an agent.

    Args:
        agent_name: Name of the agent
        agent_config: Agent configuration object

    Returns:
        List of validation errors (empty if valid)
    """
    errors: List[str] = []

    if not agent_config.sampling:
        return errors

    sampling = agent_config.sampling

    # Check for supported providers
    supported_providers = ["mcp"]
    if sampling.provider and sampling.provider not in supported_providers:
        errors.append(
            f"❌ Agent '{agent_name}': Unsupported sampling provider '{sampling.provider}'. "
            f"Supported providers: {', '.join(supported_providers)}"
        )

    # Check for MCP provider compatibility
    if sampling.provider == "mcp":
        communicator = agent_config.communicator
        if communicator and not (communicator.startswith("mcp_") or communicator == "mcp"):
            errors.append(
                f"⚠️ Agent '{agent_name}': Using 'mcp' sampling provider with non-MCP communicator '{communicator}'. "
                f"This may cause compatibility issues."
            )

    # Note: Pydantic will handle range validations for parameters like temperature, top_p, etc.
    # during the model validation phase, so we don't need to duplicate those checks here

    return errors


def validate_config(config_path: Path = Path("openmas_project.yml")) -> int:
    """Validate the OpenMAS project configuration.

    Args:
        config_path: Path to the OpenMAS project configuration file

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if not config_path.exists():
        click.echo(f"❌ Project configuration file '{config_path}' not found")
        return 1

    try:
        # Load the YAML file using the hardened ConfigLoader
        config_loader = ConfigLoader()
        config_dict = config_loader.load_yaml_file(config_path)

        if not config_dict:
            click.echo(f"❌ Project configuration file '{config_path}' is empty or invalid YAML")
            return 1

        # First stage validation - Pydantic model validation
        try:
            config = ProjectConfig(**config_dict)
            click.echo("✅ Project configuration schema is valid")
        except ValidationError as e:
            click.echo("❌ Invalid project configuration:")
            for error in e.errors():
                loc = " -> ".join(str(loc_item) for loc_item in error["loc"])
                msg = error["msg"]
                click.echo(f"  - Error in {loc}: {msg}")
            return 1

        # Second stage validation - Check if referenced resources exist

        # 1. Check agent paths
        for agent_name, agent_config in config.agents.items():
            # In model_post_init, all agent configs are converted to AgentConfigEntry
            # Cast to ensure type checking works correctly
            agent_entry = cast(AgentConfigEntry, agent_config)
            module_parts = agent_entry.module.split(".")

            # Convert module path to directory path for validation
            # This is an approximation - in practice, Python modules could be organized differently
            possible_paths: List[Path] = [
                Path(*module_parts),  # Direct module path (foo.bar -> foo/bar)
                Path(*module_parts[:-1]) / f"{module_parts[-1]}.py",  # Module file (foo.bar -> foo/bar.py)
                Path(*module_parts) / "agent.py",  # Agent module (foo.bar -> foo/bar/agent.py)
                Path(agent_name),  # Just agent name
                Path(f"agents/{agent_name}"),  # Common pattern
            ]

            agent_found = False
            for agent_path in possible_paths:
                if agent_path.exists():
                    click.echo(f"✅ Agent '{agent_name}' found at '{agent_path}'")
                    agent_found = True
                    break

            if not agent_found:
                click.echo(
                    f"⚠️ Agent '{agent_name}': Could not find agent module at expected locations. "
                    + f"Module: {agent_entry.module}"
                )

            # Validate prompts configuration
            prompt_errors: List[str] = validate_prompt_configs(agent_name, agent_entry, config_path.parent)
            for error_str in prompt_errors:
                click.echo(error_str)

            # Validate sampling configuration
            sampling_errors: List[str] = validate_sampling_config(agent_name, agent_entry)
            for error_str in sampling_errors:
                click.echo(error_str)

        # 2. Validate shared paths
        all_shared_paths_exist = True
        for shared_path in config.shared_paths:
            path = Path(shared_path)
            if not path.exists():
                click.echo(f"❌ Shared directory '{shared_path}' does not exist")
                all_shared_paths_exist = False

        if all_shared_paths_exist and config.shared_paths:
            click.echo("✅ All shared paths exist")
        elif not config.shared_paths:
            click.echo("ℹ️ No shared paths configured")

        # 3. Validate extension paths
        all_ext_paths_exist = True
        for ext_path in config.extension_paths:
            path = Path(ext_path)
            if not path.exists():
                click.echo(f"❌ Extension directory '{ext_path}' does not exist")
                all_ext_paths_exist = False

        if all_ext_paths_exist and config.extension_paths:
            click.echo("✅ All extension paths exist")
        elif not config.extension_paths:
            click.echo("ℹ️ No extension paths configured")

        # 4. Validate dependencies
        if config.dependencies:
            click.echo(f"Validating {len(config.dependencies)} dependencies...")
            all_deps_valid = True

            for i, dep in enumerate(config.dependencies):
                # Each dependency must have exactly one type key
                dep_types = [key for key in ["git", "package", "local"] if key in dep]
                if len(dep_types) != 1:
                    click.echo(f"❌ Dependency #{i + 1} must have exactly one type (git, package, or local)")
                    all_deps_valid = False
                    continue

                dep_type = dep_types[0]

                # Git dependencies must have a valid URL
                if dep_type == "git":
                    git_url = dep["git"]
                    if not git_url or not isinstance(git_url, str):
                        click.echo(f"❌ Git dependency #{i + 1} has invalid URL: {git_url}")
                        all_deps_valid = False
                        continue

                # Package dependencies must have a valid version
                elif dep_type == "package":
                    package_name = dep["package"]
                    if not package_name or not isinstance(package_name, str):
                        click.echo(f"❌ Package dependency #{i + 1} has invalid name: {package_name}")
                        all_deps_valid = False
                        continue

                    if "version" not in dep:
                        click.echo(f"❌ Package dependency '{package_name}' is missing required 'version' field")
                        all_deps_valid = False
                        continue

                # Local dependencies must have a valid path
                elif dep_type == "local":
                    local_path = dep["local"]
                    if not local_path or not isinstance(local_path, str):
                        click.echo(f"❌ Local dependency #{i + 1} has invalid path: {local_path}")
                        all_deps_valid = False
                        continue

                    # Check if the path exists
                    if not Path(local_path).exists():
                        click.echo(f"❌ Local dependency path '{local_path}' does not exist")
                        all_deps_valid = False
                        continue

            if all_deps_valid:
                click.echo("✅ Dependencies schema is valid")
                click.echo("⚠️ Note: Only 'git' dependencies are fully implemented")
        else:
            click.echo("ℹ️ No dependencies configured")

        # 5. Check if there were any prompt or sampling errors
        has_validation_errors = False

        for agent_name, agent_config in config.agents.items():
            agent_entry = cast(AgentConfigEntry, agent_config)
            prompt_errors = validate_prompt_configs(agent_name, agent_entry, config_path.parent)
            sampling_errors = validate_sampling_config(agent_name, agent_entry)

            if prompt_errors or sampling_errors:
                has_validation_errors = True
                break

        if has_validation_errors:
            click.echo("❌ Project configuration has validation errors. Fix them before proceeding.")
            return 1

        click.echo(f"✅ Project configuration '{config_path}' is valid")
        click.echo(f"Project: {config.name} v{config.version}")
        click.echo(f"Agents defined: {len(config.agents)}")
        return 0

    except ConfigurationError as e:
        click.echo(f"❌ {e}")
        return 1
    except FileNotFoundError as e:
        click.echo(f"❌ File not found: {e}")
        return 1
    except Exception as e:
        click.echo(f"❌ Error validating project configuration: {e}")
        return 1
