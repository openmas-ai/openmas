# Integrating Large Language Models (LLMs)

OpenMAS agents can easily integrate with various Large Language Models (LLMs) like OpenAI's GPT, Anthropic's Claude, or Google's Gemini to add sophisticated reasoning capabilities.

The recommended approach is straightforward: initialize the official LLM client library (e.g., `openai`, `anthropic`, `google-generativeai`) directly within your agent's `setup()` method, using configuration loaded via OpenMAS's standard mechanisms.

This pattern offers several advantages:
*   **Simplicity:** Leverages the official, feature-rich SDKs provided by the LLM vendors.
*   **Direct Control:** Gives you full control over model parameters, error handling, and interaction logic.
*   **Standard Configuration:** Uses OpenMAS's environment variable and configuration file loading for API keys and model names.
*   **No Extra Abstraction:** Avoids adding unnecessary abstraction layers over the LLM clients.

## Steps

### 1. Install the LLM Client Library

Ensure you have the necessary Python package for your chosen LLM installed in your project's environment:

```bash
# Example for OpenAI
pip install openai
# poetry add openai

# Example for Anthropic
pip install anthropic
# poetry add anthropic

# Example for Google
pip install google-generativeai
# poetry add google-generativeai
```

### 2. Configure API Keys and Model Names

Set environment variables for your LLM service. OpenMAS configuration will automatically pick these up if you map them in your agent's config or access them directly.

```bash
export OPENAI_API_KEY="your_openai_api_key"
export OPENAI_MODEL_NAME="gpt-4o" # Or your preferred model

export ANTHROPIC_API_KEY="your_anthropic_api_key"
export ANTHROPIC_MODEL_NAME="claude-3-opus-20240229"

export GOOGLE_API_KEY="your_google_api_key"
export GOOGLE_MODEL_NAME="gemini-1.5-pro-latest"
```

### 3. Initialize the Client in `setup()`

In your agent's code (subclassing `BaseAgent`), import the LLM library and initialize its client within the `setup` method.

```python
import asyncio
import os
from openmas.agent import BaseAgent
# Assuming you might use a custom config, or access os.environ directly
# from openmas.config import AgentConfig

# --- Example using OpenAI ---
class OpenAIAgent(BaseAgent):
    """Agent that uses OpenAI for reasoning."""

    async def setup(self) -> None:
        """Set up the agent by initializing the OpenAI client."""
        try:
            import openai
            self.logger.info("Initializing OpenAI client...")
            # Load API key from environment variable
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.logger.error("OPENAI_API_KEY environment variable not set.")
                raise ValueError("Missing OpenAI API Key")

            # Get model name from environment or use a default
            self.model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")

            # Use the official OpenAI async client
            self.aclient = openai.AsyncOpenAI(api_key=api_key)
            self.logger.info("OpenAI client initialized.", model=self.model_name)

        except ImportError:
            self.logger.error("OpenAI package not installed. Run: pip install openai")
            raise
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    async def get_llm_response(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        """Get a response from the initialized OpenAI LLM."""
        if not hasattr(self, 'aclient'):
            raise RuntimeError("OpenAI client not initialized. Call setup() first.")

        try:
            response = await self.aclient.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            # Basic error check (you might want more robust handling)
            if response.choices:
                return response.choices[0].message.content
            else:
                self.logger.warning("LLM response had no choices.")
                return ""
        except Exception as e:
            self.logger.error(f"Error getting LLM response: {e}")
            # Decide how to handle errors - raise, return default, etc.
            raise

    async def run(self) -> None:
        """Example run loop using the LLM."""
        self.logger.info("LLM Agent running...")
        try:
            response = await self.get_llm_response("What is the capital of France?")
            self.logger.info(f"LLM Response: {response}")
        except Exception as e:
            self.logger.error(f"Failed during run loop: {e}")

        # Keep agent alive or perform other tasks
        await asyncio.sleep(3600)

    async def shutdown(self) -> None:
        """Clean up resources."""
        self.logger.info("Shutting down LLM agent.")
        if hasattr(self, 'aclient'):
             # Use await for the async client's close method if available
             # await self.aclient.close() # Check specific SDK docs for cleanup
             pass
        await super().shutdown()

# --- Example using Anthropic ---
# (Similar structure: import, init in setup, use client method)
# Remember to use the official async client: anthropic.AsyncAnthropic

# --- Example using Google Gemini ---
# (Similar structure: import, configure/init model in setup, use model method)
# Ensure you use async methods if available in the google-generativeai library

```

### 4. Use the Client in Agent Logic

Call the methods of the initialized LLM client (like `aclient.chat.completions.create` for OpenAI) within your agent's `run` loop or request handlers to generate responses based on prompts.

## Best Practices

*   **Use Async Clients:** Always use the asynchronous versions of the LLM client libraries (e.g., `openai.AsyncOpenAI`, `anthropic.AsyncAnthropic`) to avoid blocking your agent's event loop.
*   **Configuration:** Load API keys and model names securely from environment variables or configuration files managed by OpenMAS.
*   **Error Handling:** Implement robust error handling for API calls, considering network issues, rate limits, and invalid responses.
*   **Resource Management:** Ensure any necessary client cleanup is performed in the agent's `shutdown` method (refer to the specific LLM SDK documentation).
*   **Prompt Engineering:** Develop clear and effective prompts, potentially using system messages to provide context about the agent's role and goals.
*   **Dependency Management:** Add the required LLM client library to your project's dependencies (e.g., in `pyproject.toml` or `requirements.txt`).

*(See the specific documentation for the OpenAI, Anthropic, or Google Generative AI Python libraries for detailed API usage.)*
