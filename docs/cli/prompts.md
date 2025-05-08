# Prompt Management Commands

The `openmas prompts` command group provides tools for working with prompt templates defined in your OpenMAS project.

## List Prompts

The `openmas prompts list` command displays all prompts defined in your project, showing their structure, source, and input variables.

```bash
openmas prompts list [--agent <agent_name>] [--project-dir <project_dir>]
```

### Options

- `--agent <agent_name>`: Filter prompts by agent name
- `--project-dir <project_dir>`: Explicit path to the project directory containing openmas_project.yml

### Examples

List all prompts across all agents:

```bash
openmas prompts list
```

List prompts for a specific agent:

```bash
openmas prompts list --agent my_agent
```

### Output

The command displays detailed information about each prompt:

```
🤖 Agent: my_agent

  📝 Prompt: greeting
    Template (inline): Hello, {{name}}!
    Input variables: name

  📝 Prompt: farewell
    Template file: farewell.txt
    Input variables: name
```

For each prompt, the output includes:
- The prompt name
- Template content (truncated if too long) or template file path
- Input variables expected by the template

## Prompt Configuration

Prompts in OpenMAS are defined in the `openmas_project.yml` file under each agent's configuration. Here's an example:

```yaml
agents:
  my_agent:
    module: "agents.my_agent"
    class: "MyAgent"
    prompts_dir: "prompts"  # Directory for template files (relative to project root)
    prompts:
      - name: "greeting"
        template: "Hello, {{name}}!"  # Inline template
        input_variables: ["name"]
      - name: "farewell"
        template_file: "farewell.txt"  # File-based template
        input_variables: ["name"]
```

Each prompt can have either:
- An inline template using the `template` field, or
- A reference to a template file using the `template_file` field

Template files are looked up in the directory specified by `prompts_dir` (defaults to "prompts" if not specified).
