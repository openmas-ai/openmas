"""Unit tests for the sampling system."""

import json

import pytest

from openmas.prompt.base import Prompt, PromptContent, PromptMetadata
from openmas.sampling.base import (
    Message,
    MessageRole,
    Sampler,
    SamplerProtocol,
    SamplingContext,
    SamplingParameters,
    SamplingResult,
)


class TestMessage:
    """Tests for the Message class."""

    def test_initialization(self):
        """Test basic initialization of Message."""
        message = Message(role=MessageRole.USER, content="Hello")
        assert message.role == MessageRole.USER
        assert message.content == "Hello"
        assert message.metadata is None

    def test_initialization_with_metadata(self):
        """Test initialization of Message with metadata."""
        metadata = {"timestamp": "2023-01-01T12:00:00Z"}
        message = Message(role=MessageRole.USER, content="Hello", metadata=metadata)
        assert message.role == MessageRole.USER
        assert message.content == "Hello"
        assert message.metadata == metadata

    def test_to_dict(self):
        """Test conversion to dictionary."""
        message = Message(role=MessageRole.USER, content="Hello")
        message_dict = message.to_dict()
        assert message_dict["role"] == "user"
        assert message_dict["content"] == "Hello"
        assert "metadata" not in message_dict

    def test_to_dict_with_metadata(self):
        """Test conversion to dictionary with metadata."""
        metadata = {"timestamp": "2023-01-01T12:00:00Z"}
        message = Message(role=MessageRole.USER, content="Hello", metadata=metadata)
        message_dict = message.to_dict()
        assert message_dict["role"] == "user"
        assert message_dict["content"] == "Hello"
        assert message_dict["metadata"] == metadata


class TestSamplingParameters:
    """Tests for the SamplingParameters class."""

    def test_initialization_defaults(self):
        """Test that the default values are set correctly."""
        params = SamplingParameters()
        assert params.temperature == 0.7
        assert params.max_tokens is None
        assert params.top_p is None
        assert params.top_k is None
        assert params.stop_sequences is None
        assert params.frequency_penalty is None
        assert params.presence_penalty is None
        assert params.seed is None

    def test_initialization_custom(self):
        """Test initialization with custom values."""
        params = SamplingParameters(
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
            top_k=50,
            stop_sequences=["END"],
            presence_penalty=0.5,
            frequency_penalty=0.5,
            seed=42,
        )
        assert params.temperature == 0.5
        assert params.max_tokens == 500
        assert params.top_p == 0.8
        assert params.top_k == 50
        assert params.stop_sequences == ["END"]
        assert params.presence_penalty == 0.5
        assert params.frequency_penalty == 0.5
        assert params.seed == 42

    def test_to_dict(self):
        """Test conversion to dictionary."""
        params = SamplingParameters(
            temperature=0.5,
            max_tokens=500,
            top_p=0.8,
        )
        params_dict = params.to_dict()
        assert params_dict["temperature"] == 0.5
        assert params_dict["max_tokens"] == 500
        assert params_dict["top_p"] == 0.8
        assert "top_k" not in params_dict  # None values should be omitted


