"""Integration tests for MCP Client Agent interaction with MCP Communicator.

This module tests the integration between McpClientAgent and McpSseCommunicator
in client mode, verifying that client methods properly delegate to the communicator.
"""

from typing import Any, Dict, List, Optional

import pytest

from openmas.agent import McpClientAgent
from openmas.testing.harness import AgentTestHarness


class MockMcpSseCommunicator:
    """Mock MCP SSE communicator for testing client mode delegation."""

    def __init__(self, agent_name: str, service_urls: Dict[str, str], server_mode: bool = False, **kwargs):
        """Initialize the mock communicator.

        Args:
            agent_name: The name of the agent
            service_urls: Dictionary of service URLs
            server_mode: Whether to run in server mode
            **kwargs: Additional configuration options
        """
        self.agent_name = agent_name
        self.service_urls = service_urls
        self.server_mode = server_mode

        # Track method calls
        self.call_tool_calls = []
        self.get_prompt_calls = []
        self.read_resource_calls = []
        self.list_tools_calls = []
        self.list_prompts_calls = []
        self.sample_prompt_calls = []

        # Define mocked responses
        self.mocked_tool_responses = {
            "add_numbers": {"result": 42},
            "process_data": {"status": "success", "processed": True},
        }

        self.mocked_prompt_responses = {
            "greeting": "Hello, Test User!",
            "summary": "This is a summary of the content.",
        }

        self.mocked_resource_data = {
            "/api/data": b'{"data": "test"}',
            "/images/logo.png": b"BINARY_IMAGE_DATA",
        }

        self.mocked_tools_list = [
            {"name": "add_numbers", "description": "Add two numbers"},
            {"name": "process_data", "description": "Process input data"},
        ]

        self.mocked_prompts_list = [
            {"name": "greeting", "description": "Generate a greeting"},
            {"name": "summary", "description": "Generate a summary"},
        ]

        self.mocked_sampling_responses = {"default": {"content": "Mocked sampling response"}}

    async def start(self) -> None:
        """Start the communicator."""
        pass

    async def stop(self) -> None:
        """Stop the communicator."""
        pass

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a remote service.

        Args:
            target_service: The target service
            tool_name: The tool name
            arguments: Tool arguments
            timeout: Optional timeout

        Returns:
            Tool result
        """
        self.call_tool_calls.append(
            {
                "target_service": target_service,
                "tool_name": tool_name,
                "arguments": arguments,
                "timeout": timeout,
            }
        )

        # Return a mocked response based on the tool name
        return self.mocked_tool_responses.get(tool_name, {"result": "unknown tool"})

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """Get a prompt from a service.

        Args:
            target_service: The target service
            prompt_name: The prompt name
            arguments: Prompt arguments
            timeout: Optional timeout

        Returns:
            Rendered prompt
        """
        self.get_prompt_calls.append(
            {
                "target_service": target_service,
                "prompt_name": prompt_name,
                "arguments": arguments,
                "timeout": timeout,
            }
        )

        # Return a mocked response based on the prompt name
        return self.mocked_prompt_responses.get(prompt_name, "Unknown prompt")

    async def read_resource(
        self,
        target_service: str,
        resource_uri: str,
        timeout: Optional[float] = None,
    ) -> bytes:
        """Read a resource from a service.

        Args:
            target_service: The target service
            resource_uri: The resource URI
            timeout: Optional timeout

        Returns:
            Resource data
        """
        self.read_resource_calls.append(
            {
                "target_service": target_service,
                "resource_uri": resource_uri,
                "timeout": timeout,
            }
        )

        # Return a mocked response based on the resource URI
        return self.mocked_resource_data.get(resource_uri, b"Resource not found")

    async def list_tools(
        self,
        target_service: str,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """List tools available on a service.

        Args:
            target_service: The target service
            timeout: Optional timeout

        Returns:
            List of tools
        """
        self.list_tools_calls.append(
            {
                "target_service": target_service,
                "timeout": timeout,
            }
        )

        # Return the mocked tools list
        return self.mocked_tools_list

    async def list_prompts(
        self,
        target_service: str,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """List prompts available on a service.

        Args:
            target_service: The target service
            timeout: Optional timeout

        Returns:
            List of prompts
        """
        self.list_prompts_calls.append(
            {
                "target_service": target_service,
                "timeout": timeout,
            }
        )

        # Return the mocked prompts list
        return self.mocked_prompts_list

    async def sample_prompt(
        self,
        target_service: str,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[float] = None,
        include_context: Optional[str] = None,
        model_preferences: Optional[Dict[str, Any]] = None,
        stop_sequences: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Sample a prompt from a service.

        Args:
            target_service: The target service
            messages: The messages to include
            system_prompt: Optional system prompt
            temperature: Optional temperature
            max_tokens: Optional max tokens
            include_context: Optional context inclusion mode
            model_preferences: Optional model preferences
            stop_sequences: Optional stop sequences
            timeout: Optional timeout

        Returns:
            The sampling result
        """
        self.sample_prompt_calls.append(
            {
                "target_service": target_service,
                "messages": messages,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "include_context": include_context,
                "model_preferences": model_preferences,
                "stop_sequences": stop_sequences,
                "timeout": timeout,
            }
        )

        # Return a mocked sampling response
        key = "default"
        if messages and isinstance(messages, list) and len(messages) > 0:
            first_message = messages[0]
            if isinstance(first_message, dict) and "content" in first_message:
                content = first_message["content"]
                if content in self.mocked_sampling_responses:
                    key = content

        return self.mocked_sampling_responses.get(key, {"content": "Default response"})


