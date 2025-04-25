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
shared_paths:
  - "shared"
extension_paths:
  - "extensions/custom_communicators"
default_config:
  log_level: "INFO"
  communicator_type: "http"
  communicator_options:
    timeout: 30
```

The `default_config` section provides base configuration values for all agents in the project.

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

To use environment-specific configuration, set the `OPENMAS_ENV` environment variable:

```bash
export OPENMAS_ENV=production
```

## Using Environment Variables

Environment variables have the highest precedence and can override any configuration value:

### Standard Configuration Variables

- `AGENT_NAME`: Name of the agent
- `LOG_LEVEL`: Logging level (e.g., "DEBUG", "INFO", "WARNING")
- `COMMUNICATOR_TYPE`: Type of communicator to use (e.g., "http", "mcp_stdio")

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

## Configuration in Code

In your agent code, use the `load_config` function to load and validate configuration:

```python
from openmas.config import load_config, AgentConfig

# Load standard agent configuration
config = load_config(AgentConfig)

# Or extend AgentConfig for custom settings
from pydantic import Field

class MyAgentConfig(AgentConfig):
    api_key: str = Field(..., description="API key for external service")
    model_name: str = Field("gpt-4", description="Model name to use")

config = load_config(MyAgentConfig)
```

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
