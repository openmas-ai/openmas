# LLM Integration

This document outlines patterns for integrating Large Language Models (LLMs) such as OpenAI, Anthropic, and Google Gemini into OpenMAS agents.

## Recommended Pattern

The recommended approach for integrating LLMs is to use the standard configuration system and initialize the LLM clients directly in the agent's `setup()` method.

### 1. Configure API Keys via Environment Variables

Set up environment variables for your LLM service:

```bash
# OpenAI
export OPENAI_API_KEY=your_openai_api_key
export OPENAI_MODEL_NAME=gpt-4

# Anthropic
export ANTHROPIC_API_KEY=your_anthropic_api_key
export ANTHROPIC_MODEL_NAME=claude-3-opus-20240229

# Google
export GOOGLE_API_KEY=your_google_api_key
export GOOGLE_MODEL_NAME=gemini-pro
```

These will be loaded into your agent's configuration through the standard `AgentConfig` system.

### 2. Initialize the LLM Client in the Agent's setup() Method

```python
import asyncio
from typing import Optional

from openmas.agent.base import BaseAgent
from openmas.config import AgentConfig


class LLMAgent(BaseAgent):
    """Agent that uses an LLM for reasoning."""

    async def setup(self) -> None:
        """Set up the agent by initializing the LLM client."""
        # For OpenAI
        try:
            import openai

            # Configure from environment or agent config
            api_key = os.environ.get("OPENAI_API_KEY")
            self.model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4")

            # Initialize the client
            self.client = openai.OpenAI(api_key=api_key)
            self.logger.info("OpenAI client initialized", model=self.model_name)
        except ImportError:
            self.logger.error("OpenAI package not installed. Install with: pip install openai")
            raise

    async def get_llm_response(self, prompt: str) -> str:
        """Get a response from the LLM."""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are an intelligent agent in a multi-agent system."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    async def run(self) -> None:
        """Run the agent's main loop."""
        while True:
            # ... agent logic
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        """Clean up resources."""
        # Some LLM clients might need cleanup
        pass
```

### 3. Using Different LLM Providers

#### OpenAI

```python
async def setup(self) -> None:
    """Set up the agent by initializing OpenAI."""
    try:
        import openai

        api_key = os.environ.get("OPENAI_API_KEY")
        self.model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4")

        self.client = openai.OpenAI(api_key=api_key)
        self.logger.info("OpenAI client initialized", model=self.model_name)
    except ImportError:
        self.logger.error("OpenAI package not installed. Install with: pip install openai")
        raise

async def get_llm_response(self, prompt: str) -> str:
    """Get a response from OpenAI."""
    response = self.client.chat.completions.create(
        model=self.model_name,
        messages=[
            {"role": "system", "content": "You are an intelligent agent in a multi-agent system."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
```

#### Anthropic

```python
async def setup(self) -> None:
    """Set up the agent by initializing Anthropic."""
    try:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.model_name = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.logger.info("Anthropic client initialized", model=self.model_name)
    except ImportError:
        self.logger.error("Anthropic package not installed. Install with: pip install anthropic")
        raise

async def get_llm_response(self, prompt: str) -> str:
    """Get a response from Anthropic."""
    message = self.client.messages.create(
        model=self.model_name,
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return message.content[0].text
```

#### Google Gemini

```python
async def setup(self) -> None:
    """Set up the agent by initializing Google Gemini."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        self.model_name = os.environ.get("GOOGLE_MODEL_NAME", "gemini-pro")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)
        self.logger.info("Google Gemini model initialized", model=self.model_name)
    except ImportError:
        self.logger.error("Google generativeai package not installed. Install with: pip install google-generativeai")
        raise

async def get_llm_response(self, prompt: str) -> str:
    """Get a response from Google Gemini."""
    response = self.model.generate_content(prompt)
    return response.text
```

## Best Practices

1. **Environment Variables**: Always load API keys from environment variables or secure configuration rather than hardcoding them.

2. **Error Handling**: Implement appropriate error handling for API rate limits, errors, and timeouts.

3. **Async Support**: Most LLM clients support async operations. Use them to keep your agent responsive.

4. **Dependency Management**: Include the LLM client packages in your project's optional dependencies.

5. **Prompting Strategies**: Develop clear prompting strategies with system messages that define the agent's role and context.

## Extending Agent Configuration

You can extend the base `AgentConfig` to include LLM-specific configuration:

```python
from pydantic import Field
from openmas.config import AgentConfig

class LLMAgentConfig(AgentConfig):
    """Configuration for an LLM-powered agent."""

    llm_provider: str = Field("openai", description="The LLM provider to use (openai, anthropic, google)")
    llm_model: str = Field("gpt-4", description="The model name to use")
    llm_temperature: float = Field(0.7, description="Temperature setting for LLM responses")
    llm_max_tokens: int = Field(1000, description="Maximum number of tokens in responses")
```

Then use this extended configuration in your agent:

```python
class MyLLMAgent(BaseAgent):
    def __init__(self, name=None, config=None):
        super().__init__(name, config, config_model=LLMAgentConfig)

    async def setup(self) -> None:
        # Access LLM-specific config
        provider = self.config.llm_provider
        model = self.config.llm_model
        temperature = self.config.llm_temperature

        # Initialize appropriate client based on provider
        # ...
```
