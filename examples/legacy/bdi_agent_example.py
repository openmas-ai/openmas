#!/usr/bin/env python3
"""Example of a BDI agent in SimpleMAS.

This example demonstrates how to create and use a BDI agent in SimpleMAS.
It creates a simple delivery agent that has beliefs about items and their locations,
desires to deliver items, and intentions to pick up and deliver items.
"""

import argparse
import asyncio
from typing import Dict

from simple_mas.agent import BdiAgent
from simple_mas.logging import configure_logging, get_logger

logger = get_logger(__name__)


class DeliveryAgent(BdiAgent):
    """A BDI agent that delivers items from one location to another."""

    async def setup(self) -> None:
        """Set up the delivery agent.

        Initialize the agent's beliefs, desires, and register message handlers.
        """
        await super().setup()

        # Register message handlers
        await self.communicator.register_handler("delivery_request", self._handle_delivery_request)
        await self.communicator.register_handler("location_update", self._handle_location_update)

        # Initialize beliefs
        self.add_belief("location", "warehouse")
        self.add_belief("items", {"book": "warehouse", "laptop": "warehouse", "phone": "store"})
        self.add_belief("battery_level", 100)

        # Add an initial desire to check inventory
        self.add_desire("check_inventory")

        self.logger.info("Delivery agent setup complete", agent_name=self.name)

    async def _handle_delivery_request(self, params: Dict) -> Dict:
        """Handle delivery request messages.

        Args:
            params: The parameters of the request, including item and destination

        Returns:
            Response indicating whether the delivery was accepted
        """
        item = params.get("item")
        destination = params.get("destination")

        if not item or not destination:
            return {"status": "error", "message": "Missing item or destination"}

        # Check if we have the item
        items = self.get_belief("items", {})
        if item not in items:
            return {"status": "error", "message": f"Item {item} not available"}

        # Add desire to deliver the item
        desire_id = f"deliver_{item}_to_{destination}"
        self.add_desire(desire_id)

        self.logger.info(
            "Received delivery request", agent_name=self.name, item=item, destination=destination, desire=desire_id
        )

        return {"status": "accepted", "message": f"Will deliver {item} to {destination}", "desire_id": desire_id}

    async def _handle_location_update(self, params: Dict) -> Dict:
        """Handle location update messages.

        Args:
            params: The parameters of the update, including the new location

        Returns:
            Response indicating whether the update was accepted
        """
        location = params.get("location")

        if not location:
            return {"status": "error", "message": "Missing location"}

        # Update the agent's location belief
        self.add_belief("location", location)

        self.logger.info("Location updated", agent_name=self.name, location=location)

        return {"status": "success", "location": location}

    async def update_beliefs(self) -> None:
        """Update the agent's beliefs based on perception.

        In a real agent, this would involve sensing the environment.
        Here we simulate battery drain over time.
        """
        # Simulate battery drain
        battery_level = self.get_belief("battery_level", 100)
        if battery_level > 0:
            new_level = max(0, battery_level - 1)
            if new_level != battery_level:
                self.add_belief("battery_level", new_level)

                # Add a desire to recharge if battery is low
                if new_level < 20 and "recharge" not in self.get_all_desires():
                    self.add_desire("recharge")
                    self.logger.info("Battery low, need to recharge", agent_name=self.name, battery=new_level)

    async def deliberate(self) -> None:
        """Run the deliberation cycle.

        Select which desires to pursue based on current beliefs.
        """
        # Get current beliefs
        # location is unused but kept for future expansion
        _ = self.get_belief("location", "unknown")
        items = self.get_belief("items", {})
        battery_level = self.get_belief("battery_level", 0)

        # Prioritize recharging if battery is low
        if battery_level < 10 and "recharge" not in self.get_all_desires():
            self.add_desire("recharge")
            self.logger.info("Critical battery level, must recharge", agent_name=self.name, battery=battery_level)

        # Remove completed desires
        for desire in list(self.get_all_desires()):
            if desire.startswith("deliver_"):
                _, item, _, destination = desire.split("_")

                # If the item is at the destination, the desire is fulfilled
                if items.get(item) == destination:
                    self.remove_desire(desire)
                    self.logger.info("Delivery completed", agent_name=self.name, item=item, destination=destination)

    async def plan(self) -> None:
        """Generate plans for achieving selected desires.

        Create intentions (plans) to achieve the agent's current desires.
        """
        # Check if we already have intentions
        if self.get_all_intentions():
            return

        # Get current beliefs
        location = self.get_belief("location", "unknown")
        items = self.get_belief("items", {})
        battery_level = self.get_belief("battery_level", 0)

        # Prioritize recharging if it's desired
        if "recharge" in self.get_all_desires() and battery_level < 20:
            # Plan to go to charging station
            if location != "charging_station":
                self.add_intention(
                    {"id": "go_to_charging_station", "steps": [{"action": "move", "destination": "charging_station"}]}
                )
                return
            else:
                # Already at charging station, plan to recharge
                self.add_intention({"id": "recharge_battery", "steps": [{"action": "recharge", "duration": 10}]})
                return

        # Plan for item deliveries
        for desire in self.get_all_desires():
            if desire.startswith("deliver_"):
                _, item, _, destination = desire.split("_")

                # Check if we have the item
                item_location = items.get(item)
                if not item_location:
                    self.logger.warning("Item not found", agent_name=self.name, item=item)
                    continue

                # Plan to pick up the item if needed
                if item_location != location and item_location != destination:
                    self.add_intention(
                        {
                            "id": f"pickup_{item}",
                            "item": item,
                            "steps": [
                                {"action": "move", "destination": item_location},
                                {"action": "pickup", "item": item},
                            ],
                        }
                    )
                    return

                # Plan to deliver the item if we have it
                if item_location == location and location != destination:
                    self.add_intention(
                        {
                            "id": f"deliver_{item}",
                            "item": item,
                            "destination": destination,
                            "steps": [
                                {"action": "move", "destination": destination},
                                {"action": "deliver", "item": item},
                            ],
                        }
                    )
                    return

        # Plan for inventory check
        if "check_inventory" in self.get_all_desires():
            self.add_intention({"id": "inventory_check", "steps": [{"action": "inventory_check"}]})

    async def execute_intentions(self) -> None:
        """Execute the current intentions.

        Carry out the steps in the current intentions.
        """
        # Check if we have intentions
        intentions = self.get_all_intentions()
        if not intentions:
            return

        # Execute the first intention (in a real agent, we might use a priority queue)
        intention = intentions[0]
        intention_id = intention["id"]

        # Get the first step of the intention
        steps = intention.get("steps", [])
        if not steps:
            self.logger.info("Intention completed (no steps)", agent_name=self.name, intention=intention_id)
            self.remove_intention(intention_id)
            return

        step = steps[0]
        action = step.get("action")

        if action == "move":
            destination = step.get("destination")
            current_location = self.get_belief("location", "unknown")

            if current_location == destination:
                # Already at destination, remove the step
                self.logger.info("Already at destination", agent_name=self.name, destination=destination)
                intention["steps"].pop(0)
            else:
                # Simulate movement (in a real agent, this would take time)
                self.logger.info(
                    "Moving to destination",
                    agent_name=self.name,
                    from_location=current_location,
                    to_location=destination,
                )
                self.add_belief("location", destination)
                intention["steps"].pop(0)

        elif action == "pickup":
            item = step.get("item")
            items = self.get_belief("items", {})
            current_location = self.get_belief("location", "unknown")

            if items.get(item) != current_location:
                self.logger.warning(
                    "Item not at current location",
                    agent_name=self.name,
                    item=item,
                    item_location=items.get(item),
                    current_location=current_location,
                )
            else:
                # Simulate picking up the item
                self.logger.info("Picking up item", agent_name=self.name, item=item)
                # The item is now with the agent
                items[item] = "agent"
                self.add_belief("items", items)
                intention["steps"].pop(0)

        elif action == "deliver":
            item = step.get("item")
            items = self.get_belief("items", {})
            current_location = self.get_belief("location", "unknown")

            if items.get(item) != "agent":
                self.logger.warning(
                    "Agent doesn't have the item", agent_name=self.name, item=item, item_location=items.get(item)
                )
            else:
                # Simulate delivering the item
                self.logger.info("Delivering item", agent_name=self.name, item=item, location=current_location)
                # The item is now at the current location
                items[item] = current_location
                self.add_belief("items", items)
                intention["steps"].pop(0)

        elif action == "recharge":
            # duration is unused in this implementation but kept for potential future use
            _ = step.get("duration", 5)
            battery_level = self.get_belief("battery_level", 0)

            if battery_level >= 100:
                self.logger.info("Battery already full", agent_name=self.name)
                intention["steps"].pop(0)

                # Remove the recharge desire if it exists
                if "recharge" in self.get_all_desires():
                    self.remove_desire("recharge")
            else:
                # Simulate recharging (in a real agent, this would take time)
                new_level = min(100, battery_level + 20)
                self.logger.info(
                    "Recharging battery", agent_name=self.name, old_level=battery_level, new_level=new_level
                )
                self.add_belief("battery_level", new_level)

                if new_level >= 100:
                    intention["steps"].pop(0)

                    # Remove the recharge desire if it exists
                    if "recharge" in self.get_all_desires():
                        self.remove_desire("recharge")

        elif action == "inventory_check":
            # Simulate inventory check
            items = self.get_belief("items", {})
            self.logger.info("Checking inventory", agent_name=self.name, items=items)
            intention["steps"].pop(0)

            # Remove the check_inventory desire if it exists
            if "check_inventory" in self.get_all_desires():
                self.remove_desire("check_inventory")

        else:
            self.logger.warning("Unknown action", agent_name=self.name, action=action)
            intention["steps"].pop(0)

        # If all steps are completed, remove the intention
        if not intention["steps"]:
            self.logger.info("Intention completed", agent_name=self.name, intention=intention_id)
            self.remove_intention(intention_id)


async def main():
    """Run the BDI agent example."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="BDI agent example")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    args = parser.parse_args()

    # Configure logging
    configure_logging(log_level=args.log_level)

    # Create and start the agent
    agent = DeliveryAgent(name="delivery-agent")
    await agent.start()

    try:
        # Simulate a delivery request after 2 seconds
        await asyncio.sleep(2)
        logger.info("Sending delivery request to agent")
        response = await agent.communicator.send_request(
            target_service="delivery-agent", method="delivery_request", params={"item": "book", "destination": "home"}
        )
        logger.info("Delivery request response", response=response)

        # Wait for a while to see the agent in action
        logger.info("Waiting for the agent to process the delivery...")
        await asyncio.sleep(20)

    except KeyboardInterrupt:
        logger.info("Interrupted, stopping agent")
    finally:
        # Stop the agent
        await agent.stop()
        logger.info("Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
