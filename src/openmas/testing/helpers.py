"""Testing helpers for OpenMAS agents.

This module provides helper functions to simplify common multi-agent testing patterns.
"""

import contextlib
import difflib
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol, Tuple, Type, TypeVar

from openmas.agent.base import BaseAgent
from openmas.logging import get_logger
from openmas.testing.harness import AgentTestHarness
from openmas.testing.mock_communicator import MockCommunicator

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseAgent)
U = TypeVar("U", bound=BaseAgent)
V = TypeVar("V", bound=BaseAgent)


# Define a protocol for objects with __getattr__ method
class HasGetAttr(Protocol):
    """Protocol for objects with __getattr__ method."""

    def __getattr__(self, name: str) -> Any:
        """Get attribute implementation."""
        pass


async def setup_sender_receiver_test(
    sender_class: Type[T],
    receiver_class: Type[U],
    sender_name: str = "sender",
    receiver_name: str = "receiver",
    sender_config: Optional[Dict[str, Any]] = None,
    receiver_config: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
) -> Tuple[AgentTestHarness[T], AgentTestHarness[U], T, U]:
    """Set up a test scenario with a sender and receiver agent.

    Creates two agent test harnesses and their corresponding agents for a
    typical sender-receiver test scenario.

    Args:
        sender_class: The sender agent class
        receiver_class: The receiver agent class
        sender_name: Name for the sender agent
        receiver_name: Name for the receiver agent
        sender_config: Optional configuration for the sender agent
        receiver_config: Optional configuration for the receiver agent
        project_root: The root directory for the agent's project files (for test isolation)

    Returns:
        A tuple of (sender_harness, receiver_harness, sender_agent, receiver_agent)
    """
    # Create test harnesses for both agents
    sender_harness = AgentTestHarness(sender_class, project_root=project_root)
    receiver_harness = AgentTestHarness(receiver_class, project_root=project_root)

    # Create the agents with their configurations
    sender_agent = await sender_harness.create_agent(name=sender_name, **(sender_config or {}))
    receiver_agent = await receiver_harness.create_agent(name=receiver_name, **(receiver_config or {}))

    # Set up both agents' communicators for direct communication
    # Link both harnesses together
    # The issue is we can't directly link sender_harness with receiver_harness
    # Instead we need to link their agents
    if hasattr(sender_agent, "communicator") and hasattr(receiver_agent, "communicator"):
        # Set up service URLs
        sender_agent.config.service_urls[receiver_name] = f"mock://{receiver_name}"
        receiver_agent.config.service_urls[sender_name] = f"mock://{sender_name}"

        # Make sure the communicators are MockCommunicators
        if isinstance(sender_agent.communicator, MockCommunicator) and isinstance(
            receiver_agent.communicator, MockCommunicator
        ):
            # Set service URLs in the communicators
            sender_agent.communicator.service_urls[receiver_name] = f"mock://{receiver_name}"
            receiver_agent.communicator.service_urls[sender_name] = f"mock://{sender_name}"

            # Link the communicators
            sender_agent.communicator.link_communicator(receiver_agent.communicator)

    return sender_harness, receiver_harness, sender_agent, receiver_agent


def expect_sender_request(
    sender_agent: BaseAgent,
    target_service: str,
    method_name: str,
    params: Dict[str, Any],
    response: Dict[str, Any],
) -> None:
    """Set up an expectation for a sender agent to make a specific request.

    This helper simplifies setting up expectations on a MockCommunicator for
    a typical request-response pattern.

    Args:
        sender_agent: The agent that will send the request
        target_service: The name of the target service to receive the request
        method_name: The method name to be called on the target service
        params: The parameters for the request
        response: The response to be returned by the mock
    """
    if not hasattr(sender_agent, "communicator") or not isinstance(sender_agent.communicator, MockCommunicator):
        raise ValueError(f"Agent {sender_agent} does not have a MockCommunicator attached")

    sender_agent.communicator.expect_request(
        target_service=target_service,
        method=method_name,
        params=params,
        response=response,
    )


