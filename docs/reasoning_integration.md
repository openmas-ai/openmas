# Reasoning Integration in SimpleMAS

SimpleMAS focuses on providing a robust structure and communication layer for multi-agent systems, but it's designed to be extensible and integrate with various reasoning frameworks. This document explains how to integrate external reasoning engines, particularly Belief-Desire-Intention (BDI) frameworks, with SimpleMAS agents.

## BDI Architecture Overview

The Belief-Desire-Intention (BDI) model is a framework for designing intelligent agents with three key components:

1. **Beliefs**: The agent's knowledge about the world, itself, and other agents
2. **Desires**: The agent's goals or objectives that it wants to achieve
3. **Intentions**: The agent's committed plans to achieve its goals

The BDI reasoning cycle typically involves:

1. **Perception**: Updating beliefs based on sensory input
2. **Deliberation**: Selecting which desires to pursue based on current beliefs
3. **Planning**: Creating intentions (plans) to achieve selected desires
4. **Execution**: Carrying out intentions

## BDI Integration in SimpleMAS

SimpleMAS provides a `BdiAgent` base class that extends `BaseAgent` with hooks for BDI integration. This class provides:

1. Basic belief, desire, and intention management
2. A structured BDI reasoning cycle
3. Hooks for integrating external BDI frameworks

### BdiAgent Architecture

The `BdiAgent` class has the following key components:

1. **Belief Management**: Methods to add, update, and query beliefs
2. **Desire Management**: Methods to add and remove desires
3. **Intention Management**: Methods to manage intentions (plans)
4. **BDI Lifecycle Hooks**: Overridable methods for belief update, deliberation, planning, and execution
5. **Event Hooks**: Methods called when beliefs, desires, or intentions change

The BDI reasoning cycle is implemented in the `_run_bdi_cycle` method, which runs continuously while the agent is active.

### Integration with BaseAgent Lifecycle

The `BdiAgent` integrates with the `BaseAgent` lifecycle as follows:

1. **setup**: Called when the agent starts, can be used to initialize resources
2. **run**: Starts the BDI reasoning cycle and waits until the agent is stopped
3. **shutdown**: Stops the BDI reasoning cycle and cleans up resources

## Using BdiAgent

### Basic Usage

To create a simple BDI agent, subclass `BdiAgent` and override the necessary methods:

```python
from simple_mas.agent import BdiAgent

class MyBdiAgent(BdiAgent):
    async def setup(self) -> None:
        # Initialize resources, register handlers
        self.add_belief("location", "home")
        self.add_desire("go_to_work")

    async def update_beliefs(self) -> None:
        # Update beliefs based on perception
        # For example, get current location from a sensor
        current_location = await self.get_location_from_sensor()
        self.add_belief("location", current_location)

    async def deliberate(self) -> None:
        # Select desires based on beliefs
        if self.get_belief("location") == "home" and self.get_belief("time") > "08:00":
            self.add_desire("go_to_work")

    async def plan(self) -> None:
        # Create intentions to achieve desires
        if "go_to_work" in self.get_all_desires():
            self.add_intention({
                "id": "travel_to_work",
                "steps": ["get_ready", "take_bus", "arrive_at_office"]
            })

    async def execute_intentions(self) -> None:
        # Execute intentions
        for intention in self.get_all_intentions():
            if intention["id"] == "travel_to_work":
                await self.execute_travel_plan(intention["steps"])
```

### Integrating External BDI Frameworks

SimpleMAS can integrate with external BDI frameworks by:

1. Subclassing `BdiAgent`
2. Overriding the BDI lifecycle methods to integrate with the external framework
3. Synchronizing the agent's state between SimpleMAS and the external framework

#### Example: SPADE-BDI Integration

SimpleMAS includes an example integration with the SPADE-BDI framework. The `SpadeBdiAgent` class demonstrates how to:

1. Initialize a SPADE-BDI agent
2. Synchronize beliefs between SimpleMAS and SPADE-BDI
3. Map the SPADE-BDI lifecycle to the SimpleMAS BDI lifecycle

```python
from simple_mas.agent import SpadeBdiAgent

# Create a SPADE-BDI agent with an AgentSpeak (ASL) file
agent = SpadeBdiAgent(name="my-agent", asl_file_path="my_plans.asl")
await agent.start()

# Add a belief (will be synchronized to SPADE-BDI)
agent.add_belief("location", "home")

# The ASL file defines plans that react to belief changes
# For example, when the "location" belief changes, a plan might be triggered
```

## Customizing BDI Integration

### Creating a Custom BDI Integration

To integrate with another BDI framework:

1. Subclass `BdiAgent`
2. Override the BDI lifecycle methods to integrate with the external framework
3. Synchronize the agent's state between SimpleMAS and the external framework

Example:

```python
from simple_mas.agent import BdiAgent
from external_bdi_framework import ExternalBdiEngine

class CustomBdiAgent(BdiAgent):
    async def setup(self) -> None:
        await super().setup()

        # Initialize the external BDI engine
        self._external_bdi = ExternalBdiEngine()
        self._external_bdi.start()

    async def update_beliefs(self) -> None:
        # Synchronize beliefs from external perception to SimpleMAS
        external_beliefs = self._external_bdi.get_beliefs()
        for belief_name, belief_value in external_beliefs.items():
            self.add_belief(belief_name, belief_value)

    async def deliberate(self) -> None:
        # Use the external BDI engine for deliberation
        selected_desires = self._external_bdi.deliberate(self._beliefs)

        # Synchronize desires to SimpleMAS
        for desire in selected_desires:
            self.add_desire(desire)

    async def plan(self) -> None:
        # Use the external BDI engine for planning
        plans = self._external_bdi.plan(self._beliefs, self._desires)

        # Synchronize plans to SimpleMAS as intentions
        for plan in plans:
            self.add_intention(plan)

    async def execute_intentions(self) -> None:
        # Execute intentions using the external BDI engine
        for intention in self.get_all_intentions():
            self._external_bdi.execute(intention)

    async def shutdown(self) -> None:
        # Clean up the external BDI engine
        self._external_bdi.stop()
        await super().shutdown()
```

### Communication in BDI Agents

BDI agents can use the SimpleMAS `Communicator` to interact with other agents:

```python
class CommunicativeBdiAgent(BdiAgent):
    async def setup(self) -> None:
        await super().setup()

        # Register a handler for receiving messages
        await self.communicator.register_handler("receive_message", self.handle_message)

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        # Update beliefs based on received message
        self.add_belief("message_received", message)
        return {"status": "message_processed"}

    async def execute_intentions(self) -> None:
        # Example: Send a message to another agent as part of intention execution
        for intention in self.get_all_intentions():
            if intention["id"] == "inform_agent":
                await self.communicator.send_request(
                    target_service=intention["target"],
                    method="receive_message",
                    params={"content": intention["content"]}
                )
```

## Best Practices

1. **Modular Design**: Keep the BDI reasoning separate from agent-specific functionality
2. **State Synchronization**: Ensure consistent state between SimpleMAS and external frameworks
3. **Error Handling**: Handle exceptions in the BDI reasoning cycle
4. **Efficient Communication**: Use the SimpleMAS communicator for agent interaction
5. **Performance Considerations**: Adjust the deliberation cycle interval for your use case

## References

- [RAO (1995) BDI Agents: From Theory to Practice](https://cdn.aaai.org/ICMAS/1995/ICMAS95-042.pdf)
- [SPADE-BDI Documentation](https://spade-bdi.readthedocs.io/)
- [AgentSpeak Language](https://en.wikipedia.org/wiki/AgentSpeak)
