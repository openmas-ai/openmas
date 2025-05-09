"""BDI agent implementation for OpenMAS.

This module provides a base class for implementing BDI (Belief-Desire-Intention) agents
in OpenMAS. It extends the BaseAgent class with hooks for beliefs, desires, and
intentions management.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from openmas.agent.base import BaseAgent
from openmas.assets.manager import AssetManager
from openmas.config import AgentConfig
from openmas.logging import get_logger

logger = get_logger(__name__)


class BdiAgent(BaseAgent):
    """Base agent class for BDI agents in OpenMAS.

    This class extends BaseAgent with hooks for belief-desire-intention (BDI)
    reasoning cycles. It is designed to be agnostic to specific BDI implementations
    while providing a structured framework for integrating external BDI libraries.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        config_model: Type[AgentConfig] = AgentConfig,
        env_prefix: str = "",
        bdi_enabled: bool = True,
        deliberation_cycle_interval: float = 0.1,
        project_root: Optional[Path] = None,
        asset_manager: Optional[AssetManager] = None,
    ) -> None:
        """Initialize the BDI agent.

        Args:
            name: The name of the agent (overrides config)
            config: The agent configuration
            config_model: The configuration model class to use
            env_prefix: Optional prefix for environment variables
            bdi_enabled: Whether BDI reasoning is enabled
            deliberation_cycle_interval: Interval between deliberation cycles (in seconds)
            project_root: The project root directory for resolving prompt/template files
            asset_manager: The asset manager for accessing required assets
        """
        super().__init__(
            name=name,
            config=config,
            config_model=config_model,
            env_prefix=env_prefix,
            project_root=project_root,
            asset_manager=asset_manager,
        )

        # BDI state
        self._beliefs: Dict[str, Any] = {}
        self._desires: Set[str] = set()
        self._intentions: List[Dict[str, Any]] = []
        self._bdi_enabled = bdi_enabled
        self._deliberation_cycle_interval = deliberation_cycle_interval
        self._bdi_task: Optional[asyncio.Task] = None

        self.logger.info(
            "Initialized BDI agent",
            agent_name=self.name,
            bdi_enabled=bdi_enabled,
            cycle_interval=deliberation_cycle_interval,
        )

    # Belief management methods
    def add_belief(self, belief_name: str, belief_value: Any) -> None:
        """Add or update a belief.

        Args:
            belief_name: The name of the belief
            belief_value: The value of the belief
        """
        self._beliefs[belief_name] = belief_value
        self.logger.debug("Added belief", agent_name=self.name, belief=belief_name, value=belief_value)
        asyncio.create_task(self.on_belief_change(belief_name, belief_value))

    def remove_belief(self, belief_name: str) -> None:
        """Remove a belief.

        Args:
            belief_name: The name of the belief
        """
        if belief_name in self._beliefs:
            del self._beliefs[belief_name]
            self.logger.debug("Removed belief", agent_name=self.name, belief=belief_name)
            asyncio.create_task(self.on_belief_change(belief_name, None))

    def get_belief(self, belief_name: str, default: Any = None) -> Any:
        """Get the value of a belief.

        Args:
            belief_name: The name of the belief
            default: Default value if belief doesn't exist

        Returns:
            The value of the belief or the default value
        """
        return self._beliefs.get(belief_name, default)

    def get_all_beliefs(self) -> Dict[str, Any]:
        """Get all beliefs.

        Returns:
            A dictionary of all beliefs
        """
        return self._beliefs.copy()

    # Desire management methods
    def add_desire(self, desire: str) -> None:
        """Add a desire.

        Args:
            desire: The desire to add
        """
        self._desires.add(desire)
        self.logger.debug("Added desire", agent_name=self.name, desire=desire)
        asyncio.create_task(self.on_desire_change(desire, True))

    def remove_desire(self, desire: str) -> None:
        """Remove a desire.

        Args:
            desire: The desire to remove
        """
        if desire in self._desires:
            self._desires.remove(desire)
            self.logger.debug("Removed desire", agent_name=self.name, desire=desire)
            asyncio.create_task(self.on_desire_change(desire, False))

    def get_all_desires(self) -> Set[str]:
        """Get all desires.

        Returns:
            A set of all desires
        """
        return self._desires.copy()

    # Intention management methods
    def add_intention(self, intention: Dict[str, Any]) -> None:
        """Add an intention.

        Args:
            intention: The intention to add, typically a dictionary with at least an "id" key
        """
        self._intentions.append(intention)
        self.logger.debug("Added intention", agent_name=self.name, intention=intention)
        asyncio.create_task(self.on_intention_change(intention, True))

    def remove_intention(self, intention_id: str) -> None:
        """Remove an intention.

        Args:
            intention_id: The ID of the intention to remove
        """
        for i, intention in enumerate(self._intentions):
            if intention.get("id") == intention_id:
                removed = self._intentions.pop(i)
                self.logger.debug("Removed intention", agent_name=self.name, intention=removed)
                asyncio.create_task(self.on_intention_change(removed, False))
                break

    def get_all_intentions(self) -> List[Dict[str, Any]]:
        """Get all intentions.

        Returns:
            A list of all intentions
        """
        return self._intentions.copy()

    # BDI lifecycle hooks (to be overridden by subclasses)
    async def update_beliefs(self) -> None:
        """Update the agent's beliefs based on perception.

        This method should be overridden by subclasses to implement
        perception and belief update logic.
        """
        pass

    async def deliberate(self) -> None:
        """Run the deliberation cycle.

        This method should be overridden by subclasses to implement
        the agent's decision-making process, selecting which desires
        to pursue based on current beliefs.
        """
        pass

    async def plan(self) -> None:
        """Generate plans for achieving selected desires.

        This method should be overridden by subclasses to implement
        the agent's planning process, creating intentions (plans) to
        achieve selected desires.
        """
        pass

    async def execute_intentions(self) -> None:
        """Execute the current intentions.

        This method should be overridden by subclasses to implement
        the actual execution of intentions.
        """
        pass

    # Event hooks
    async def on_belief_change(self, belief_name: str, belief_value: Any) -> None:
        """Called when a belief is added, updated, or removed.

        This method can be overridden to react to belief changes.

        Args:
            belief_name: The name of the belief that changed
            belief_value: The new value of the belief, or None if removed
        """
        pass

    async def on_desire_change(self, desire: str, added: bool) -> None:
        """Called when a desire is added or removed.

        This method can be overridden to react to desire changes.

        Args:
            desire: The desire that changed
            added: True if added, False if removed
        """
        pass

    async def on_intention_change(self, intention: Dict[str, Any], added: bool) -> None:
        """Called when an intention is added or removed.

        This method can be overridden to react to intention changes.

        Args:
            intention: The intention that changed
            added: True if added, False if removed
        """
        pass

    # BDI reasoning cycle
    async def _run_bdi_cycle(self) -> None:
        """Run the BDI reasoning cycle.

        This method runs the main BDI loop, consisting of:
        1. Perception and belief update
        2. Deliberation (desire selection)
        3. Planning (intention selection)
        4. Intention execution
        """
        self.logger.info("Starting BDI reasoning cycle", agent_name=self.name)

        while self._bdi_enabled:
            try:
                # Step 1: Update beliefs based on perception
                await self.update_beliefs()

                # Step 2: Deliberate (select desires based on beliefs)
                await self.deliberate()

                # Step 3: Plan (create intentions to achieve desires)
                await self.plan()

                # Step 4: Execute intentions
                await self.execute_intentions()

                # Wait before next cycle
                await asyncio.sleep(self._deliberation_cycle_interval)

            except asyncio.CancelledError:
                self.logger.info("BDI reasoning cycle cancelled", agent_name=self.name)
                break
            except Exception as e:
                self.logger.exception("Error in BDI reasoning cycle", agent_name=self.name, error=str(e))
                await asyncio.sleep(self._deliberation_cycle_interval)

    # BaseAgent lifecycle methods
    async def setup(self) -> None:
        """Set up the BDI agent.

        This method is called when the agent starts and can be used to initialize
        resources, register handlers, etc.
        """
        pass

    async def run(self) -> None:
        """Run the BDI agent's main loop.

        This method starts the BDI reasoning cycle and runs until the agent is stopped.
        """
        if self._bdi_enabled:
            self._bdi_task = asyncio.create_task(self._run_bdi_cycle())

        # Wait forever (or until cancelled)
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            # Clean up BDI task if it's running
            if self._bdi_task is not None and not self._bdi_task.done():
                self._bdi_task.cancel()
                try:
                    await self._bdi_task
                except asyncio.CancelledError:
                    pass
            raise

    async def shutdown(self) -> None:
        """Shut down the BDI agent.

        This method is called when the agent stops and can be used to clean up
        resources, close connections, etc.
        """
        # Stop BDI reasoning cycle if it's running
        if self._bdi_task is not None and not self._bdi_task.done():
            self._bdi_task.cancel()
            try:
                # Wait for the task to be cancelled
                await asyncio.wait_for(asyncio.shield(self._bdi_task), timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                # Expected exceptions
                pass
            self._bdi_task = None

        # Instead of calling superclass shutdown which could be abstract,
        # explicitly implement any shutdown actions needed
        # The base class BaseAgent's shutdown is abstract, so implement it here
        self.logger.info("BDI agent shutdown complete", agent_name=self.name)
