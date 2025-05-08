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

## Render Prompt

The `openmas prompts render` command renders a specific prompt for a given agent with provided variables. This is useful for testing how prompt templates will look when rendered with actual values.

```bash
openmas prompts render <agent_name> <prompt_name> [--var key=value] [--project-dir <project_dir>]
```

### Arguments

- `agent_name`: The name of the agent containing the prompt
- `prompt_name`: The name of the prompt to render

### Options

- `--var key=value`: Variables to use when rendering the prompt (can be specified multiple times)
- `--project-dir <project_dir>`: Explicit path to the project directory containing openmas_project.yml

### Examples

Render a prompt with a single variable:

```bash
openmas prompts render my_agent greeting --var name="John Smith"
```

Render a prompt with multiple variables:

```bash
openmas prompts render my_agent analyze --var text="This is a sample text" --var depth=3
```

List the required variables for a prompt without rendering it:

```bash
openmas prompts render my_agent greeting
```

### Output

The command displays the rendered prompt:

```
=== Rendered Prompt ===

Hello, John Smith!

======================
```

If no variables are provided, the command will display the required variables for the prompt:

```
Required variables for prompt 'greeting':
  name

Use --var key=value to provide values for variables
```
