"""SimpleMAS testing module.

This module provides utilities for testing SimpleMAS agents and their interactions.
"""

from simple_mas.communication.base import register_communicator
from simple_mas.testing.harness import AgentTestHarness
from simple_mas.testing.mock_communicator import MockCommunicator

# Register the MockCommunicator type for testing
register_communicator("mock", MockCommunicator)

__all__ = ["MockCommunicator", "AgentTestHarness"]
