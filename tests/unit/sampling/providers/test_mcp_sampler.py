"""Unit tests for the MCP samplers."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openmas.agent.mcp import McpAgent
from openmas.communication.base import BaseCommunicator, CommunicationError
from openmas.prompt import Prompt, PromptContent, PromptMetadata
from openmas.sampling import MessageRole, SamplingContext, SamplingParameters
from openmas.sampling.providers.mcp import McpAgentSampler, McpSampler


class TestMcpSampler:
    """Tests for the McpSampler class."""

    @pytest.fixture
    def communicator(self):
        """Create a mock communicator for testing."""
        mock_communicator = MagicMock(spec=BaseCommunicator)
        mock_communicator.sample_prompt = AsyncMock(return_value={"content": "Test response"})
        return mock_communicator

    @pytest.fixture
    def sampler(self, communicator):
        """Create a McpSampler instance for testing."""
        return McpSampler(
            communicator=communicator,
            target_service="llm-service",
            default_model="claude-3",
        )

    def test_initialization(self, communicator):
        """Test initialization of McpSampler."""
        sampler = McpSampler(
            communicator=communicator,
            target_service="llm-service",
            default_model="claude-3",
        )
        assert sampler.communicator == communicator
        assert sampler.target_service == "llm-service"
        assert sampler.default_model == "claude-3"

    def test_initialization_no_sample_prompt(self):
        """Test initialization with a communicator that doesn't support sample_prompt."""
        communicator = MagicMock(spec=BaseCommunicator)
        # Communicator has no sample_prompt method
        
        with pytest.raises(ValueError, match="does not support MCP sampling"):
            McpSampler(
                communicator=communicator,
                target_service="llm-service",
            )

    @pytest.mark.asyncio
    async def test_sample(self, sampler, communicator):
        """Test sampling from a context."""
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[
                {"role": MessageRole.USER, "content": "Hello"}
            ],
            parameters=SamplingParameters(temperature=0.5, max_tokens=100),
        )
        
        result = await sampler.sample(context)
        
        # Check that the communicator's sample_prompt method was called correctly
        communicator.sample_prompt.assert_called_once()
        call_args = communicator.sample_prompt.call_args[1]
        assert call_args["target_service"] == "llm-service"
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Hello"
        assert call_args["system_prompt"] == "You are a helpful assistant."
        assert call_args["temperature"] == 0.5
        assert call_args["max_tokens"] == 100
        
        # Check the result
        assert result.content == "Test response"

    @pytest.mark.asyncio
    async def test_sample_with_model_override(self, sampler, communicator):
        """Test sampling with a model override."""
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[
                {"role": MessageRole.USER, "content": "Hello"}
            ],
        )
        
        result = await sampler.sample(context, model="gpt-4")
        
        # Check that the model was passed correctly
        call_args = communicator.sample_prompt.call_args[1]
        assert call_args["model_preferences"] == {"model": "gpt-4"}

    @pytest.mark.asyncio
    async def test_sample_exception(self, sampler, communicator):
        """Test handling of exceptions during sampling."""
        communicator.sample_prompt.side_effect = ValueError("Test error")
        
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[
                {"role": MessageRole.USER, "content": "Hello"}
            ],
        )
        
        with pytest.raises(CommunicationError, match="Error sampling from llm-service"):
            await sampler.sample(context)


class TestMcpAgentSampler:
    """Tests for the McpAgentSampler class."""

    @pytest.fixture
    def agent(self):
        """Create a mock agent for testing."""
        mock_agent = MagicMock(spec=McpAgent)
        mock_agent.sample_prompt = AsyncMock(return_value={"content": "Test response"})
        return mock_agent

    @pytest.fixture
    def sampler(self, agent):
        """Create a McpAgentSampler instance for testing."""
        return McpAgentSampler(
            agent=agent,
            target_service="llm-service",
            default_model="claude-3",
        )

    def test_initialization(self, agent):
        """Test initialization of McpAgentSampler."""
        sampler = McpAgentSampler(
            agent=agent,
            target_service="llm-service",
            default_model="claude-3",
        )
        assert sampler.agent == agent
        assert sampler.target_service == "llm-service"
        assert sampler.default_model == "claude-3"

    @pytest.mark.asyncio
    async def test_sample(self, sampler, agent):
        """Test sampling from a context."""
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[
                {"role": MessageRole.USER, "content": "Hello"}
            ],
            parameters=SamplingParameters(temperature=0.5, max_tokens=100),
        )
        
        result = await sampler.sample(context)
        
        # Check that the agent's sample_prompt method was called correctly
        agent.sample_prompt.assert_called_once()
        call_args = agent.sample_prompt.call_args[1]
        assert call_args["target_service"] == "llm-service"
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Hello"
        assert call_args["system_prompt"] == "You are a helpful assistant."
        assert call_args["temperature"] == 0.5
        assert call_args["max_tokens"] == 100
        
        # Check the result
        assert result.content == "Test response"

    @pytest.mark.asyncio
    async def test_sample_with_model_override(self, sampler, agent):
        """Test sampling with a model override."""
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[
                {"role": MessageRole.USER, "content": "Hello"}
            ],
        )
        
        result = await sampler.sample(context, model="gpt-4")
        
        # Check that the model was passed correctly
        call_args = agent.sample_prompt.call_args[1]
        assert call_args["model_preferences"] == {"model": "gpt-4"}

    @pytest.mark.asyncio
    async def test_sample_exception(self, sampler, agent):
        """Test handling of exceptions during sampling."""
        agent.sample_prompt.side_effect = ValueError("Test error")
        
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[
                {"role": MessageRole.USER, "content": "Hello"}
            ],
        )
        
        with pytest.raises(CommunicationError, match="Error sampling from llm-service"):
            await sampler.sample(context)

    @pytest.mark.asyncio
    async def test_sample_from_prompt(self, sampler, agent):
        """Test sampling from a prompt."""
        # Create a test prompt
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
        )
        prompt = Prompt(metadata=metadata, content=content)
        
        # Test sampling from the prompt
        result = await sampler.sample_from_prompt(
            prompt=prompt,
            context_vars={"question": "What is the capital of Germany?"},
            parameters={"temperature": 0.5},
            model="gpt-4",
        )
        
        # Check that the agent's sample_prompt method was called
        agent.sample_prompt.assert_called_once()
        call_args = agent.sample_prompt.call_args[1]
        
        # Check the messages
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert "What is the capital of Germany?" in call_args["messages"][0]["content"]
        
        # Check the system prompt
        assert call_args["system_prompt"] == "You are a helpful assistant."
        
        # Check the sampling parameters
        assert call_args["temperature"] == 0.5
        
        # Check the model preference
        assert call_args["model_preferences"] == {"model": "gpt-4"}
        
        # Check the result
        assert result.content == "Test response" 