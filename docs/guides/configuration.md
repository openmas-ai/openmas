# OpenMAS Configuration System

OpenMAS provides a flexible configuration system that supports layered configuration from multiple sources. This guide explains how the configuration system works, the precedence of different configuration sources, and how to use it in your projects.

## Configuration Sources and Precedence

OpenMAS loads configuration from multiple sources in the following order (from lowest to highest precedence):

1. **SDK Internal Defaults**: Default values defined in the Pydantic models (e.g., `AgentConfig`).
2. **Project Configuration (`openmas_project.yml`)**: Values in the `default_config` section of the project configuration file.
3. **Default Configuration File (`config/default.yml`)**: Settings shared by all environments.
4. **Environment-Specific Configuration (`config/<OPENMAS_ENV>.yml`)**: Settings specific to the current environment.
5. **Environment Variables**: The highest precedence, overriding all other sources.

This layered approach allows you to define sane defaults, environment-specific configurations, and easily override settings for testing or deployment without modifying code.

## Configuration Files

### Project Configuration (`openmas_project.yml`)

The central project configuration file, located at the root of your project:

```yaml
name: "my_mas_project"
version: "0.1.0"
agents:
  orchestrator: "agents/orchestrator"
  worker: "agents/worker"
# Define paths for code shared between agents in this project
shared_paths:
  - "shared"
# Define paths for project-local framework extensions (e.g., custom communicators)
extension_paths:
  - "extensions"
default_config:
  log_level: "INFO"
  communicator_type: "http"
  communicator_options:
    timeout: 30
```

The `default_config` section provides base configuration values for all agents in the project. The `shared_paths` and `extension_paths` sections define locations where OpenMAS will look for project-specific shared code or framework extensions (like custom communicators).

### Agent Configuration with Prompts and Sampling

OpenMAS supports defining prompts and sampling parameters directly in the agent configuration.
These configurations can be specified in the `openmas_project.yml` file:

```yaml
agents:
  llm_analyst:
    module: "agents.llm_analyst"
    class: "LlmAnalystAgent"
    prompts_dir: "prompts"  # Directory relative to project root
    prompts:
      - name: "summarize_text"
        template_file: "summarize.txt"  # File in prompts_dir
        input_variables: ["text_to_summarize"]
      - name: "generate_greeting"
        template: "Hello, {{user_name}}! Welcome to {{service}}."
        input_variables: ["user_name", "service"]
    sampling:
      provider: "mcp"       # "mcp", "mock", or others supported
      model: "claude-3-opus-20240229"  # model identifier
      temperature: 0.7      # Controls randomness (0.0-1.0)
      max_tokens: 2000      # Maximum tokens in completion
      top_p: 0.9            # Nucleus sampling parameter
```

#### Prompt Configuration

The `prompts` field is a list of prompt configurations with these properties:

| Property | Description | Required |
|----------|-------------|----------|
| `name` | Unique name for the prompt | Yes |
| `template` | Inline template with variables in Handlebars syntax (`{{variable}}`) | One of `template` or `template_file` required |
| `template_file` | Path to template file (relative to `prompts_dir`) | One of `template` or `template_file` required |
| `input_variables` | List of variable names used in the template | No, but recommended for validation |

The `prompts_dir` field specifies the directory where template files are stored, relative to the project root. It defaults to `prompts` if not specified.

#### Sampling Configuration

The `sampling` field configures how the agent samples from language models:

| Property | Description | Default |
|----------|-------------|---------|
| `provider` | Sampling provider (e.g., "mcp", "mock") | None |
| `model` | Model name/identifier to use for sampling | None |
| `temperature` | Controls randomness (0.0-1.0) | 0.7 |
| `max_tokens` | Maximum tokens to generate | None |
| `top_p` | Nucleus sampling parameter (0.0-1.0) | None |
| `top_k` | Top-k sampling parameter | None |
| `stop_sequences` | List of strings that stop generation | None |
| `frequency_penalty` | Penalizes repeated tokens | None |
| `presence_penalty` | Penalizes repeated topics | None |
| `seed` | Seed for random sampling | None |

When using the `"mcp"` provider, the MCP communication protocol will be used to interact with language models. This requires an appropriate MCP communicator configuration.

### Environment Configuration Files

OpenMAS looks for YAML configuration files in the `config/` directory of your project:

1. **Default Configuration (`config/default.yml`)**: Shared settings for all environments:

```yaml
# config/default.yml
log_level: "INFO"
communicator_type: "http"
service_urls:
  chess-engine: "http://chess-engine:8000"
  vision: "http://vision-service:8001"
communicator_options:
  timeout: 30
  retries: 3
```

2. **Environment-Specific Configuration (`config/<env>.yml`)**: Settings for specific environments (development, staging, production):

