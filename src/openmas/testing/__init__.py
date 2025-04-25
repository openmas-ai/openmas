"""OpenMAS testing module.

This module provides utilities for testing OpenMAS agents and their interactions.
"""

from openmas.communication.base import register_communicator
from openmas.testing.harness import AgentTestHarness
from openmas.testing.mock_communicator import MockCommunicator

# Register the MockCommunicator type for testing
register_communicator("mock", MockCommunicator)

__all__ = ["MockCommunicator", "AgentTestHarness"]
