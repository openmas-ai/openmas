# OpenMAS MQTT Communicator Example

This directory contains an example implementation of a custom communicator for OpenMAS using the MQTT protocol. It demonstrates how to create and use a plugin for the OpenMAS communication layer.

## Files

- `mqtt_communicator.py`: The main implementation of the `MqttCommunicator` class
- `setup.py`: Example setup script with entry point registration
- `mqtt_example.py`: Example usage of the MQTT communicator

## Installation

To install the MQTT communicator as a plugin:

```bash
# Install the dependencies
pip install asyncio-mqtt

# Install the package in development mode
pip install -e .
```

## Usage

Once installed, you can use the MQTT communicator in your OpenMAS agents:

```python
from openmas.agent import BaseAgent
from openmas.config import AgentConfig

agent = BaseAgent(
    name="my-agent",
    config=AgentConfig(
        name="my-agent",
        communicator_type="mqtt",  # Use "mqtt" as the communicator type
        communicator_options={
            "broker_host": "localhost",
            "broker_port": 1883,
            "client_id": "my-custom-id"  # Optional
        },
        service_urls={
            "other_service": "other_service_name"  # MQTT topic prefix
        }
    )
)
```

## Example

To run the example:

1. Start an MQTT broker (e.g., Mosquitto):
   ```bash
   mosquitto -v
   ```

2. Run the example script:
   ```bash
   python mqtt_example.py
   ```

## Implementation Details

The MQTT communicator implements these key features:

- Connection to an MQTT broker
- Request/response handling over MQTT topics
- Notification support
- Timeout handling for requests
- Error handling with JSON-RPC style responses

## Plugin System Integration

This example demonstrates two ways to integrate with OpenMAS's plugin system:

1. **Entry Points**: Using `setup.py` to register the communicator via entry points
2. **Direct Registration**: Manual registration with `register_communicator()`

The entry point registration is the recommended approach for third-party packages, as it allows OpenMAS to automatically discover and load the communicator when the package is installed.