class TestSamplingContext:
    """Tests for the SamplingContext class."""

    def test_initialization_defaults(self):
        """Test that the default values are set correctly."""
        context = SamplingContext()
        assert context.system_prompt is None
        assert context.messages == []
        assert isinstance(context.parameters, SamplingParameters)
        assert context.metadata == {}

    def test_initialization_custom(self):
        """Test initialization with custom values."""
        messages = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        ]
        parameters = SamplingParameters(temperature=0.5)
        metadata = {"source": "test"}

        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=messages,
            parameters=parameters,
            metadata=metadata,
        )

        assert context.system_prompt == "You are a helpful assistant."
        assert context.messages == messages
        assert context.parameters == parameters
        assert context.metadata == metadata

    def test_from_prompt(self):
        """Test creating a context from a prompt."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
            examples=[
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is Paris."},
            ],
        )
        prompt = Prompt(metadata=metadata, content=content)

        context = SamplingContext.from_prompt(
            prompt,
            context_vars={"question": "What is the capital of Germany?"},
            params=SamplingParameters(temperature=0.5),
        )

        assert context.system_prompt == "You are a helpful assistant."
        assert len(context.messages) == 3  # 2 examples + 1 template
        assert context.messages[0].role == MessageRole.USER
        assert context.messages[0].content == "What is the capital of France?"
        assert context.messages[1].role == MessageRole.ASSISTANT
        assert context.messages[1].content == "The capital of France is Paris."
        assert context.messages[2].role == MessageRole.USER
        assert context.messages[2].content == "Answer the following question: What is the capital of Germany?"
        assert context.parameters.temperature == 0.5

    def test_add_message(self):
        """Test adding a message to the context."""
        context = SamplingContext()
        context.add_message(MessageRole.USER, "Hello")

        assert len(context.messages) == 1
        assert context.messages[0].role == MessageRole.USER
        assert context.messages[0].content == "Hello"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        messages = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        ]
        parameters = SamplingParameters(temperature=0.5)
        metadata = {"source": "test"}

        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=messages,
            parameters=parameters,
            metadata=metadata,
        )

        context_dict = context.to_dict()
        assert context_dict["system"] == "You are a helpful assistant."
        assert len(context_dict["messages"]) == 2
        assert context_dict["messages"][0]["role"] == "user"
        assert context_dict["messages"][0]["content"] == "Hello"
        assert context_dict["parameters"]["temperature"] == 0.5
        assert context_dict["metadata"] == metadata


class TestSamplingResult:
    """Tests for the SamplingResult class."""

    def test_initialization_minimal(self):
        """Test minimal initialization of SamplingResult."""
        result = SamplingResult(content="Hello world")
        assert result.content == "Hello world"
        assert result.finish_reason is None
        assert result.usage is None
        assert result.metadata == {}
        assert result.raw_response is None

    def test_initialization_full(self):
        """Test full initialization of SamplingResult."""
        result = SamplingResult(
            content="Hello world",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            metadata={"model": "gpt-4"},
            raw_response={"content": "Hello world", "other_field": "value"},
        )
        assert result.content == "Hello world"
        assert result.finish_reason == "stop"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert result.metadata == {"model": "gpt-4"}
        assert result.raw_response == {"content": "Hello world", "other_field": "value"}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = SamplingResult(
            content="Hello world",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            metadata={"model": "gpt-4"},
        )
        result_dict = result.to_dict()
        assert result_dict["content"] == "Hello world"
        assert result_dict["finish_reason"] == "stop"
        assert result_dict["usage"] == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert result_dict["metadata"] == {"model": "gpt-4"}

    def test_to_json(self):
        """Test conversion to JSON."""
        result = SamplingResult(
            content="Hello world",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            metadata={"model": "gpt-4"},
        )
        result_json = result.to_json()
        parsed = json.loads(result_json)
        assert parsed["content"] == "Hello world"
        assert parsed["finish_reason"] == "stop"
        assert parsed["usage"] == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert parsed["metadata"] == {"model": "gpt-4"}

    def test_to_json_pretty(self):
        """Test pretty conversion to JSON."""
        result = SamplingResult(content="Hello world")
        result_json = result.to_json(pretty=True)
        assert "Hello world" in result_json
        assert "  " in result_json  # Check for indentation


class TestSampler:
    """Tests for the Sampler class."""

    def test_initialization(self):
        """Test initialization of Sampler."""
        sampler = Sampler()
        assert isinstance(sampler, Sampler)

    @pytest.mark.asyncio
    async def test_sample_not_implemented(self):
        """Test that sample raises NotImplementedError."""
        sampler = Sampler()
        context = SamplingContext(
            system_prompt="You are a helpful assistant.",
            messages=[Message(role=MessageRole.USER, content="Hello")],
        )

        with pytest.raises(NotImplementedError):
            await sampler.sample(context)

    def test_create_context(self):
        """Test creating a context from parameters."""
        system = "You are a helpful assistant."
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        parameters = {"temperature": 0.5, "max_tokens": 500}

        context = Sampler.create_context(
            system=system,
            messages=messages,
            parameters=parameters,
        )

        assert context.system_prompt == system
        assert len(context.messages) == 2
        assert context.messages[0].role == MessageRole.USER
        assert context.messages[0].content == "Hello"
        assert context.messages[1].role == MessageRole.ASSISTANT
        assert context.messages[1].content == "Hi there!"
        assert context.parameters.temperature == 0.5
        assert context.parameters.max_tokens == 500

    @pytest.mark.asyncio
    async def test_sample_from_prompt(self):
        """Test sampling from a prompt."""

        # Create a mock sampler that returns a fixed result
        class MockSampler(Sampler):
            async def sample(self, context, model=None):
                return SamplingResult(content="Mocked response")

        sampler = MockSampler()

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

        assert result.content == "Mocked response"


# Create a protocol implementation for testing
class TestSamplerImplementation(Sampler):
    """Concrete implementation of Sampler for testing."""

    async def sample(self, context, model=None):
        """Sample implementation for testing."""
        return SamplingResult(content="Test response")


class TestSamplerProtocol:
    """Tests for the SamplerProtocol."""

    def test_protocol_recognition(self):
        """Test that a class implementing the protocol is recognized."""
        sampler = TestSamplerImplementation()
        assert isinstance(sampler, SamplerProtocol)

    def test_protocol_non_recognition(self):
        """Test that a class not implementing the protocol is not recognized."""

        class NonProtocolClass:
            pass

        non_sampler = NonProtocolClass()
        assert not isinstance(non_sampler, SamplerProtocol)
