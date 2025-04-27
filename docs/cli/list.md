# `openmas list` Command

The `openmas list` command displays resources defined in your OpenMAS project, such as agents, making it easier to understand your project structure.

## Usage

```bash
openmas list [RESOURCE_TYPE]
```

Where:
- `[RESOURCE_TYPE]` is the type of resource to list (currently only "agents" is supported)

## Purpose

This command helps you view resources defined in your project configuration, providing a quick overview of what's available in your multi-agent system.

## Example Usage

```bash
# List all agents in the project
openmas list agents
```

## Available Resource Types

### agents

Lists all agents defined in your project's `openmas_project.yml` file.

Example output:

```
╒════════════════╤═══════════════════════╕
│ Agent Name     │ Path                  │
╞════════════════╪═══════════════════════╡
│ orchestrator   │ agents/orchestrator   │
├────────────────┼───────────────────────┤
│ worker1        │ agents/worker1        │
├────────────────┼───────────────────────┤
│ worker2        │ agents/worker2        │
╘════════════════╧═══════════════════════╛
```

## Related Commands

- `openmas init`: Initialize a new OpenMAS project
- `openmas validate`: Validate the project configuration
- `openmas run`: Run an agent from the project
