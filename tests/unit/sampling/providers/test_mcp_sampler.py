"""Unit tests for the MCP samplers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from openmas.agent.mcp import McpAgent
from openmas.communication.base import BaseCommunicator
from openmas.exceptions import CommunicationError
from openmas.sampling import MessageRole, SamplingContext, SamplingParameters
from openmas.sampling.providers.mcp import McpAgentSampler, McpSampler


class TestMcpSampler:
    """Tests for the McpSampler class."""

    @pytest.fixture
    def communicator(self):
        """Create a mock communicator."""
        mock_communicator = MagicMock(spec=BaseCommunicator)
        mock_communicator.sample_prompt = AsyncMock(return_value={"content": "Generated response"})
        return mock_communicator

    def test_initialization(self, communicator):
        """Test initialization of McpSampler."""
        sampler = McpSampler(communicator=communicator, target_service="llm-service")
        assert sampler.communicator is communicator
        assert sampler.target_service == "llm-service"
        assert sampler.default_model is None

    def test_initialization_with_model(self, communicator):
        """Test initialization with a default model."""
        sampler = McpSampler(communicator=communicator, target_service="llm-service", default_model="claude-3")
        assert sampler.default_model == "claude-3"

    @pytest.mark.asyncio
    async def test_sample_text(self, communicator):
        """Test sampling text."""
        sampler = McpSampler(communicator=communicator, target_service="llm-service")

        # Call sample_text
        response = await sampler.sample_text(
            prompt="Hello, how are you?",
            system="You are a helpful assistant.",
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
        )

        # Check the response
        assert response.content == "Generated response"

        # Check that sample_prompt was called correctly
        communicator.sample_prompt.assert_called_once()
        args, kwargs = communicator.sample_prompt.call_args
        assert kwargs["target_service"] == "llm-service"
        assert "messages" in kwargs
        assert len(kwargs["messages"]) == 2  # System + user message
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][0]["content"] == "You are a helpful assistant."
        assert kwargs["messages"][1]["role"] == "user"
        assert kwargs["messages"][1]["content"] == "Hello, how are you?"

    @pytest.mark.asyncio
    async def test_sample_text_with_model(self, communicator):
        """Test sampling text with a specified model."""
        sampler = McpSampler(communicator=communicator, target_service="llm-service", default_model="claude-3")

        # Call sample_text with a different model
        await sampler.sample_text(
            prompt="Hello, how are you?",
            system="You are a helpful assistant.",
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
            model="claude-3-opus",
        )

        # Check that sample_prompt was called with the correct model
        args, kwargs = communicator.sample_prompt.call_args
        assert kwargs["model_preferences"] == {"model": "claude-3-opus"}

    @pytest.mark.asyncio
    async def test_sample_messages(self, communicator):
        """Test sampling from messages."""
        sampler = McpSampler(communicator=communicator, target_service="llm-service")

        # Create messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm fine, thank you!"},
            {"role": "user", "content": "What can you do?"},
        ]

        # Call sample_messages
        await sampler.sample_messages(
            messages=messages,
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
        )

        # Check that sample_prompt was called correctly
        communicator.sample_prompt.assert_called_once()
        args, kwargs = communicator.sample_prompt.call_args
        assert kwargs["target_service"] == "llm-service"
        assert len(kwargs["messages"]) == 4

    @pytest.mark.asyncio
    async def test_sample_from_context(self, communicator):
        """Test sampling from a context."""
        sampler = McpSampler(communicator=communicator, target_service="llm-service")

        # Create a context
        context = SamplingContext(
            messages=[
                {"role": MessageRole.SYSTEM, "content": "You are a helpful assistant."},
                {"role": MessageRole.USER, "content": "Hello, how are you?"},
            ],
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
        )

        # Call sample_from_context
        response = await sampler.sample_from_context(context)

        # Check the response
        assert response.content == "Generated response"

        # Check that sample_prompt was called correctly
        communicator.sample_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_communication_error(self, communicator):
        """Test handling communication errors."""
        # Mock the communicator to raise a CommunicationError
        communicator.sample_prompt = AsyncMock(side_effect=CommunicationError("Test error"))

        sampler = McpSampler(communicator=communicator, target_service="llm-service")

        # Call sample_text and expect an exception
        with pytest.raises(CommunicationError, match="Test error"):
            await sampler.sample_text(prompt="Hello", system="You are a helpful assistant.")


class TestMcpAgentSampler:
    """Tests for the McpAgentSampler class."""

    @pytest.fixture
    def agent(self):
        """Create a mock agent."""
        mock_agent = MagicMock(spec=McpAgent)
        mock_agent.sample_prompt = AsyncMock(return_value={"content": "Generated response"})
        return mock_agent

    def test_initialization(self, agent):
        """Test initialization of McpAgentSampler."""
        sampler = McpAgentSampler(agent=agent, target_service="llm-service")
        assert sampler.agent is agent
        assert sampler.target_service == "llm-service"
        assert sampler.default_model is None

    def test_initialization_with_model(self, agent):
        """Test initialization with a default model."""
        sampler = McpAgentSampler(agent=agent, target_service="llm-service", default_model="claude-3")
        assert sampler.default_model == "claude-3"

    @pytest.mark.asyncio
    async def test_sample_text(self, agent):
        """Test sampling text."""
        sampler = McpAgentSampler(agent=agent, target_service="llm-service")

        # Call sample_text
        await sampler.sample_text(
            prompt="Hello, how are you?",
            system="You are a helpful assistant.",
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
        )

        # Check that sample_prompt was called correctly
        agent.sample_prompt.assert_called_once()
        args, kwargs = agent.sample_prompt.call_args
        assert kwargs["target_service"] == "llm-service"
        assert len(kwargs["messages"]) == 2  # System + user message
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][0]["content"] == "You are a helpful assistant."
        assert kwargs["messages"][1]["role"] == "user"
        assert kwargs["messages"][1]["content"] == "Hello, how are you?"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_sample_text_with_model(self, agent):
        """Test sampling text with a specified model."""
        sampler = McpAgentSampler(agent=agent, target_service="llm-service", default_model="claude-3")

        # Call sample_text with a different model
        await sampler.sample_text(
            prompt="Hello, how are you?",
            system="You are a helpful assistant.",
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
            model="claude-3-opus",
        )

        # Check that sample_prompt was called with the correct model preferences
        args, kwargs = agent.sample_prompt.call_args
        assert kwargs["model_preferences"] == {"model": "claude-3-opus"}

    @pytest.mark.asyncio
    async def test_sample_messages(self, agent):
        """Test sampling from messages."""
        sampler = McpAgentSampler(agent=agent, target_service="llm-service")

        # Create messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm fine, thank you!"},
            {"role": "user", "content": "What can you do?"},
        ]

        # Call sample_messages
        await sampler.sample_messages(
            messages=messages,
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
        )

        # Check that sample_prompt was called correctly
        agent.sample_prompt.assert_called_once()
        args, kwargs = agent.sample_prompt.call_args
        assert kwargs["target_service"] == "llm-service"
        assert len(kwargs["messages"]) == 4

    @pytest.mark.asyncio
    async def test_sample_from_context(self, agent):
        """Test sampling from a context."""
        sampler = McpAgentSampler(agent=agent, target_service="llm-service")

        # Create a context
        context = SamplingContext(
            messages=[
                {"role": MessageRole.SYSTEM, "content": "You are a helpful assistant."},
                {"role": MessageRole.USER, "content": "Hello, how are you?"},
            ],
            parameters=SamplingParameters(temperature=0.7, max_tokens=100),
        )

        # Call sample_from_context
        await sampler.sample_from_context(context)

        # Check that sample_prompt was called correctly
        agent.sample_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_communication_error(self, agent):
        """Test handling communication errors."""
        # Mock the agent to raise a CommunicationError
        agent.sample_prompt = AsyncMock(side_effect=CommunicationError("Test error"))

        sampler = McpAgentSampler(agent=agent, target_service="llm-service")

        # Call sample_text and expect an exception
        with pytest.raises(CommunicationError, match="Test error"):
            await sampler.sample_text(prompt="Hello", system="You are a helpful assistant.")
