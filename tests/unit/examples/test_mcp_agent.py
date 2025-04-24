#!/usr/bin/env python3
"""Unit tests for the MCP agent example."""

import asyncio
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Try to import MCP and the agent class to test
try:
    from mcp.types import TextContent

    from examples.integrations.mcp_agent import AssistantAgent

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

    # Define stub classes if MCP is not installed
    class TextContent:  # type: ignore
        """Stub class for TextContent when MCP is not installed."""

        def __init__(self, text: str, type: str = "text") -> None:
            self.text = text
            self.type = type

    class AssistantAgent:  # type: ignore
        """Stub class for AssistantAgent when MCP is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


from simple_mas.config import AgentConfig


@pytest.mark.skipif(not HAS_MCP, reason="MCP not installed")
class TestMcpAgent(unittest.TestCase):
    """Test cases for the MCP agent example."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = AgentConfig(
            name="test-agent",
            log_level="ERROR",
            service_urls={},
            communicator_type="in-memory",
        )

        # Create an instance of the agent with explicit name parameter
        self.agent = AssistantAgent(name="test-agent", config=self.config)

        # Create event loop for testing async functions
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up after tests."""
        self.loop.close()

    def test_agent_initialization(self):
        """Test that the agent initializes correctly."""
        self.assertEqual(self.agent.name, "test-agent")
        self.assertEqual(self.agent.config.log_level, "ERROR")

    def test_get_weather_tool(self):
        """Test the get_weather tool."""
        # Run the async method in the loop
        weather_data = self.loop.run_until_complete(self.agent.get_weather(location="New York", unit="celsius"))

        # Verify the result contains expected fields
        self.assertEqual(weather_data["location"], "New York")
        self.assertEqual(weather_data["temperature"], 22)
        self.assertEqual(weather_data["unit"], "celsius")
        self.assertEqual(weather_data["condition"], "sunny")
        self.assertIn("humidity", weather_data)
        self.assertIn("requested_at", weather_data)

        # Verify using fahrenheit
        weather_data = self.loop.run_until_complete(self.agent.get_weather(location="Boston", unit="fahrenheit"))
        self.assertEqual(weather_data["temperature"], 72)

    def test_calculate_tool(self):
        """Test the calculate tool with different operations."""
        # Test sum operation
        result = self.loop.run_until_complete(self.agent.calculate(operation="sum", numbers=[1, 2, 3, 4, 5]))
        self.assertEqual(result["result"], 15)

        # Test average operation
        result = self.loop.run_until_complete(self.agent.calculate(operation="average", numbers=[1, 2, 3, 4, 5]))
        self.assertEqual(result["result"], 3)

        # Test min operation
        result = self.loop.run_until_complete(self.agent.calculate(operation="min", numbers=[1, 2, 3, 4, 5]))
        self.assertEqual(result["result"], 1)

        # Test max operation
        result = self.loop.run_until_complete(self.agent.calculate(operation="max", numbers=[1, 2, 3, 4, 5]))
        self.assertEqual(result["result"], 5)

        # Test invalid operation
        result = self.loop.run_until_complete(self.agent.calculate(operation="invalid", numbers=[1, 2, 3]))
        self.assertIn("error", result)

    def test_get_agent_status_tool(self):
        """Test the get_agent_status tool."""
        # The agent should start with 0 requests
        status = self.loop.run_until_complete(self.agent.get_agent_status())
        self.assertEqual(status["name"], "test-agent")
        self.assertEqual(status["request_count"], 0)
        self.assertIsNone(status["last_request_time"])
        self.assertEqual(status["status"], "running")

        # Make a request to increment the counter
        self.loop.run_until_complete(self.agent.get_weather(location="London"))

        # Check the status again
        status = self.loop.run_until_complete(self.agent.get_agent_status())
        self.assertEqual(status["request_count"], 1)
        self.assertIsNotNone(status["last_request_time"])

    @pytest.mark.asyncio
    async def test_help_resource_async(self):
        """Test the help resource asynchronously."""
        help_data = await self.agent.help_resource()

        self.assertEqual(help_data["agent_name"], "test-agent")
        self.assertIn("description", help_data)
        self.assertIn("tools", help_data)
        self.assertIn("prompts", help_data)
        self.assertIn("resources", help_data)

        # Verify tools
        tools = help_data["tools"]
        tool_names = [tool["name"] for tool in tools]
        self.assertIn("get_weather", tool_names)
        self.assertIn("calculate", tool_names)
        self.assertIn("get_agent_status", tool_names)

        # Verify prompts
        prompts = help_data["prompts"]
        prompt_names = [prompt["name"] for prompt in prompts]
        self.assertIn("assistant", prompt_names)

    @patch("examples.integrations.mcp_agent.TextContent")
    def test_assistant_prompt(self, mock_text_content):
        """Test the assistant prompt."""
        # Configure the mock
        mock_instance = MagicMock()
        mock_text_content.return_value = mock_instance

        # Run the prompt
        self.loop.run_until_complete(self.agent.assistant_prompt(query="What is the weather?"))

        # Verify the TextContent was created with expected text
        mock_text_content.assert_called_once()
        call_args = mock_text_content.call_args[1]["text"]
        self.assertIn("What is the weather?", call_args)

        # Verify request count was incremented
        self.assertEqual(self.agent.request_count, 1)
        self.assertIsNotNone(self.agent.last_request_time)


if __name__ == "__main__":
    unittest.main()
