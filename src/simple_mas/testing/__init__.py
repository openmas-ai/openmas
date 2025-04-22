"""SimpleMAS testing module.

This module provides utilities for testing SimpleMAS agents and their interactions.
"""

from simple_mas.testing.harness import AgentTestHarness
from simple_mas.testing.mock_communicator import MockCommunicator

__all__ = ["MockCommunicator", "AgentTestHarness"]
