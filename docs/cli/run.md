# `openmas run` Command

The `openmas run` command is a cornerstone of the OpenMAS developer experience, designed for local execution and debugging of a single agent within a multi-agent system. It functions similarly to `dbt run` in its role within the development loop.

## Usage

```bash
openmas run <agent_name> [--project-dir PATH]
```

Where:
- `<agent_name>` is the name of an agent defined in your project's `openmas_project.yml` file.
- `--project-dir PATH` (optional) is an explicit path to the project directory containing the `openmas_project.yml` file.

## Purpose

This command provides a standardized, framework-aware way to run and test individual agents locally. It:

1. Finds your project root (location of `openmas_project.yml`)
2. Loads the complete, layered configuration stack
3. Sets up Python paths for imports from `shared/` and `extensions/` directories
4. Dynamically loads and instantiates the specified agent
5. Executes the agent's lifecycle methods (`setup()`, `run()`, and `shutdown()`) via `asyncio`
6. Blocks the terminal while the agent's `run()` method executes
7. Provides guidance for running other agents in separate terminals
8. Gracefully handles signals (Ctrl+C) to ensure proper shutdown

## Configuration Loading

When running an agent, configuration is loaded in the following order (lowest to highest precedence):

1. OpenMAS SDK internal defaults (defined in Pydantic models)
2. `default_config` section in `openmas_project.yml`
3. `config/default.yml` file
4. `config/<OPENMAS_ENV>.yml` file (defaults to `local.yml` if `OPENMAS_ENV` is not set)
5. `.env` file at project root
6. Environment variables (highest precedence)

This layered approach allows for flexible configuration management across different environments.

## Running Multiple Agents

To run a full multi-agent system locally, you need to:

1. Open a separate terminal window for each agent
2. Run each agent with `openmas run <agent_name>`

After successfully starting an agent, if your project contains multiple agents, the command will display a helpful guidance message suggesting how to run the other agents in your project.

## Example

```bash
# In terminal 1
$ openmas run orchestrator

Starting agent 'orchestrator' (OrchestratorAgent)
Setting up agent...

[OpenMAS CLI] Agent start success.
[OpenMAS CLI] To run other agents in this project, open new terminal windows and use:
[OpenMAS CLI]     openmas run worker1
[OpenMAS CLI]     openmas run worker2
[OpenMAS CLI] Project agents: orchestrator, worker1, worker2

# In terminal 2
$ openmas run worker1
...

# In terminal 3
$ openmas run worker2
...
```

### Example with project directory specified

```bash
# Running from outside the project directory
$ openmas run orchestrator --project-dir /path/to/my/project

Starting agent 'orchestrator' (OrchestratorAgent)
Setting up agent...
```

## Graceful Shutdown

The command handles `SIGINT` (Ctrl+C) and `SIGTERM` signals gracefully, ensuring that:

1. The agent's `run()` method is cancelled or completes
2. The agent's `shutdown()` method is called to perform cleanup
3. The process exits cleanly

## Python Path Management

When running an agent, the command automatically sets up the Python path to include:

1. The project root directory
2. The agent's parent directory
3. All directories listed in `shared_paths` in your project configuration
4. All directories listed in `extension_paths` in your project configuration

This enables imports from shared modules and extensions without requiring manual `PYTHONPATH` manipulation.

## Error Handling

The command provides specific and informative error messages for common issues:

- Missing project configuration
- Agent not found in configuration
- Missing agent module file
- Import errors
- No BaseAgent subclass found
- Exceptions during agent setup, run, or shutdown

## Related Commands

- `openmas init`: Initialize a new OpenMAS project
- `openmas validate`: Validate project configuration
- `openmas list agents`: List agents defined in the project
