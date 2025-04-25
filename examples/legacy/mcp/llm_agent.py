#!/usr/bin/env python3
"""
LLM Agent with MCP Example.

This example demonstrates how to create an agent that uses an LLM via MCP
for natural language interactions. It shows how to:
1. Connect to an MCP server
2. Send prompts to an LLM model
3. Process responses in an agent-based system

To run:
$ poetry run python examples/mcp/llm_agent.py

Requirements:
- Anthropic API key: set ANTHROPIC_API_KEY environment variable
- MCP server: can run locally with `poetry run mcp-server`
"""

import asyncio
import logging
import os
import sys

from mcp.client.session import ClientSession
from mcp.types import TextContent

from openmas.agent import Agent
from openmas.communication import Message
from openmas.config import AgentConfig, CommunicatorConfig


class LLMAgent(Agent):
    """An agent that uses an LLM via MCP for natural language processing.

    This agent can:
    1. Receive questions from other agents
    2. Process them with an LLM
    3. Return the responses
    """

    async def setup(self) -> None:
        """Set up the agent and initialize MCP client session."""
        await super().setup()

        # Initialize state
        self.questions_answered = 0
        self.mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8000")
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not self.anthropic_api_key:
            logging.warning("ANTHROPIC_API_KEY not set. LLM functionality will not work!")

        # Create MCP client session
        self.mcp_client = ClientSession(api_key=self.anthropic_api_key, base_url=self.mcp_server_url)

        # Register message handlers
        await self.communicator.register_handler("question", self.handle_question)
        logging.info(f"LLM Agent {self.name} initialized and ready")

    async def cleanup(self) -> None:
        """Clean up resources before agent shutdown."""
        if hasattr(self, "mcp_client"):
            await self.mcp_client.aclose()
        await super().cleanup()

    async def handle_question(self, message: Message) -> None:
        """Handle a question message by querying the LLM.

        Args:
            message: The message containing a question to answer
        """
        question = message.content.get("question", "")
        if not question:
            logging.warning(f"Received empty question from {message.sender_id}")
            return

        logging.info(f"Received question from {message.sender_id}: {question}")

        # Process with LLM
        try:
            answer = await self.query_llm(question)
            self.questions_answered += 1

            # Send response back
            await self._send_answer(message.sender_id, question, answer)

        except Exception as e:
            logging.error(f"Error querying LLM: {e}")
            # Send error response
            await self._send_answer(message.sender_id, question, f"Sorry, I encountered an error: {str(e)}")

    async def query_llm(self, question: str) -> str:
        """Query the LLM with a question using MCP.

        Args:
            question: The question to ask the LLM

        Returns:
            The LLM's response
        """
        if not self.anthropic_api_key:
            return "Error: ANTHROPIC_API_KEY not set. Cannot query LLM."

        # Create a system prompt
        system_prompt = """
        You are a helpful assistant integrated into a multi-agent system.
        Answer questions concisely and accurately.
        If you don't know something, admit it rather than making up information.
        """

        # Send the query to the LLM via MCP
        response = await self.mcp_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )

        # Extract the response text
        for content in response.content:
            if isinstance(content, TextContent):
                return content.text

        return "Error: Could not extract response from LLM"

    async def _send_answer(self, recipient_id: str, question: str, answer: str) -> None:
        """Send an answer back to the agent who asked the question.

        Args:
            recipient_id: ID of the agent who asked the question
            question: The original question
            answer: The LLM's answer
        """
        response_content = {"original_question": question, "answer": answer, "question_number": self.questions_answered}

        # Create and send the message
        response_message = Message(
            sender_id=self.id, recipient_id=recipient_id, content=response_content, message_type="answer"
        )

        await self.communicator.send_message(response_message)
        logging.info(f"Sent answer to {recipient_id}")


class UserAgent(Agent):
    """An agent that simulates a user asking questions to the LLM agent."""

    async def setup(self) -> None:
        """Set up the agent."""
        await super().setup()
        self.questions = [
            "What is a multi-agent system?",
            "How can LLMs be integrated into agent-based systems?",
            "What are some challenges in multi-agent communication?",
            "Explain the concept of emergence in complex systems",
            "How do agents share knowledge in a distributed system?",
        ]
        self.current_question = 0
        self.answers_received = 0

        # Register message handler for answers
        await self.communicator.register_handler("answer", self.handle_answer)
        logging.info(f"User Agent {self.name} initialized with {len(self.questions)} questions")

    async def run(self) -> None:
        """Run the agent's main loop to ask questions."""
        logging.info(f"User Agent {self.name} starting to ask questions")

        try:
            # Ask each question with a delay between them
            while self.current_question < len(self.questions):
                if hasattr(self, "llm_agent_id") and self.llm_agent_id:
                    await self._ask_question(self.questions[self.current_question])
                    self.current_question += 1

                # Wait for the answer before asking the next question
                await asyncio.sleep(5)

            # Wait for any remaining answers
            logging.info("Finished asking all questions, waiting for remaining answers...")
            await asyncio.sleep(10)

            logging.info(f"Questions asked: {self.current_question}")
            logging.info(f"Answers received: {self.answers_received}")

        except asyncio.CancelledError:
            logging.info(f"User Agent {self.name} run task was cancelled")
            raise

    async def _ask_question(self, question: str) -> None:
        """Ask a question to the LLM agent.

        Args:
            question: The question to ask
        """
        question_content = {"question": question, "question_number": self.current_question + 1}

        # Create and send the message
        question_message = Message(
            sender_id=self.id, recipient_id=self.llm_agent_id, content=question_content, message_type="question"
        )

        await self.communicator.send_message(question_message)
        logging.info(f"Asked question {self.current_question + 1}: {question}")

    async def handle_answer(self, message: Message) -> None:
        """Handle an answer message from the LLM agent.

        Args:
            message: The answer message
        """
        original_question = message.content.get("original_question", "")
        answer = message.content.get("answer", "")

        self.answers_received += 1

        logging.info(f"\n----- Answer Received from {message.sender_id} -----")
        logging.info(f"Question: {original_question}")
        logging.info(f"Answer: {answer}")
        logging.info("-" * 50)


async def main() -> None:
    """Run the LLM agent example."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout
    )

    # Get the MCP server URL
    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8000")
    logging.info(f"Using MCP server at: {mcp_server_url}")

    # Check for Anthropic API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logging.warning(
            "ANTHROPIC_API_KEY environment variable not set. "
            "The LLM agent will run but won't be able to query Claude."
        )

    # Create communicator config with MCP server URL
    mcp_config = CommunicatorConfig(communicator_type="mcp", service_urls={"mcp_server": mcp_server_url})

    # Create agent configurations
    llm_agent_config = AgentConfig(name="llm_assistant", log_level="INFO", communicator_config=mcp_config)

    user_agent_config = AgentConfig(name="user", log_level="INFO", communicator_config=mcp_config)

    # Create agent instances
    llm_agent = LLMAgent(config=llm_agent_config)
    user_agent = UserAgent(config=user_agent_config)

    # Set the LLM agent ID in the user agent
    user_agent.llm_agent_id = llm_agent.id

    try:
        # Start both agents
        logging.info("Starting agents...")
        await asyncio.gather(llm_agent.start(), user_agent.start())

        # Let the agents run to completion of their tasks
        await asyncio.sleep(60)  # Adjust this timeout based on expected interaction time

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received")

    finally:
        # Ensure both agents are properly shut down
        logging.info("Shutting down agents...")
        await asyncio.gather(llm_agent.stop(), user_agent.stop())
        logging.info("Example complete")


if __name__ == "__main__":
    asyncio.run(main())