def expect_notification(
    sender_agent: BaseAgent,
    target_service: str,
    method_name: str,
    params: Dict[str, Any],
) -> None:
    """Set up an expectation for a sender agent to send a specific notification.

    This helper simplifies setting up expectations on a MockCommunicator for
    a typical one-way notification pattern.

    Args:
        sender_agent: The agent that will send the notification
        target_service: The name of the target service to receive the notification
        method_name: The method name to be called on the target service
        params: The parameters for the notification
    """
    if not hasattr(sender_agent, "communicator") or not isinstance(sender_agent.communicator, MockCommunicator):
        raise ValueError(f"Agent {sender_agent} does not have a MockCommunicator attached")

    sender_agent.communicator.expect_notification(
        target_service=target_service,
        method=method_name,
        params=params,
    )


# Enhance MockCommunicator with better error messages for method typos
def _get_similar_methods(obj: Any, name: str) -> List[str]:
    """Find methods with similar names to the requested one."""
    methods = [m for m in dir(obj) if callable(getattr(obj, m)) and not m.startswith("_")]
    return difflib.get_close_matches(name, methods, n=3, cutoff=0.6)


# Patch MockCommunicator to provide better error messages
original_getattr = getattr(MockCommunicator, "__getattr__", None)


def enhanced_getattr(self: Any, name: str) -> Any:
    """Provide helpful error messages for common method errors."""
    if name == "send":
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'. "
            f"Did you mean to use 'send_request()' or 'send_notification()'?"
        )

    if original_getattr:
        return original_getattr(self, name)

    # Default behavior if no original __getattr__
    try:
        return self.__getattribute__(name)
    except AttributeError:
        similar = _get_similar_methods(self, name)
        if similar:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'. "
                f"Did you mean one of these? {', '.join(similar)}"
            )
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# Only add the method if it doesn't already exist
if not hasattr(MockCommunicator, "__getattr__"):
    setattr(MockCommunicator, "__getattr__", enhanced_getattr)


@contextlib.asynccontextmanager
async def multi_running_agents(*args: Any) -> AsyncGenerator[List[V], None]:
    """Run multiple agents in a single context manager.

    This simplifies managing the lifecycle of multiple agents in tests when using
    multiple different AgentTestHarness instances.

    Args:
        *args: Agent harnesses and agents, alternating. For each agent,
               its harness must precede it in the argument list.

    Yields:
        A list of running agents

    Example:
        ```python
        async with multi_running_agents(sender_harness, sender, receiver_harness, receiver):
            # Both agents are now running
            # Test code here
        ```
    """
    # Input validation
    if len(args) == 0:
        raise ValueError("multi_running_agents requires at least one harness-agent pair")

    if len(args) % 2 != 0:
        raise ValueError("multi_running_agents requires an even number of arguments (harness, agent pairs)")

    # Create a list to store agents
    running_agents_list: List[V] = []
    contexts = []

    try:
        # Start each agent
        for i in range(0, len(args), 2):
            harness = args[i]
            agent = args[i + 1]

            # Handle both real harnesses and mocks (for testing)
            if not (isinstance(harness, AgentTestHarness) or hasattr(harness, "running_agent")):
                raise TypeError(
                    f"Expected AgentTestHarness or mock with running_agent method, got {type(harness).__name__}"
                )

            # Use the harness's running_agent context manager
            ctx = harness.running_agent(agent)
            contexts.append(ctx)
            # Enter the context and get the running agent
            agent_instance = await ctx.__aenter__()
            running_agents_list.append(agent_instance)

        # Yield the list of running agents
        yield running_agents_list

    finally:
        # Clean up in reverse order to ensure proper shutdown
        for ctx in reversed(contexts):
            try:
                await ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error while stopping agent: {e}")
