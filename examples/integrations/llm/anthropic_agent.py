#!/usr/bin/env python
"""Example agent using Anthropic for reasoning.

This example demonstrates how to integrate Anthropic's Claude LLM into a SimpleMAS agent
for reasoning capabilities, using the helper functions from simple_mas.integrations.llm.

To run:
    export ANTHROPIC_API_KEY=your_anthropic_api_key
    export ANTHROPIC_MODEL_NAME=claude-3-opus-20240229  # optional
    python examples/integrations/llm/anthropic_agent.py
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from pydantic import Field

from simple_mas.agent.base import BaseAgent
from simple_mas.config import AgentConfig
from simple_mas.integrations.llm import initialize_anthropic_client


class AnthropicAgentConfig(AgentConfig):
    """Configuration for the Anthropic-powered agent."""

    anthropic_model: str = Field("claude-3-opus-20240229", description="Anthropic model to use")
    max_tokens: int = Field(1000, description="Maximum number of tokens in response")
    system_prompt: str = Field(
        "You are an intelligent agent that provides helpful, concise responses.",
        description="System prompt to use for Anthropic",
    )


class AnthropicAgent(BaseAgent):
    """Example agent that uses Anthropic for reasoning."""

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the Anthropic agent."""
        super().__init__(name=name, config=config, config_model=AnthropicAgentConfig)
        self.anthropic_client = None
        self.model = self.config.anthropic_model  # type: ignore
        self.max_tokens = self.config.max_tokens  # type: ignore

    async def setup(self) -> None:
        """Set up the agent by initializing the Anthropic client."""
        try:
            # Use the helper function from simple_mas.integrations.llm
            self.anthropic_client = initialize_anthropic_client(model=self.model)
            self.logger.info("Anthropic client initialized", model=self.model)

        except (ImportError, ValueError) as e:
            self.logger.error(f"Failed to initialize Anthropic client: {e}")
            raise

    async def get_anthropic_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from Anthropic.

        Args:
            messages: List of message dictionaries, each with 'role' and 'content'

        Returns:
            The text response from the model
        """
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized. Call setup() first.")

        self.logger.debug("Sending request to Anthropic", messages=messages)
        system_prompt = None

        # Extract system prompt if present
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append(msg)

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=user_messages,
        )

        return response.content[0].text

    async def ask_question(self, question: str) -> str:
        """Ask a question to the Anthropic model.

        Args:
            question: The question to ask

        Returns:
            The model's response
        """
        messages = [
            {"role": "system", "content": self.config.system_prompt},  # type: ignore
            {"role": "user", "content": question},
        ]
        return await self.get_anthropic_response(messages)

    async def run(self) -> None:
        """Run the agent's main loop."""
        # Example questions
        questions = [
            "What is the capital of Japan?",
            "Explain the concept of multi-agent systems in one paragraph.",
            "What are the key differences between ChatGPT and Claude?",
        ]

        self.logger.info("Anthropic Agent started, asking example questions...")

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
        self.logger.info("Anthropic agent shutting down")


async def main():
    """Run the example."""
    # Configure from environment variables
    model_name = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")

    # Create and start the agent
    agent = AnthropicAgent(
        name="anthropic-agent",
        config={
            "anthropic_model": model_name,
            "max_tokens": 1000,
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
