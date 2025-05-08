# `openmas validate` Command

The `openmas validate` command checks your OpenMAS project configuration for correctness and consistency, helping you catch issues before running your agents.

## Usage

```bash
openmas validate [OPTIONS]
```

## Purpose

This command performs a series of validation checks on your OpenMAS project to ensure that:

1. The `openmas_project.yml` file has the required structure
2. All referenced agent paths exist
3. All referenced shared and plugin paths exist
4. Dependencies are correctly specified
5. The configuration format is valid
6. Prompt configurations are valid and reference existing files
7. Sampling configurations are compatible with the agent's communicator

It helps identify issues early, such as missing files or invalid references, before you try to run your agents.

## Example Usage

```bash
# Validate project in the current directory
openmas validate
```

## Validation Checks

The command performs the following validation checks:

### Project Configuration

- Validates that `openmas_project.yml` exists
- Checks that required fields (`name`, `version`) are present
- Validates the format of optional fields (`agents`, `shared_paths`, `plugin_paths`, `default_config`, `dependencies`)

### Agent Paths

For each agent defined in the `agents` section:
- Validates that the agent directory exists
- Checks that the agent directory contains an `agent.py` file
- Verifies that `agent.py` contains a `BaseAgent` subclass

### Prompt Configuration

For each agent with prompt configurations:
- Validates that each prompt has a unique name within the agent
- Checks that template files referenced by `template_file` exist in the `prompts_dir`
- Verifies that variables listed in `input_variables` appear in the template with the expected `{{variable}}` syntax
- Confirms that either `template` or `template_file` is provided for each prompt

### Sampling Configuration

For each agent with sampling configurations:
- Validates the sampling provider (if specified)
- Checks that the provider is compatible with the communicator type (e.g., "mcp" provider with "mcp_sse" communicator)
- Verifies that required parameters for the provider are present

### Shared and Plugin Paths

- Validates that all paths in `shared_paths` exist
- Validates that all paths in `plugin_paths` exist

### Dependencies

For each dependency in the `dependencies` section:
- Validates the dependency type (`git`, `package`, or `local`)
- For `git` dependencies, checks that the URL is valid
- For `package` dependencies, checks that the version is specified
- For `local` dependencies, checks that the path exists

## Exit Codes

- `0`: Validation successful
- `1`: Validation failed (with error messages)

## Example Feedback

Here are examples of the feedback provided:

### Successful Validation

```
✅ Project configuration found and validated
✅ Agent 'orchestrator' found at 'agents/orchestrator'
✅ Agent 'worker' found at 'agents/worker'
✅ All shared paths exist
✅ All plugin paths exist
✅ Dependencies validated
```

### Failed Validation

```
✅ Project configuration found
❌ Agent 'orchestrator': Directory 'agents/orchestrator' does not exist
✅ Agent 'worker' found at 'agents/worker'
❌ Shared path 'shared/missing' does not exist
✅ All plugin paths exist
❌ Git dependency 'https://example.com/invalid.git': Invalid URL format
```

## Related Commands

- `openmas init`: Initialize a new OpenMAS project
- `openmas list agents`: List agents defined in the project
- `openmas run`: Run an agent from the project
