"""Core sampling functionality for OpenMAS.

This module provides abstractions for sampling from language models in a way that
is consistent across different providers (e.g., Anthropic, OpenAI) and integrates
with MCP.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple, Type, Union, runtime_checkable
import json
from pydantic import BaseModel, Field

from openmas.prompt.base import Prompt


class SamplingParameters(BaseModel):
    """Parameters for sampling from a language model."""

    temperature: Optional[float] = Field(
        default=0.7,
        description="Controls randomness. Higher values produce more random outputs.",
        ge=0.0,
        le=1.0,
    )
    max_tokens: Optional[int] = Field(
        default=1024,
        description="Maximum number of tokens to generate.",
        gt=0,
    )
    top_p: Optional[float] = Field(
        default=0.9,
        description="Nucleus sampling parameter. Keep the most likely tokens whose cumulative probability exceeds p.",
        ge=0.0,
        le=1.0,
    )
    top_k: Optional[int] = Field(
        default=None,
        description="Only sample from the top k most likely tokens.",
        gt=0,
    )
    stop_sequences: Optional[List[str]] = Field(
        default=None,
        description="Sequences that will cause the model to stop generating further tokens.",
    )
    repetition_penalty: Optional[float] = Field(
        default=None,
        description="Penalty for repeating tokens. Higher values discourage repetition.",
        ge=0.0,
    )
    presence_penalty: Optional[float] = Field(
        default=None,
        description="Penalty for new tokens based on whether they appear in the text so far.",
        ge=0.0,
    )
    frequency_penalty: Optional[float] = Field(
        default=None,
        description="Penalty for new tokens based on their frequency in the text so far.",
        ge=0.0,
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for deterministic sampling."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary, omitting None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """A message in a conversation."""

    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        result = {"role": self.role, "content": self.content}
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class SamplingContext(BaseModel):
    """Context for a sampling operation."""

    system_prompt: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    parameters: SamplingParameters = Field(default_factory=SamplingParameters)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_prompt(
        cls,
        prompt: Prompt,
        context_vars: Optional[Dict[str, Any]] = None,
        params: Optional[SamplingParameters] = None,
    ) -> "SamplingContext":
        """Create a sampling context from a prompt.

        Args:
            prompt: The prompt to use
            context_vars: Variables to use for template rendering
            params: Optional sampling parameters

        Returns:
            A sampling context for the given prompt
        """
        system = prompt.get_system_prompt()
        
        # Start with an empty message list
        messages = []
        
        # Add examples as messages if available
        for example in prompt.get_examples():
            if "role" in example and "content" in example:
                role = MessageRole(example["role"])
                messages.append(Message(role=role, content=example["content"]))
        
        # Add the template as a user message if available
        template = prompt.get_template()
        if template and context_vars:
            # Simple template rendering (use a proper template engine in production)
            content = template
            for key, value in context_vars.items():
                if isinstance(value, (str, int, float, bool)):
                    placeholder = f"{{{{{key}}}}}"
                    content = content.replace(placeholder, str(value))
            
            messages.append(Message(role=MessageRole.USER, content=content))
        
        return cls(
            system_prompt=system,
            messages=messages,
            parameters=params or SamplingParameters(),
        )

    def add_message(self, role: MessageRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to the context.

        Args:
            role: The role of the message
            content: The content of the message
            metadata: Optional metadata for the message
        """
        self.messages.append(Message(role=role, content=content, metadata=metadata))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        result = {
            "messages": [m.to_dict() for m in self.messages],
            "parameters": self.parameters.to_dict(),
        }
        if self.system_prompt:
            result["system"] = self.system_prompt
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class SamplingResult(BaseModel):
    """Result of a sampling operation."""

    content: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_response: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        result = {"content": self.content}
        if self.finish_reason:
            result["finish_reason"] = self.finish_reason
        if self.usage:
            result["usage"] = self.usage
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def to_json(self, pretty: bool = False) -> str:
        """Convert to JSON."""
        if pretty:
            return json.dumps(self.to_dict(), indent=2)
        return json.dumps(self.to_dict())


@runtime_checkable
class SamplerProtocol(Protocol):
    """Protocol for samplers."""

    async def sample(
        self,
        context: SamplingContext,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from the language model.

        Args:
            context: The sampling context
            model: Optional model to use

        Returns:
            The sampling result
        """
        ...


class Sampler:
    """Base class for samplers."""

    async def sample(
        self,
        context: SamplingContext,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from the language model.

        Args:
            context: The sampling context
            model: Optional model to use

        Returns:
            The sampling result

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement sample")

    @classmethod
    def create_context(
        cls,
        system: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> SamplingContext:
        """Create a sampling context.

        Args:
            system: Optional system prompt
            messages: Optional list of messages
            parameters: Optional sampling parameters

        Returns:
            A sampling context
        """
        params = SamplingParameters(**(parameters or {}))
        
        msg_list = []
        if messages:
            for msg in messages:
                role = MessageRole(msg["role"])
                content = msg["content"]
                metadata = msg.get("metadata")
                msg_list.append(Message(role=role, content=content, metadata=metadata))
        
        return SamplingContext(
            system_prompt=system,
            messages=msg_list,
            parameters=params,
        )
        
    async def sample_from_prompt(
        self,
        prompt: Prompt,
        context_vars: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from a prompt.

        Args:
            prompt: The prompt to sample from
            context_vars: Variables to use for template rendering
            parameters: Optional sampling parameters
            model: Optional model to use

        Returns:
            The sampling result
        """
        params = SamplingParameters(**(parameters or {}))
        context = SamplingContext.from_prompt(prompt, context_vars, params)
        return await self.sample(context, model) 