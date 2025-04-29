"""CLI run module for OpenMAS."""

import asyncio
import functools
import importlib.util
import inspect
import os
import signal
import sys
import traceback
from pathlib import Path
from typing import Optional

import click
import typer
import yaml

from openmas.agent.base import BaseAgent
from openmas.config import AgentConfigEntry, ConfigLoader, ProjectConfig, _find_project_root
from openmas.exceptions import ConfigurationError, LifecycleError


def add_package_paths_to_sys_path(packages_dir: str | Path) -> None:
    """Add package paths to sys.path for dependency resolution.

    Scans the packages directory and adds appropriate paths to sys.path so
    that packages can be imported. For packages with a src directory, it adds
    the src directory. For packages without a src directory, it adds the
    package root directory.

    Args:
        packages_dir: Path to the packages directory
    """
    packages_dir = Path(packages_dir)
    if not os.path.isdir(packages_dir):
        return

    # Skip special directories like .git, __pycache__, etc.
    skip_dirs = {".git", "__pycache__", "__pypackages__", ".tox", ".pytest_cache"}

    # Get all directories in the packages directory
    for package_name in os.listdir(packages_dir):
        package_path = packages_dir / package_name

        # Skip non-directories and special directories
        if not os.path.isdir(package_path) or package_name in skip_dirs or package_name.startswith("."):
            continue

        # Check if this package has a src directory
        src_path = package_path / "src"
        if os.path.isdir(src_path):
            # Add the src directory if it exists
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
        else:
            # Otherwise add the package root
            if str(package_path) not in sys.path:
                sys.path.insert(0, str(package_path))