```yaml
# config/production.yml
log_level: "WARNING"
service_urls:
  chess-engine: "http://prod-chess-engine.internal:8000"
  vision: "http://prod-vision.internal:8001"
communicator_options:
  timeout: 60
```

To use environment-specific configuration, set the `OPENMAS_ENV` environment variable (defaults to `local` if not set):

```bash
export OPENMAS_ENV=production
```

## Using Environment Variables

Environment variables have the highest precedence and can override any configuration value:

### Standard Configuration Variables

- `AGENT_NAME`: Name of the agent
- `LOG_LEVEL`: Logging level (e.g., "DEBUG", "INFO", "WARNING")
- `COMMUNICATOR_TYPE`: Type of communicator to use (e.g., "http", "mcp_sse", "mcp_stdio")

### Configuring Service URLs

There are two ways to configure service URLs (the external services your agent connects to):

1. **JSON Dictionary** (all services at once):

```bash
export SERVICE_URLS='{"chess-engine": "http://localhost:8000", "vision": "http://localhost:8001"}'
```

2. **Individual Service URLs** (one service at a time):

```bash
export SERVICE_URL_CHESS_ENGINE="http://localhost:8000"
export SERVICE_URL_VISION="http://localhost:8001"
```

### Communicator Options

Similarly, communicator options can be set in two ways:

1. **JSON Dictionary**:

```bash
export COMMUNICATOR_OPTIONS='{"timeout": 60, "retries": 5}'
```

2. **Individual Options**:

```bash
export COMMUNICATOR_OPTION_TIMEOUT=60
export COMMUNICATOR_OPTION_RETRIES=5
```

## Plugin Configuration

In the `openmas_project.yml` file, you can specify paths to plugin directories:

```yaml
plugin_paths:
  - "plugins/communicators"
  - "plugins/agents"
```

OpenMAS will automatically discover and load plugins from these directories. For custom communicators, they will be available for use by specifying the communicator type in your configuration.

## Configuration in Code

In your agent code, use the `load_config` function along with a Pydantic model (typically `AgentConfig` or a subclass) to load and validate configuration:

```python
from openmas.config import load_config, AgentConfig
from pydantic import Field

# Load standard agent configuration using the base AgentConfig model
config: AgentConfig = load_config(AgentConfig)

# --- Or define and load a custom configuration model ---

class MyLLMAgentConfig(AgentConfig):
    """Custom configuration including LLM settings."""
    llm_api_key: str = Field(..., description="API key for external LLM service")
    llm_model_name: str = Field("gpt-4o", description="Model name to use")

# Load configuration using your custom model
my_config: MyLLMAgentConfig = load_config(MyLLMAgentConfig)

# Access validated config values later in your agent:
# api_key = my_config.llm_api_key
# agent_name = my_config.name
```

The `load_config` function handles the layering logic, environment variable parsing, and Pydantic validation, providing a type-safe configuration object.

## Common Configuration Patterns

### Best Practices

1. **Use YAML for Static Configuration**: Put relatively static configuration in YAML files.
2. **Use Environment Variables for Dynamic or Sensitive Configuration**: Use environment variables for values that change between deployments or for secrets.
3. **External Service Configuration**: Define service URLs in your YAML configuration files, and override for local development or specific deployments using environment variables.

### External Service Configuration Examples

For configuring external services, typically in a containerized environment:

**config/default.yml**:
```yaml
service_urls:
  database: "postgresql://postgres:5432/mydb"
  cache: "redis://redis:6379/0"
  mcp-server: "http://mcp-server:8080/v1"
```

**config/local.yml**:
```yaml
service_urls:
  database: "postgresql://localhost:5432/mydb"
  cache: "redis://localhost:6379/0"
  mcp-server: "http://localhost:8080/v1"
```

In your Dockerfile or docker-compose environment:
```bash
OPENMAS_ENV=production
SERVICE_URL_MCP_SERVER=http://production-mcp.internal:8080/v1
```

## Debugging Configuration

If you're having trouble with configuration, you can enable DEBUG logging to see where values are coming from:

```bash
export LOG_LEVEL=DEBUG
```

This will show detailed logs about configuration loading, including which files are being read and what values are being applied from each source.

## Configuration Keys Reference

Here are the commonly used configuration keys in OpenMAS:

| Key | Description | Default |
| --- | --- | --- |
| `name` | Agent name | `"agent"` |
| `log_level` | Logging level | `"INFO"` |
| `communicator_type` | Type of communicator | `"http"` |
| `service_urls` | Dictionary of service URLs | `{}` |
| `communicator_options` | Dictionary of options for the communicator | `{}` |
| `plugin_paths` | List of paths to look for plugins | `[]` |
| `extension_paths` | List of paths to look for local framework extensions | `[]` |

For communicator-specific options, refer to the [Communication Guide](communication/index.md).
