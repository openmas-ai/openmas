# Sampling Configuration

This guide explains how to configure and use OpenMAS's sampling capabilities, which provide a consistent interface for generating text from language models.

## Introduction

Sampling refers to the process of generating text from language models. OpenMAS provides a flexible sampling system that:

- Offers a consistent API across different language model providers
- Supports configuring sampling parameters in project files
- Integrates with MCP (Model Context Protocol) for enhanced functionality
- Enables testing with mock samplers

## Sampling Parameters

Sampling parameters control how text is generated from language models. The following parameters are supported:

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `provider` | The sampling provider to use (e.g., "mcp", "mock") | None | - |
| `model` | The model to use for sampling | None | Provider-specific |
| `temperature` | Controls randomness - higher values produce more diverse outputs | 0.7 | 0.0-1.0 |
| `max_tokens` | Maximum number of tokens to generate | None | Positive integer |
| `top_p` | Nucleus sampling parameter - limits token selection to a cumulative probability | None | 0.0-1.0 |
| `top_k` | Limits token selection to top k options | None | Positive integer |
| `stop_sequences` | List of strings that stop generation when encountered | None | List of strings |
| `frequency_penalty` | Penalizes repeated tokens | None | Provider-specific |
| `presence_penalty` | Penalizes repeated topics | None | Provider-specific |
| `seed` | Random seed for reproducible outputs | None | Integer |

Note that not all parameters are supported by all providers, and some providers may have additional parameters not listed here.

## Configuring Sampling in Project Files

The simplest way to configure sampling is through the `openmas_project.yml` file:

```yaml
agents:
  llm_agent:
    module: "agents.llm_agent"
    class: "LlmAgent"
    sampling:
      provider: "mcp"
      model: "claude-3-opus-20240229"
      temperature: 0.5
      max_tokens: 2000
      top_p: 0.9
```

This configuration creates a sampler that:
- Uses the MCP provider
- Uses the Claude 3 Opus model
- Has a temperature of 0.5 (more deterministic than the default)
- Generates at most 2000 tokens
- Uses nucleus sampling with top_p of 0.9

## Sampling Providers

OpenMAS supports multiple sampling providers:

### MCP Provider

The MCP provider uses the Model Context Protocol to interact with language models:

```yaml
sampling:
  provider: "mcp"
  model: "claude-3-opus-20240229"
  temperature: 0.7
```

When using the MCP provider, your agent must use an MCP-compatible communicator:

```yaml
communicator_type: "mcp_sse"  # or "mcp_stdio"
communicator_options:
  server_mode: false
```

### Mock Provider

For testing and development, you can use the mock provider:

```yaml
sampling:
  provider: "mock"
  model: "test-model"
```

The mock provider logs sampling requests but returns a fixed response without calling an actual language model.

## Using a Sampler in Code

### Accessing the Sampler in an Agent

If you configure sampling in your project file, the agent will automatically create a sampler for you:

```python
from openmas.agent import BaseAgent
from openmas.sampling import SamplingParameters

class MyAgent(BaseAgent):
    async def setup(self):
        # Setup is called automatically when the agent starts
        # No need to create a sampler manually if configured in project file
        if self.config.sampling:
            # Access the sampler parameters from config
            params = SamplingParameters(**self.config.sampling.model_dump(exclude_none=True))
            self.sampler = get_sampler(params=params)
        else:
            # Create a default sampler if not configured
            self.sampler = get_sampler(SamplingParameters())
```

### Sampling from the Sampler

To sample from a language model:

```python
async def process_message(self, message):
    # Create a sampling context
    context = self.sampler.create_context(
        system="You are a helpful assistant.",
        messages=[
            {"role": "user", "content": message}
        ],
        parameters={
            "temperature": 0.5,
            "max_tokens": 1000
        }
    )

    # Sample from the language model
    result = await self.sampler.sample(context)

    # Use the result
    return result.content
```

### Using Sampling with Prompts

You can also sample directly from a prompt:

```python
# Get a prompt from the prompt manager
prompt = await self.prompt_manager.get_prompt("analyze_text")

# Sample from the prompt
result = await self.sampler.sample_from_prompt(
    prompt=prompt,
    context_vars={"text": input_text, "analysis_depth": "deep"},
    parameters={"temperature": 0.3}  # Override default parameters
)
```

## Working with MCP Samplers

The MCP sampler integrates with the MCP protocol to provide enhanced functionality.

### MCP-Specific Configuration

When using the MCP provider, you need to:

1. Configure your agent to use an MCP communicator
2. Specify the target service for language model requests

```yaml
agents:
  mcp_agent:
    module: "agents.mcp_agent"
    class: "McpAgent"
    communicator_type: "mcp_sse"
    communicator_options:
      server_mode: false
    service_urls:
      llm_service: "http://localhost:8080/v1"
    sampling:
      provider: "mcp"
      model: "claude-3-opus-20240229"
```

### Using the `PromptMcpAgent`

For convenience, OpenMAS provides a `PromptMcpAgent` class that combines prompt management and sampling capabilities:

```python
from openmas.agent import PromptMcpAgent

# Create the agent
agent = PromptMcpAgent(
    name="analyzer",
    llm_service="llm_service",  # Service name defined in service_urls
    default_model="claude-3-opus-20240229"
)

# Setup the agent
await agent.setup()

# Create a prompt
prompt_id = await agent.create_prompt(
    name="analyze",
    system="You are an analytical assistant.",
    template="Please analyze the following text: {{text}}"
)

# Sample using the prompt
result = await agent.sample(
    prompt_id=prompt_id,
    context={"text": input_text},
    parameters={"temperature": 0.5}
)
```

## Best Practices

1. **Define Sampling Parameters in Project Files**: This makes it easy to adjust parameters without changing code.

2. **Use Different Temperatures for Different Tasks**:
   - Lower temperatures (0.0-0.5) for factual or structured output
   - Medium temperatures (0.5-0.8) for creative but controlled text
   - Higher temperatures (0.8-1.0) for more creative or exploratory outputs

3. **Set Appropriate Max Tokens**: Estimate the maximum length of the expected response and add a safety margin.

4. **Use Stop Sequences Wisely**: Define stop sequences to prevent the model from continuing beyond the needed response.

5. **Consider Using Seeds for Reproducibility**: When testing or when deterministic outputs are required, set a seed value.

6. **Mock for Testing**: Use the mock provider during testing to avoid calling actual language models.
