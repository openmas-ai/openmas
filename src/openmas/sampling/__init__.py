"""OpenMAS sampling module.

This module provides sampling functionality for OpenMAS agents, allowing them
to interact with language models in a consistent way across different providers.
"""

from openmas.sampling.base import (
    Message,
    MessageRole,
    Sampler,
    SamplerProtocol,
    SamplingContext,
    SamplingParameters,
    SamplingResult,
)

__all__ = [
    "Message",
    "MessageRole",
    "Sampler",
    "SamplerProtocol",
    "SamplingContext",
    "SamplingParameters",
    "SamplingResult",
] 