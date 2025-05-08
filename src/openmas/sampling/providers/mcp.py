"""MCP-specific sampler implementation.

This module provides a sampler that uses the MCP protocol to sample from language models.
It integrates with the existing MCP communicators in OpenMAS.
"""

from typing import Any, Dict, List, Optional

from openmas.agent.mcp import McpAgent
from openmas.communication.base import BaseCommunicator
from openmas.exceptions import CommunicationError
from openmas.logging import get_logger
from openmas.sampling.base import BaseSampler, Message, MessageRole, SamplingContext, SamplingParameters, SamplingResult

# Configure logging
logger = get_logger(__name__)


class McpSampler(BaseSampler):
    """Sampler that uses MCP to sample from a language model."""

    def __init__(
        self,
        communicator: BaseCommunicator,
        params: SamplingParameters,
        target_service: str = "mcp",
    ) -> None:
        """Initialize the sampler.

        Args:
            communicator: The communicator to use for sampling
            params: The sampling parameters, including provider and model
            target_service: The target service to sample from (defaults to "mcp")
        """
        self.communicator = communicator
        self.params = params
        self.target_service = target_service
        self.default_model = params.model

        # Validate that the communicator supports MCP sampling
        if not hasattr(self.communicator, "sample_prompt"):
            raise ValueError(f"Communicator {type(communicator).__name__} does not support MCP sampling")

    async def sample(
        self,
        context: SamplingContext,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from the language model.

        Args:
            context: The context to sample from
            model: Optional model to use

        Returns:
            The sampling result
        """
        # If a model is provided, override the context's model
        if model:
            context.model = model

        return await self.sample_from_context(context)

    async def sample_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        parameters: Optional[SamplingParameters] = None,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from a text prompt.

        Args:
            prompt: The prompt text
            system: Optional system prompt
            parameters: Optional sampling parameters
            model: Optional model to use (overrides default_model)

        Returns:
            The sampling result
        """
        # Create a context with the prompt as a user message
        messages = []

        # Add system message if provided
        if system:
            messages.append({"role": MessageRole.SYSTEM.value, "content": system})

        # Add user message
        messages.append({"role": MessageRole.USER.value, "content": prompt})

        context = self._create_instance_context(
            messages=messages,
            parameters=parameters,
            model=model,
        )

        return await self.sample_from_context(context)

    async def sample_messages(
        self,
        messages: List[Dict[str, str]],
        parameters: Optional[SamplingParameters] = None,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from a list of messages.

        Args:
            messages: List of messages
            parameters: Optional sampling parameters
            model: Optional model to use (overrides default_model)

        Returns:
            The sampling result
        """
        # Create a context with the messages
        context = self._create_instance_context(
            messages=messages,
            parameters=parameters,
            model=model,
        )

        return await self.sample_from_context(context)

    async def sample_from_context(self, context: SamplingContext) -> SamplingResult:
        """Sample from a context.

        Args:
            context: The context to sample from

        Returns:
            The sampling result
        """
        try:
            params = context.parameters.to_dict() if context.parameters else {}

            # Add model preferences if a model is specified
            model_preferences = {}
            if context.model:
                model_preferences = {"model": context.model}

            # Convert Message objects to dictionaries if needed
            messages: List[Dict[str, Any]] = []
            for msg in context.messages:
                if hasattr(msg, "to_dict"):
                    messages.append(msg.to_dict())
                else:
                    # Fall back to a simple conversion if to_dict is not available
                    messages.append(
                        {
                            "role": getattr(msg, "role", MessageRole.USER).value,
                            "content": getattr(msg, "content", str(msg)),
                        }
                    )

            # Use the communicator to sample from the language model
            response = await self.communicator.sample_prompt(  # type: ignore
                target_service=self.target_service,
                messages=messages,
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens"),
                top_p=params.get("top_p"),
                top_k=params.get("top_k"),
                stop_sequences=params.get("stop_sequences"),
                model_preferences=model_preferences,
            )

            # Extract content from the response
            if isinstance(response, dict) and "content" in response:
                content = str(response["content"])
            else:
                content = str(response)

            # Return the sampling result
            return SamplingResult(content=content)
        except Exception as e:
            # Propagate CommunicationError as is
            if isinstance(e, CommunicationError):
                raise

            # Otherwise, wrap in a CommunicationError
            logger.exception("Error during sampling: %s", str(e))
            raise CommunicationError(f"Error during sampling: {str(e)}") from e

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
            The sampling context
        """
        params = SamplingParameters(**(parameters or {}))

        msg_list = []
        if messages:
            for msg in messages:
                role = MessageRole(msg["role"])
                content = msg["content"]
                metadata = msg.get("metadata")
                msg_list.append(
                    Message(role=role, content=content, metadata=metadata if isinstance(metadata, dict) else None)
                )

        return SamplingContext(
            system_prompt=system,
            messages=msg_list,
            parameters=params,
        )

    def _create_instance_context(
        self,
        messages: List[Dict[str, Any]],
        parameters: Optional[SamplingParameters] = None,
        model: Optional[str] = None,
    ) -> SamplingContext:
        """Create a sampling context (instance method version).

        Args:
            messages: Messages to include in the context
            parameters: Optional sampling parameters
            model: Optional model to use

        Returns:
            The sampling context
        """
        # Convert dict messages to Message objects
        msg_list: List[Message] = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                role = MessageRole(msg["role"])
                content = msg["content"]
                metadata = msg.get("metadata")
                msg_list.append(
                    Message(role=role, content=content, metadata=metadata if isinstance(metadata, dict) else None)
                )
            elif isinstance(msg, Message):  # Handle Message objects directly
                msg_list.append(msg)

        return SamplingContext(
            messages=msg_list,
            parameters=parameters or SamplingParameters(),
            model=model or self.default_model,
        )


class McpAgentSampler(BaseSampler):
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

    def _create_instance_context(
        self,
        messages: List[Dict[str, Any]],
        parameters: Optional[SamplingParameters] = None,
        model: Optional[str] = None,
    ) -> SamplingContext:
        """Create a sampling context (instance method version).

        Args:
            messages: Messages to include in the context
            parameters: Optional sampling parameters
            model: Optional model to use

        Returns:
            The sampling context
        """
        # Convert dict messages to Message objects
        msg_list: List[Message] = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                role = MessageRole(msg["role"])
                content = msg["content"]
                metadata = msg.get("metadata")
                msg_list.append(
                    Message(role=role, content=content, metadata=metadata if isinstance(metadata, dict) else None)
                )
            elif isinstance(msg, Message):  # Handle Message objects directly
                msg_list.append(msg)

        return SamplingContext(
            messages=msg_list,
            parameters=parameters or SamplingParameters(),
            model=model or self.default_model,
        )

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
            if hasattr(message, "to_dict"):
                mcp_messages.append(message.to_dict())
            else:
                mcp_messages.append(
                    {
                        "role": message.role.value,
                        "content": message.content,
                        **({"metadata": message.metadata} if message.metadata else {}),
                    }
                )

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
                model_preferences={"model": model or self.default_model} if model or self.default_model else None,
            )

            # Extract content from the response
            if isinstance(response, dict) and "content" in response:
                content = str(response["content"])
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

    async def sample_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        parameters: Optional[SamplingParameters] = None,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from a text prompt.

        Args:
            prompt: The prompt text
            system: Optional system prompt
            parameters: Optional sampling parameters
            model: Optional model to use (overrides default_model)

        Returns:
            The sampling result
        """
        # Create a context with the prompt as a user message
        messages = []

        # Add system message if provided
        if system:
            messages.append({"role": MessageRole.SYSTEM.value, "content": system})

        # Add user message
        messages.append({"role": MessageRole.USER.value, "content": prompt})

        context = self._create_instance_context(
            messages=messages,
            parameters=parameters,
            model=model,
        )

        return await self.sample_from_context(context)

    async def sample_messages(
        self,
        messages: List[Dict[str, str]],
        parameters: Optional[SamplingParameters] = None,
        model: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from a list of messages.

        Args:
            messages: List of messages
            parameters: Optional sampling parameters
            model: Optional model to use (overrides default_model)

        Returns:
            The sampling result
        """
        # Create a context with the messages
        context = self._create_instance_context(
            messages=messages,
            parameters=parameters,
            model=model,
        )

        return await self.sample_from_context(context)

    async def sample_from_context(self, context: SamplingContext) -> SamplingResult:
        """Sample from a context.

        Args:
            context: The context to sample from

        Returns:
            The sampling result
        """
        try:
            params = context.parameters.to_dict() if context.parameters else {}

            # Add model preferences if a model is specified
            model_preferences = {}
            if context.model:
                model_preferences = {"model": context.model}

            # Convert Message objects to dictionaries
            messages = []
            for msg in context.messages:
                if hasattr(msg, "to_dict"):
                    messages.append(msg.to_dict())
                else:
                    # Convert any other object to a dict with role and content
                    messages.append(
                        {"role": getattr(msg, "role", "user"), "content": getattr(msg, "content", str(msg))}
                    )

            # Use the agent to sample from the language model
            # Note: McpAgent.sample_prompt doesn't support top_p and top_k parameters
            response = await self.agent.sample_prompt(
                target_service=self.target_service,
                messages=messages,
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens"),
                stop_sequences=params.get("stop_sequences"),
                model_preferences=model_preferences,
            )

            # Extract content from the response
            if isinstance(response, dict) and "content" in response:
                content = str(response["content"])
            else:
                content = str(response)

            # Create and return a SamplingResult
            return SamplingResult(
                content=content,
                raw_response=response,
            )
        except Exception as e:
            # Propagate CommunicationError as is
            if isinstance(e, CommunicationError):
                raise

            # Otherwise, wrap in a CommunicationError
            logger.exception("Error during sampling: %s", str(e))
            raise CommunicationError(f"Error during sampling: {str(e)}") from e
