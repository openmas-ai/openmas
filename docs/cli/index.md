# SimpleMAS CLI

SimpleMAS includes a command-line interface (CLI) to help you manage your multi-agent system projects. The CLI provides tools for project initialization, validation, agent listing, and running agents locally.

## Available Commands

- **[simplemas init](./init.md)**: Initialize a new SimpleMAS project with standard directory structure
- **[simplemas validate](./validate.md)**: Validate the SimpleMAS project configuration
- **[simplemas list agents](./list.md)**: List agents defined in the project
- **[simplemas run](./run.md)**: Run an agent from the SimpleMAS project

## Installation

The CLI is automatically installed when you install the SimpleMAS package:

```bash
poetry add simple-mas
```

## Usage

```bash
# Show help
simplemas --help

# Show help for a specific command
simplemas run --help
```

## Environmental Requirements

Running agents using the CLI requires:

1. A properly structured SimpleMAS project (created with `simplemas init` or following the same conventions)
2. A `simplemas_project.yml` file in the project root
3. Agent directories containing `agent.py` files with `BaseAgent` subclasses

For more details on project structure and conventions, see the [Getting Started](../getting_started.md) guide.