class TestMcpClientAgent(McpClientAgent):
    """Test client agent for delegation testing."""

    async def add_numbers(self, service_name: str, a: int, b: int) -> Dict[str, Any]:
        """Call the add_numbers tool on a service.

        Args:
            service_name: The service to call
            a: First number
            b: Second number

        Returns:
            Result from the service
        """
        result = await self.call_tool(target_service=service_name, tool_name="add_numbers", arguments={"a": a, "b": b})
        return result

    async def get_custom_greeting(self, service_name: str, name: str) -> str:
        """Get a custom greeting from a service.

        Args:
            service_name: The service to call
            name: The name to greet

        Returns:
            Greeting from the service
        """
        result = await self.get_prompt(target_service=service_name, prompt_name="greeting", arguments={"name": name})
        return result

    async def get_data_resource(self, service_name: str) -> bytes:
        """Get data resource from a service.

        Args:
            service_name: The service to call

        Returns:
            Resource data
        """
        result = await self.read_resource(target_service=service_name, uri="/api/data")
        return result

    async def chat_with_service(
        self, service_name: str, messages: List[Dict[str, Any]], temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Chat with a service using prompt sampling.

        Args:
            service_name: The service to chat with
            messages: The messages to send
            temperature: The temperature for sampling

        Returns:
            The response from the service
        """
        result = await self.sample_prompt(target_service=service_name, messages=messages, temperature=temperature)
        return result


@pytest.mark.mcp
class TestMcpClientAgentIntegration:
    """Integration tests for McpClientAgent with communicator."""

    @pytest.mark.asyncio
    async def test_client_agent_call_tool_delegation(self):
        """Test delegation of call_tool to the communicator."""
        # Create a test harness
        harness = AgentTestHarness(TestMcpClientAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-client")

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={"test-service": "http://localhost:8765"}, server_mode=False
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Call the high-level method that uses call_tool
            result = await agent.add_numbers("test-service", 5, 7)

            # Verify the result
            assert result == {"result": 42}

            # Verify that call_tool was called with the correct parameters
            assert len(communicator.call_tool_calls) == 1
            call = communicator.call_tool_calls[0]
            assert call["target_service"] == "test-service"
            assert call["tool_name"] == "add_numbers"
            assert call["arguments"] == {"a": 5, "b": 7}

            # Call directly to verify direct delegation
            direct_result = await agent.call_tool(
                target_service="test-service", tool_name="process_data", arguments={"data": "test"}
            )

            # Verify the result
            assert direct_result == {"status": "success", "processed": True}

            # Verify that call_tool was called with the correct parameters
            assert len(communicator.call_tool_calls) == 2
            call = communicator.call_tool_calls[1]
            assert call["target_service"] == "test-service"
            assert call["tool_name"] == "process_data"
            assert call["arguments"] == {"data": "test"}

    @pytest.mark.asyncio
    async def test_client_agent_get_prompt_delegation(self):
        """Test delegation of get_prompt to the communicator."""
        # Create a test harness
        harness = AgentTestHarness(TestMcpClientAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-client")

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={"test-service": "http://localhost:8765"}, server_mode=False
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Call the high-level method that uses get_prompt
            result = await agent.get_custom_greeting("test-service", "John")

            # Verify the result
            assert result == "Hello, Test User!"

            # Verify that get_prompt was called with the correct parameters
            assert len(communicator.get_prompt_calls) == 1
            call = communicator.get_prompt_calls[0]
            assert call["target_service"] == "test-service"
            assert call["prompt_name"] == "greeting"
            assert call["arguments"] == {"name": "John"}

            # Call directly to verify direct delegation
            direct_result = await agent.get_prompt(
                target_service="test-service", prompt_name="summary", arguments={"text": "Some text to summarize"}
            )

            # Verify the result
            assert direct_result == "This is a summary of the content."

            # Verify that get_prompt was called with the correct parameters
            assert len(communicator.get_prompt_calls) == 2
            call = communicator.get_prompt_calls[1]
            assert call["target_service"] == "test-service"
            assert call["prompt_name"] == "summary"
            assert call["arguments"] == {"text": "Some text to summarize"}

    @pytest.mark.asyncio
    async def test_client_agent_read_resource_delegation(self):
        """Test delegation of read_resource to the communicator."""
        # Create a test harness
        harness = AgentTestHarness(TestMcpClientAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-client")

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={"test-service": "http://localhost:8765"}, server_mode=False
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Call the high-level method that uses read_resource
            result = await agent.get_data_resource("test-service")

            # Verify the result
            assert result == b'{"data": "test"}'

            # Verify that read_resource was called with the correct parameters
            assert len(communicator.read_resource_calls) == 1
            call = communicator.read_resource_calls[0]
            assert call["target_service"] == "test-service"
            assert call["resource_uri"] == "/api/data"

            # Call directly to verify direct delegation
            direct_result = await agent.read_resource(target_service="test-service", uri="/images/logo.png")

            # Verify the result
            assert direct_result == b"BINARY_IMAGE_DATA"

            # Verify that read_resource was called with the correct parameters
            assert len(communicator.read_resource_calls) == 2
            call = communicator.read_resource_calls[1]
            assert call["target_service"] == "test-service"
            assert call["resource_uri"] == "/images/logo.png"

    @pytest.mark.asyncio
    async def test_client_agent_list_tools_delegation(self):
        """Test delegation of list_tools to the communicator."""
        # Create a test harness
        harness = AgentTestHarness(TestMcpClientAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-client")

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={"test-service": "http://localhost:8765"}, server_mode=False
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Call list_tools
            result = await agent.list_tools("test-service")

            # Verify the result
            assert len(result) == 2
            assert result[0]["name"] == "add_numbers"
            assert result[1]["name"] == "process_data"

            # Verify that list_tools was called with the correct parameters
            assert len(communicator.list_tools_calls) == 1
            call = communicator.list_tools_calls[0]
            assert call["target_service"] == "test-service"

    @pytest.mark.asyncio
    async def test_client_agent_sample_prompt_delegation(self):
        """Test delegation of sample_prompt to the communicator."""
        # Create a test harness
        harness = AgentTestHarness(TestMcpClientAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-client")

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={"test-service": "http://localhost:8765"}, server_mode=False
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Call the high-level method that uses sample_prompt
            messages = [{"role": "user", "content": "Hello, how are you?"}]
            result = await agent.chat_with_service("test-service", messages, temperature=0.8)

            # Verify the result
            assert result == {"content": "Mocked sampling response"}

            # Verify that sample_prompt was called with the correct parameters
            assert len(communicator.sample_prompt_calls) == 1
            call = communicator.sample_prompt_calls[0]
            assert call["target_service"] == "test-service"
            assert call["messages"] == messages
            assert call["temperature"] == 0.8