def run_project(agent_name: str, project_dir: Optional[Path] = None, env: Optional[str] = None) -> None:
    """Run an agent from the OpenMAS project using the hardened config loader.

    Args:
        agent_name: Name of the agent to run
        project_dir: Optional explicit path to the project directory
        env: Optional environment name to use for configuration

    Raises:
        typer.Exit: When an error occurs that should terminate execution
    """
    # Set the environment if provided
    if env:
        os.environ["OPENMAS_ENV"] = env
        click.echo(f"Using environment: {env}")

    # Verify that agent_name is not empty
    if not agent_name:
        click.echo("❌ Agent name cannot be empty")
        raise typer.Exit(code=1)

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
        raise typer.Exit(code=1)

    click.echo(f"Using project root: {project_root}")

    # Load and validate project configuration using ConfigLoader
    try:
        config_loader = ConfigLoader()
        config = config_loader.load_yaml_file(project_root / "openmas_project.yml")
        project_config = ProjectConfig(**config)
    except (ConfigurationError, FileNotFoundError, yaml.YAMLError) as e:
        click.echo(f"❌ Error loading project configuration: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        click.echo(f"❌ Unexpected error loading project configuration: {e}")
        raise typer.Exit(code=1)

    # Find the agent in the project configuration
    if agent_name not in project_config.agents:
        click.echo(f"❌ Agent '{agent_name}' not found in project configuration")
        all_agents = list(project_config.agents.keys())
        if all_agents:
            click.echo(f"Available agents: {', '.join(all_agents)}")
        raise typer.Exit(code=1)

    # Get agent config entry
    agent_config_entry = project_config.agents.get(agent_name)
    if not isinstance(agent_config_entry, AgentConfigEntry):
        click.echo(f"❌ Invalid agent configuration for '{agent_name}'")
        raise typer.Exit(code=1)

    # Load agent configuration
    try:
        # Load agent-specific configuration using the agent name as the prefix
        config_loader = ConfigLoader()
        # For now, just create a basic AgentConfig
        # Keeping this variable definition commented out to avoid linting errors until we use it
        # agent_config = AgentConfig(name=agent_name)
    except ConfigurationError as e:
        click.echo(f"❌ Error loading agent configuration: {e}")
        raise typer.Exit(code=1)

    # Get agent module path
    module_path = agent_config_entry.module

    # Get shared and extension paths
    shared_paths = [project_root / path for path in project_config.shared_paths]
    extension_paths = [project_root / path for path in project_config.extension_paths]

    # Store original sys.path to restore later
    original_sys_path = sys.path.copy()

    # Set up PYTHONPATH for imports
    sys_path_additions = []

    # Add project root first to ensure absolute imports work
    sys_path_additions.append(str(project_root))

    # Determine agent directory from module path
    module_parts = module_path.split(".")
    agent_dir_path = project_root
    for part in module_parts:
        agent_dir_path = agent_dir_path / part

    # Add the agent's parent directory
    sys_path_additions.append(str(agent_dir_path.parent))

    # Add the agent directory itself
    sys_path_additions.append(str(agent_dir_path))

    # Add shared and extension paths
    for path in shared_paths + extension_paths:
        if path.exists() and str(path) not in sys_path_additions:
            sys_path_additions.append(str(path))

    # Add packages to sys.path
    packages_dir = project_root / "packages"
    if packages_dir.exists():
        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir():
                # Add primary paths for import - prioritizing src/ directory if it exists
                src_dir = package_dir / "src"
                if src_dir.exists() and src_dir.is_dir():
                    if str(src_dir) not in sys_path_additions:
                        sys_path_additions.append(str(src_dir))
                elif str(package_dir) not in sys_path_additions:
                    sys_path_additions.append(str(package_dir))

    # Update sys.path - add in reverse order so that higher priority paths appear first
    for path_str in reversed(sys_path_additions):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    click.echo("Python import paths:")
    for idx, path_str in enumerate(sys_path_additions):
        click.echo(f"  {idx+1}. {path_str}")

    # Discover local communicators and extensions BEFORE importing agent module
    # This ensures communicators are properly registered before agent code runs
    try:
        from openmas.communication import discover_communicator_extensions, discover_local_communicators

        click.echo("Discovering local communicators...")
        discover_local_communicators([str(path) for path in extension_paths if path.exists()])

        # Also discover package entry point communicators
        discover_communicator_extensions()
    except ImportError as e:
        click.echo(f"❌ Error loading communication modules: {e}")
        raise typer.Exit(code=1)

    # Set environment variables
    os.environ["AGENT_NAME"] = agent_name

    # Use project_root in the environment so agent can load its configuration
    os.environ["OPENMAS_PROJECT_ROOT"] = str(project_root)

    # If OPENMAS_ENV is not set, default to 'local'
    if "OPENMAS_ENV" not in os.environ:
        os.environ["OPENMAS_ENV"] = "local"

    click.echo(f"Using environment: {os.environ.get('OPENMAS_ENV', 'local')}")

    # Try to import the agent module
    agent_module = None
    import_exceptions = []

    try:
        # Try direct module import first
        click.echo(f"Trying to import module: {module_path}")
        agent_module = importlib.import_module(module_path)

        # Check if this is a package rather than a module - if so, try to import module.agent
        if hasattr(agent_module, "__path__") and not hasattr(agent_module, "SimpleAgent"):
            click.echo(f"Detected package, trying to import: {module_path}.agent")
            try:
                agent_module = importlib.import_module(f"{module_path}.agent")
            except ImportError:
                click.echo("Could not import .agent submodule")
    except ImportError as e:
        import_exceptions.append(f"Direct module import: {str(e)}")

        # Try agent.py in the module directory
        try:
            agent_file = agent_dir_path / "agent.py"
            if agent_file.exists():
                click.echo(f"Trying to import from file: {agent_file}")
                spec = importlib.util.spec_from_file_location("agent_module", agent_file)
                if spec is not None and spec.loader is not None:
                    agent_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(agent_module)
        except ImportError as e:
            import_exceptions.append(f"File import: {str(e)}")

    # If all import methods failed
    if agent_module is None:
        error_details = "\n".join(import_exceptions)
        click.echo(f"❌ Failed to import agent module. Tried:\n{error_details}")
        click.echo("Check that all dependencies are installed and the agent code is valid.")
        raise typer.Exit(code=1)

    # Find the BaseAgent subclass in the module
    agent_class = None
    try:
        # First see if we can get the agent class by name
        if hasattr(agent_module, "SimpleAgent") and inspect.isclass(getattr(agent_module, "SimpleAgent")):
            agent_class = getattr(agent_module, "SimpleAgent")
        elif hasattr(agent_module, "Agent") and inspect.isclass(getattr(agent_module, "Agent")):
            agent_class = getattr(agent_module, "Agent")
        else:
            # Fall back to searching all members
            for name, obj in inspect.getmembers(agent_module):
                if inspect.isclass(obj) and hasattr(obj, "__mro__") and BaseAgent in obj.__mro__ and obj != BaseAgent:
                    agent_class = obj
                    break

        if agent_class is None:
            click.echo("❌ No BaseAgent subclass found in agent module")
            click.echo("Make sure the agent file contains a class that inherits from openmas.agent.BaseAgent")
            raise typer.Exit(code=1)
    except Exception as e:
        click.echo(f"❌ Error finding agent class: {e}")
        traceback.print_exc()
        raise typer.Exit(code=1)

    # Initialize the agent with error handling
    try:
        # Use the class_name from the config if it's specified
        if agent_config_entry.class_ != "Agent" and agent_class.__name__ != agent_config_entry.class_:
            # Look for the specified class
            for name, obj in inspect.getmembers(agent_module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BaseAgent)
                    and obj != BaseAgent
                    and name == agent_config_entry.class_
                ):
                    agent_class = obj
                    break
            else:
                click.echo(f"❌ Specified agent class '{agent_config_entry.class_}' not found in agent module")
                raise typer.Exit(code=1)

        # Initialize agent with configuration
        click.echo(f"Starting agent '{agent_name}' ({agent_class.__name__})")
        agent = agent_class(name=agent_name)
    except (ImportError, AttributeError, TypeError, ConfigurationError) as e:
        click.echo(f"❌ Error initializing agent '{agent_name}': {e}")
        click.echo("This may be due to configuration issues or missing dependencies.")
        raise typer.Exit(code=1)
    except Exception as e:
        click.echo(f"❌ Unexpected error initializing agent: {e}")
        traceback.print_exc()
        raise typer.Exit(code=1)

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    stop_in_progress = False

    def signal_handler(signame: Optional[str] = None) -> None:
        nonlocal stop_in_progress
        if stop_in_progress:
            # If we get a second signal during shutdown, exit immediately
            click.echo("\nForced exit. Shutdown already in progress.")
            sys.exit(1)

        if signame:
            click.echo(f"\nReceived signal {signame}, initiating graceful shutdown...")
        else:
            click.echo("\nReceived signal, initiating graceful shutdown...")
        stop_in_progress = True
        shutdown_event.set()

    # Register signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, functools.partial(signal_handler, sig.name))

    # Run the agent lifecycle with enhanced error handling
    async def run_agent() -> None:
        try:
            # Start the agent - this will call setup() and start the communicator
            try:
                await agent.start()
            except LifecycleError as e:
                click.echo(f"❌ Error starting agent: {e}")
                return
            except Exception as e:
                click.echo(f"❌ Unexpected error starting agent: {e}")
                traceback.print_exc()
                return

            # Display guidance message for multiple agents
            all_agent_names = list(project_config.agents.keys())
            if len(all_agent_names) > 1:
                other_agents = [a for a in all_agent_names if a != agent_name]
                click.echo("\n[OpenMAS CLI] Agent start success.")
                click.echo("[OpenMAS CLI] To run other agents in this project, open new terminal windows and use:")
                for other_agent in other_agents:
                    click.echo(f"[OpenMAS CLI]     openmas run {other_agent}")
                click.echo(f"[OpenMAS CLI] Project agents: {', '.join(all_agent_names)}")
                click.echo("")

            # Wait for shutdown signal
            click.echo("Agent is running. Press Ctrl+C to stop.")
            await shutdown_event.wait()

        except asyncio.CancelledError:
            click.echo("Agent execution cancelled")
        except Exception as e:
            click.echo(f"❌ Error in agent execution: {e}")
            traceback.print_exc()
        finally:
            # Always ensure agent is stopped cleanly, even if there was an error
            if agent._is_running:
                click.echo("Stopping agent...")
                try:
                    await agent.stop()
                    click.echo("Agent stopped successfully")
                except Exception as e:
                    click.echo(f"❌ Error stopping agent: {e}")
                    traceback.print_exc()

    # Run the agent
    try:
        loop.run_until_complete(run_agent())
    except KeyboardInterrupt:
        # Handle the case where the user rapidly presses Ctrl+C multiple times
        click.echo("\nForced exit.")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        traceback.print_exc()
        raise typer.Exit(code=1)
    finally:
        # Ensure event loop is properly cleaned up
        try:
            # Cancel any pending tasks
            pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
            if pending_tasks:
                click.echo(f"Cancelling {len(pending_tasks)} pending tasks...")
                for task in pending_tasks:
                    task.cancel()

                # Give them a moment to shut down
                if pending_tasks:
                    loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        except Exception as e:
            click.echo(f"Error cleaning up tasks: {e}")

        # Close the event loop cleanly
        if hasattr(loop, "shutdown_asyncgens"):
            loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

        # Restore original sys.path
        sys.path = original_sys_path
