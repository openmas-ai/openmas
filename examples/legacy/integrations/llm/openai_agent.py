#!/usr/bin/env python
"""Example agent using OpenAI for reasoning.

This example demonstrates how to integrate OpenAI's LLM into a SimpleMAS agent
for reasoning capabilities.

To run:
    export OPENAI_API_KEY=your_openai_api_key
    export OPENAI_MODEL_NAME=gpt-4  # optional, defaults to gpt-4
    python examples/integrations/llm/openai_agent.py
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from pydantic import Field

from simple_mas.agent.base import BaseAgent
from simple_mas.config import AgentConfig


class OpenAIAgentConfig(AgentConfig):
    """Configuration for the OpenAI-powered agent."""

    openai_model: str = Field("gpt-4", description="OpenAI model to use")
    system_prompt: str = Field(
        "You are an intelligent agent that provides helpful, concise responses.",
        description="System prompt to use for OpenAI",
    )


class OpenAIAgent(BaseAgent):
    """Example agent that uses OpenAI for reasoning."""

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the OpenAI agent."""
        super().__init__(name=name, config=config, config_model=OpenAIAgentConfig)
        self.openai_client = None
        self.model = self.config.openai_model  # type: ignore

    async def setup(self) -> None:
        """Set up the agent by initializing the OpenAI client."""
        # Import OpenAI here to avoid hard dependency
        try:
            import openai

            # Get API key from environment
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable must be set to use this agent.")

            # Create the client
            self.openai_client = openai.OpenAI(api_key=api_key)
            self.logger.info("OpenAI client initialized", model=self.model)

        except ImportError:
            self.logger.error("OpenAI package not installed. Install with: pip install openai")
            raise

    async def get_openai_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from OpenAI.

        Args:
            messages: List of message dictionaries, each with 'role' and 'content'

        Returns:
            The text response from the model
        """
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized. Call setup() first.")

        self.logger.debug("Sending request to OpenAI", messages=messages)
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content

    async def ask_question(self, question: str) -> str:
        """Ask a question to the OpenAI model.

        Args:
            question: The question to ask

        Returns:
            The model's response
        """
        messages = [
            {"role": "system", "content": self.config.system_prompt},  # type: ignore
            {"role": "user", "content": question},
        ]
        return await self.get_openai_response(messages)

    async def run(self) -> None:
        """Run the agent's main loop."""
        # Example questions
        questions = [
            "What is the capital of France?",
            "Explain the concept of multi-agent systems in one paragraph.",
            "How might LLMs be used to enhance agent reasoning capabilities?",
        ]

        self.logger.info("OpenAI Agent started, asking example questions...")

        for question in questions:
            self.logger.info(f"Question: {question}")
            try:
                answer = await self.ask_question(question)
                self.logger.info(f"Answer: {answer}")
            except Exception as e:
                self.logger.error(f"Error getting response: {e}")

            # Pause to avoid rate limiting
            await asyncio.sleep(2)

        self.logger.info("Examples complete, shutting down...")

    async def shutdown(self) -> None:
        """Clean up resources."""
        self.logger.info("OpenAI agent shutting down")


async def main():
    """Run the example."""
    # Configure from environment variables
    model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4")

    # Create and start the agent
    agent = OpenAIAgent(
        name="openai-agent",
        config={
            "openai_model": model_name,
            "system_prompt": "You are an intelligent agent that provides helpful, concise responses.",
        },
    )

    try:
        await agent.start()
    except KeyboardInterrupt:
        pass
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
