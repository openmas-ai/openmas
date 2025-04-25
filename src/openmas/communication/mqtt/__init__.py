"""MQTT communication module for OpenMAS.

This module provides MQTT-based communication capabilities for OpenMAS agents.
It is implemented as a lazy-loaded module to minimize dependencies.
"""

from typing import TYPE_CHECKING, Any

__all__ = ["MqttCommunicator"]

# For type checking only
if TYPE_CHECKING:
    from openmas.communication.mqtt.communicator import MqttCommunicator


def __getattr__(name: str) -> Any:
    """Lazily load the MQTT communicator class when requested.

    This function implements PEP 562 for lazy loading the MQTT module
    only when actually requested, avoiding unnecessary dependency imports
    when the module is not used.

    Args:
        name: The name of the attribute being accessed

    Returns:
        The requested attribute

    Raises:
        AttributeError: If the attribute doesn't exist or dependencies are missing
    """
    if name == "MqttCommunicator":
        try:
            # Only import when the attribute is accessed
            from openmas.communication.mqtt.communicator import MqttCommunicator

            return MqttCommunicator
        except ImportError as e:
            # Provide a helpful error message if dependencies are missing
            raise ImportError(
                "MQTT dependencies are not installed. " "Please install with 'pip install openmas[mqtt]'"
            ) from e

    raise AttributeError(f"module 'openmas.communication.mqtt' has no attribute '{name}'")
