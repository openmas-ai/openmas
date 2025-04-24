"""Pattern implementations for SimpleMAS.

This module provides implementations of common patterns for multi-agent systems,
such as Orchestrator-Worker, Pub-Sub, etc.
"""

from simple_mas.patterns.chaining import (
    ChainBuilder,
    ChainResult,
    ChainStep,
    ChainStepResult,
    ChainStepStatus,
    ServiceChain,
    create_chain,
    execute_chain,
)
from simple_mas.patterns.orchestrator import (
    BaseOrchestratorAgent,
    BaseWorkerAgent,
    TaskHandler,
    TaskRequest,
    TaskResult,
    WorkerInfo,
)
from simple_mas.patterns.routing import (  # type: ignore
    Route,
    RouteMatch,
    Router,
    RouteResult,
    RouteType,
    RoutingAgent,
    create_router,
    route_condition,
    route_content,
    route_default,
    route_forward,
    route_method,
    route_param,
    route_param_regex,
)

__all__ = [
    # Orchestrator-Worker Pattern
    "BaseOrchestratorAgent",
    "BaseWorkerAgent",
    "TaskHandler",
    "TaskRequest",
    "TaskResult",
    "WorkerInfo",
    # Chaining Pattern
    "ServiceChain",
    "ChainBuilder",
    "ChainStep",
    "ChainStepResult",
    "ChainResult",
    "ChainStepStatus",
    "create_chain",
    "execute_chain",
    # Routing Pattern
    "Router",
    "Route",
    "RouteMatch",
    "RouteResult",
    "RouteType",
    "RoutingAgent",
    "create_router",
    "route_method",
    "route_param",
    "route_param_regex",
    "route_content",
    "route_condition",
    "route_forward",
    "route_default",
]
