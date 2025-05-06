"""MCP-specific sampler implementation.

This module provides a sampler that uses the MCP protocol to sample from language models.
It integrates with the existing MCP communicators in OpenMAS.
"""

from typing import Any, Dict, List, Optional, Tuple, cast

from openmas.agent.mcp import McpAgent, McpCommunicatorProtocol
from openmas.communication.base import BaseCommunicator, CommunicationError
from openmas.logging import get_logger
from openmas.sampling.base import (
    Message,
    MessageRole,
    SamplingContext,
    SamplingParameters,
    SamplingResult,
    Sampler,
)

# Configure logging
logger = get_logger(__name__)


class McpSampler(Sampler):
    """Sampler that uses MCP to sample from a language model."""

    def __init__(
        self,
        communicator: BaseCommunicator,
        target_service: str,
        default_model: Optional[str] = None,
    ) -> None:
        """Initialize the sampler.

        Args:
            communicator: The communicator to use for sampling
            target_service: The target service to sample from
            default_model: Optional default model to use
        """
        self.communicator = communicator
        self.target_service = target_service
        self.default_model = default_model
        
        # Validate that the communicator supports MCP sampling
        if not hasattr(self.communicator, "sample_prompt"):
            raise ValueError(
                f"Communicator {type(communicator).__name__} does not support MCP sampling"
            )

    async def sample(
        self,
        context: SamplingContext,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from the language model using MCP.

        Args:
            context: The sampling context
            model: Optional model to use (overrides default_model)

        Returns:
            The sampling result

        Raises:
            CommunicationError: If there's an error communicating with the service
        """
        # Convert messages to MCP format
        mcp_messages = []
        for message in context.messages:
            mcp_messages.append({
                "role": message.role.value,
                "content": message.content,
            })
        
        # Extract parameters from the context
        params = context.parameters
        
        try:
            # Cast to avoid type errors with protocol check
            communicator = cast(McpCommunicatorProtocol, self.communicator)
            
            # Call the MCP sample_prompt method
            response = await communicator.sample_prompt(
                target_service=self.target_service,
                messages=mcp_messages,
                system_prompt=context.system_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                stop_sequences=params.stop_sequences,
                model_preferences={
                    "model": model or self.default_model
                } if model or self.default_model else None,
            )
            
            # Extract content from the response
            if isinstance(response, dict) and "content" in response:
                content = response["content"]
            else:
                content = str(response)
                
            # Create and return a SamplingResult
            return SamplingResult(
                content=content,
                raw_response=response,
            )
            
        except Exception as e:
            logger.error(f"Error sampling from {self.target_service}: {e}")
            if isinstance(e, CommunicationError):
                raise
            raise CommunicationError(
                f"Error sampling from {self.target_service}: {e}",
                target=self.target_service,
            ) from e


class McpAgentSampler(Sampler):
    """Sampler that uses an MCP agent to sample from a language model."""

    def __init__(
        self,
        agent: McpAgent,
        target_service: str,
        default_model: Optional[str] = None,
    ) -> None:
        """Initialize the sampler.

        Args:
            agent: The MCP agent to use for sampling
            target_service: The target service to sample from
            default_model: Optional default model to use
        """
        self.agent = agent
        self.target_service = target_service
        self.default_model = default_model

    async def sample(
        self,
        context: SamplingContext,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from the language model using the MCP agent.

        Args:
            context: The sampling context
            model: Optional model to use (overrides default_model)

        Returns:
            The sampling result

        Raises:
            AttributeError: If the agent doesn't support sampling
            CommunicationError: If there's an error communicating with the service
        """
        # Convert messages to MCP format
        mcp_messages = []
        for message in context.messages:
            mcp_messages.append({
                "role": message.role.value,
                "content": message.content,
            })
        
        # Extract parameters from the context
        params = context.parameters
        
        try:
            # Use the agent's sample_prompt method
            response = await self.agent.sample_prompt(
                target_service=self.target_service,
                messages=mcp_messages,
                system_prompt=context.system_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                stop_sequences=params.stop_sequences,
                model_preferences={
                    "model": model or self.default_model
                } if model or self.default_model else None,
            )
            
            # Extract content from the response
            if isinstance(response, dict) and "content" in response:
                content = response["content"]
            else:
                content = str(response)
                
            # Create and return a SamplingResult
            return SamplingResult(
                content=content,
                raw_response=response,
            )
            
        except Exception as e:
            logger.error(f"Error sampling from {self.target_service}: {e}")
            if isinstance(e, (AttributeError, CommunicationError)):
                raise
            raise CommunicationError(
                f"Error sampling from {self.target_service}: {e}",
                target=self.target_service,
            ) from e 