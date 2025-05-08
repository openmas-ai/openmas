"""Sampling utilities for OpenMAS.

This module provides utilities for sampling from language models, which is a core
capability for OpenMAS agents. It includes a factory function for creating samplers
based on configuration.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from openmas.communication.base import BaseCommunicator
from openmas.exceptions import ConfigurationError
from openmas.logging import get_logger
from openmas.sampling.base import BaseSampler, Message, MessageRole, SamplingContext, SamplingParameters, SamplingResult

logger = get_logger(__name__)


def get_sampler(
    communicator: BaseCommunicator,
    params: Optional[SamplingParameters] = None,
    **kwargs: Any,
) -> BaseSampler:
    """Get a sampler based on the parameters.

    This function creates an appropriate sampler based on the sampling parameters.
    It delegates to provider-specific samplers as needed.

    Args:
        communicator: The communicator to use for sampling
        params: The sampling parameters
        **kwargs: Additional arguments for the sampler

    Returns:
        A sampler instance

    Raises:
        ConfigurationError: If the parameters are invalid or the provider is not supported
    """
    if not params:
        # If no parameters provided, use defaults
        params = SamplingParameters()

    # Create a sampler based on the provider
    if params.provider is None or params.provider.lower() == "default":
        # Default sampler uses the base BaseSampler class with the provided communicator
        return BaseSampler(communicator=communicator)

    elif params.provider.lower() == "mcp":
        # Import here to avoid circular imports
        from openmas.sampling.providers.mcp import McpSampler

        # Create an MCP sampler with the provided communicator and parameters
        return McpSampler(communicator=communicator, params=params)

    elif params.provider.lower() == "mock":
        import logging

        class MockSampler(BaseSampler):
            def __init__(self, communicator: BaseCommunicator, params: SamplingParameters) -> None:
                super().__init__(communicator=communicator)
                self.params = params
                self.logger = logging.getLogger("MockSampler")

            async def sample(self, context: SamplingContext, model: Any = None) -> SamplingResult:
                self.logger.info(f"Mock sampling with context: {context.to_dict()} and params: {self.params.to_dict()}")
                return SamplingResult(content="<mocked sample response>")

        return MockSampler(communicator=communicator, params=params)

    else:
        # Provider not supported or recognized
        raise ConfigurationError(f"Unsupported sampling provider: {params.provider}")


# Re-export important types
__all__ = [
    "BaseSampler",
    "Message",
    "MessageRole",
    "SamplingContext",
    "SamplingParameters",
    "SamplingResult",
    "get_sampler",
]
