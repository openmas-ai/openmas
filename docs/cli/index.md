# OpenMAS CLI

OpenMAS includes a command-line interface (CLI) to help you manage your multi-agent system projects. The CLI provides tools for project initialization, validation, agent listing, dependency management, prompt management, and running agents locally.

## Available Commands

- **[openmas init](./init.md)**: Initialize a new OpenMAS project with standard directory structure
- **[openmas validate](./validate.md)**: Validate the OpenMAS project configuration
- **[openmas list agents](./list.md)**: List agents defined in the project
- **[openmas prompts list](./prompts.md)**: List prompts defined in the project
- **[openmas run](./run.md)**: Run an agent from the OpenMAS project
- **[openmas deps](./deps.md)**: Manage project dependencies
- **[openmas generate-dockerfile](./generate-dockerfile.md)**: Generate a Dockerfile for an agent

## Installation

The CLI is automatically installed when you install the OpenMAS package:

```bash
pip install openmas
```

## Usage

```bash
# Show help
openmas --help

# Show help for a specific command
openmas run --help
```

## Environmental Requirements

Running agents using the CLI requires:

1. A properly structured OpenMAS project (created with `openmas init` or following the same conventions)
2. A `openmas_project.yml` file in the project root
3. Agent directories containing `agent.py` files with `BaseAgent` subclasses

For more details on project structure and conventions, see the [Getting Started](../guides/getting_started.md) guide.
