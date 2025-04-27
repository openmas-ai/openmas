# `openmas init` Command

The `openmas init` command helps you initialize a new OpenMAS project with the standard directory structure and configuration files.

## Usage

```bash
openmas init <project_name> [OPTIONS]
```

Where:
- `<project_name>` is the name of the project to create, or "." to initialize in the current directory.

## Options

- `--template, -t TEXT`: Template to use for project initialization (e.g., "mcp-server")
- `--name TEXT`: Project name when initializing in current directory (required if `project_name` is ".")

## Purpose

This command creates a new OpenMAS project with a standardized directory structure, making it easy to start building multi-agent systems. It:

1. Creates the project directory (unless using the current directory)
2. Sets up the standard directory structure
3. Creates starter configuration files
4. (Optionally) Sets up a template with specific agent implementations

## Directory Structure

The command creates the following directory structure:

```
project_name/
├── agents/               # Agent implementations
├── shared/               # Shared code between agents
├── extensions/           # Custom extensions
├── config/               # Configuration files
├── tests/                # Test files
├── packages/             # External dependencies
├── .gitignore            # Git ignore file
├── openmas_project.yml   # Project configuration
├── README.md             # Project README
└── requirements.txt      # Python dependencies
```

## Example Usage

### Create a New Project

```bash
# Create a new project named "my_project"
openmas init my_project
```

### Initialize in Current Directory

```bash
# Initialize in the current directory
openmas init . --name my_project
```

### Use a Template

```bash
# Create a new project with the MCP server template
openmas init my_mcp_project --template mcp-server
```

## Template Options

The `--template` option allows you to create a project with pre-configured components. Currently supported templates include:

### mcp-server

Creates a project with an MCP server agent preconfigured:

```bash
openmas init my_mcp_project --template mcp-server
```

This will create:
- A directory structure for an MCP server agent
- A sample implementation in `agents/mcp_server/agent.py`
- A deployment configuration in `agents/mcp_server/openmas.deploy.yaml`

## Project Configuration

The command creates an `openmas_project.yml` file with the following structure:

```yaml
name: "my_project"
version: "0.1.0"
agents: {}  # Will contain agent definitions
shared_paths: ["shared"]
plugin_paths: ["extensions"]
default_config:
  log_level: "INFO"
  communicator_type: "http"
dependencies: []  # External dependencies
```

## Next Steps

After initializing a project, you can:

1. Create agent implementations in the `agents/` directory
2. Register your agents in the `openmas_project.yml` file
3. Run your agents with the `openmas run` command
4. Validate your project configuration with `openmas validate`

## Related Commands

- `openmas run`: Run an agent from the project
- `openmas validate`: Validate the project configuration
- `openmas list agents`: List agents defined in the project
