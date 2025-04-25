"""Chaining pattern helpers for OpenMAS.

This module provides helper classes and functions for implementing the Chaining pattern
in a multi-agent system. The pattern consists of:

1. A sequence of service calls that are executed in order
2. Results from earlier calls can be passed to later calls
3. Error handling and optional retry mechanisms

This pattern is useful when a workflow needs to execute a series of steps in a defined
order, where each step may depend on the result of previous steps.
"""

import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from openmas.logging import get_logger

logger = get_logger(__name__)


class ChainStepStatus(str, Enum):
    """Status of a chain step execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class ChainStep(BaseModel):
    """A step in a service call chain."""

    target_service: str
    method: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    transform_input: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    transform_output: Optional[Callable[[Any], Any]] = None
    error_handler: Optional[Callable[[Exception, Dict[str, Any]], Any]] = None


class ChainStepResult(BaseModel):
    """Result of a chain step execution."""

    step: ChainStep
    status: ChainStepStatus
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    attempt_count: int = 0


class ChainResult(BaseModel):
    """Result of a chain execution."""

    results: List[ChainStepResult] = Field(default_factory=list)
    final_result: Any = None
    successful: bool = True
    execution_time: float = 0.0


class ServiceChain:
    """A chain of service calls that can be executed sequentially.

    The ServiceChain allows defining a sequence of API calls to different services,
    with the ability to pass data between steps, transform inputs/outputs, apply
    conditions, retry logic, and error handling.
    """

    def __init__(self, communicator: Any, name: str = "service_chain"):
        """Initialize the ServiceChain.

        Args:
            communicator: The communicator to use for service calls
            name: Name of this chain for logging purposes
        """
        self.communicator = communicator
        self.name = name
        self.steps: List[ChainStep] = []
        self.logger = logger.bind(chain_name=name)

    def add_step(
        self,
        target_service: str,
        method: str,
        parameters: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        retry_count: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        transform_input: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        transform_output: Optional[Callable[[Any], Any]] = None,
        error_handler: Optional[Callable[[Exception, Dict[str, Any]], Any]] = None,
    ) -> "ServiceChain":
        """Add a step to the chain.

        Args:
            target_service: The target service for this step
            method: The method to call on the service
            parameters: Parameters to pass to the method
            name: Optional name for this step
            retry_count: Number of times to retry on failure
            retry_delay: Delay between retries in seconds
            timeout: Timeout for this step in seconds
            condition: Optional condition function to determine if this step should execute
            transform_input: Optional function to transform input parameters
            transform_output: Optional function to transform the output
            error_handler: Optional function to handle errors

        Returns:
            The chain instance for method chaining
        """
        step = ChainStep(
            target_service=target_service,
            method=method,
            parameters=parameters or {},
            name=name or f"{target_service}.{method}",
            retry_count=retry_count,
            retry_delay=retry_delay,
            timeout=timeout,
            condition=condition,
            transform_input=transform_input,
            transform_output=transform_output,
            error_handler=error_handler,
        )
        self.steps.append(step)
        return self

    async def execute(self, initial_context: Optional[Dict[str, Any]] = None) -> ChainResult:
        """Execute the chain of service calls.

        Args:
            initial_context: Optional initial context data

        Returns:
            Result of the chain execution
        """
        context = initial_context or {}
        chain_result = ChainResult()

        # Track execution time
        start_time = asyncio.get_event_loop().time()

        # Execute steps sequentially
        for step in self.steps:
            step_result = await self._execute_step(step, context)
            chain_result.results.append(step_result)

            # Add result to context for next steps
            if step.name is not None:
                context[step.name] = step_result.result

            # Exit early if a step failed and no error handler recovered
            if step_result.status == ChainStepStatus.FAILURE:
                chain_result.successful = False
                break

        # Calculate total execution time
        chain_result.execution_time = asyncio.get_event_loop().time() - start_time

        # Set the final result to the result of the last successful step
        for step_result in reversed(chain_result.results):
            if step_result.status == ChainStepStatus.SUCCESS:
                chain_result.final_result = step_result.result
                break

        return chain_result

    async def _execute_step(self, step: ChainStep, context: Dict[str, Any]) -> ChainStepResult:
        """Execute a single step in the chain.

        Args:
            step: The step to execute
            context: The current context with results from previous steps

        Returns:
            Result of the step execution
        """
        result = ChainStepResult(step=step, status=ChainStepStatus.PENDING)

        # Check condition
        if step.condition is not None and not step.condition(context):
            result.status = ChainStepStatus.SKIPPED
            self.logger.info(f"Step {step.name} skipped due to condition", step=step.name)
            return result

        # Track execution time
        start_time = asyncio.get_event_loop().time()
        result.status = ChainStepStatus.IN_PROGRESS

        # Prepare parameters with context
        parameters = self._prepare_parameters(step, context)

        # Execute with retry logic
        attempt = 0
        while True:
            attempt += 1
            result.attempt_count = attempt

            try:
                response = await self.communicator.send_request(
                    target_service=step.target_service,
                    method=step.method,
                    params=parameters,
                    timeout=step.timeout,
                )

                # Process successful response
                if step.transform_output:
                    response = step.transform_output(response)

                result.result = response
                result.status = ChainStepStatus.SUCCESS
                result.execution_time = asyncio.get_event_loop().time() - start_time

                self.logger.debug(
                    f"Step {step.name} executed successfully",
                    step=step.name,
                    attempt=attempt,
                    execution_time=result.execution_time,
                )
                break

            except Exception as e:
                # Handle error
                if step.error_handler:
                    try:
                        # Try to recover with the error handler
                        recovery_result = step.error_handler(e, context)
                        result.result = recovery_result
                        result.status = ChainStepStatus.SUCCESS
                        result.execution_time = asyncio.get_event_loop().time() - start_time

                        self.logger.info(
                            f"Step {step.name} recovered from error with handler",
                            step=step.name,
                            error=str(e),
                            attempt=attempt,
                        )
                        break
                    except Exception as recovery_error:
                        # Error handler failed
                        self.logger.warning(
                            f"Error handler for step {step.name} failed",
                            step=step.name,
                            error=str(recovery_error),
                        )

                # Check if we should retry
                if attempt <= step.retry_count:
                    self.logger.info(
                        f"Retrying step {step.name} after error (attempt {attempt}/{step.retry_count})",
                        step=step.name,
                        error=str(e),
                        attempt=attempt,
                        retry_delay=step.retry_delay,
                    )
                    await asyncio.sleep(step.retry_delay)
                    continue

                # No more retries, mark as failed
                result.status = ChainStepStatus.FAILURE
                result.error = str(e)
                result.execution_time = asyncio.get_event_loop().time() - start_time

                self.logger.error(
                    f"Step {step.name} failed after {attempt} attempts",
                    step=step.name,
                    error=str(e),
                    attempt=attempt,
                )
                break

        return result

    def _prepare_parameters(self, step: ChainStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare parameters for a step, incorporating context data.

        Args:
            step: The step being executed
            context: The current context with results from previous steps

        Returns:
            The prepared parameters
        """
        # Start with the step's defined parameters
        parameters = step.parameters.copy()

        # Look for placeholders in the parameters to substitute with context values
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$"):
                context_key = value[1:]
                if context_key in context:
                    parameters[key] = context[context_key]

        # Apply transform_input if defined
        if step.transform_input:
            parameters = step.transform_input(context)

        return parameters


class ChainBuilder:
    """A builder for creating and executing service chains.

    This builder provides a fluent interface for constructing service chains.
    """

    def __init__(self, communicator: Any, name: str = "service_chain"):
        """Initialize the ChainBuilder.

        Args:
            communicator: The communicator to use for service calls
            name: Name of this chain for logging purposes
        """
        self.chain = ServiceChain(communicator, name)

    def add_step(
        self,
        target_service: str,
        method: str,
        parameters: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        retry_count: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        transform_input: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        transform_output: Optional[Callable[[Any], Any]] = None,
        error_handler: Optional[Callable[[Exception, Dict[str, Any]], Any]] = None,
    ) -> "ChainBuilder":
        """Add a step to the chain.

        Args:
            target_service: The target service for this step
            method: The method to call on the service
            parameters: Parameters to pass to the method
            name: Optional name for this step
            retry_count: Number of times to retry on failure
            retry_delay: Delay between retries in seconds
            timeout: Timeout for this step in seconds
            condition: Optional condition function to determine if this step should execute
            transform_input: Optional function to transform input parameters
            transform_output: Optional function to transform the output
            error_handler: Optional function to handle errors

        Returns:
            The builder instance for method chaining
        """
        self.chain.add_step(
            target_service=target_service,
            method=method,
            parameters=parameters,
            name=name,
            retry_count=retry_count,
            retry_delay=retry_delay,
            timeout=timeout,
            condition=condition,
            transform_input=transform_input,
            transform_output=transform_output,
            error_handler=error_handler,
        )
        return self

    def build(self) -> ServiceChain:
        """Build and return the service chain.

        Returns:
            The constructed service chain
        """
        return self.chain

    async def execute(self, initial_context: Optional[Dict[str, Any]] = None) -> ChainResult:
        """Build and execute the service chain.

        Args:
            initial_context: Optional initial context data

        Returns:
            Result of the chain execution
        """
        return await self.chain.execute(initial_context)


# Example usage of the Chaining pattern

"""
async def example_usage(communicator):
    # Create a chain builder
    chain = ChainBuilder(communicator, name="weather_forecast_chain")

    # Add steps to the chain
    chain.add_step(
        target_service="auth_service",
        method="authenticate",
        parameters={"api_key": "my_api_key"},
        name="auth",
        retry_count=2,
    )

    chain.add_step(
        target_service="location_service",
        method="get_coordinates",
        parameters={"city": "New York"},
        name="location",
        transform_output=lambda resp: resp.get("coordinates"),
    )

    chain.add_step(
        target_service="weather_service",
        method="get_forecast",
        parameters={},
        name="forecast",
        transform_input=lambda ctx: {
            "coordinates": ctx["location"],
            "auth_token": ctx["auth"]["token"],
        },
    )

    # Execute the chain
    result = await chain.execute()

    if result.successful:
        print(f"Final result: {result.final_result}")
    else:
        print(f"Chain execution failed: {result.results[-1].error}")
"""

# Function for creating reusable chains


def create_chain(communicator: Any, name: str = "service_chain") -> ChainBuilder:
    """Create a new service chain builder.

    Args:
        communicator: The communicator to use for service calls
        name: Name of this chain for logging purposes

    Returns:
        A new chain builder
    """
    return ChainBuilder(communicator, name)


async def execute_chain(
    communicator: Any,
    steps: List[Dict[str, Any]],
    initial_context: Optional[Dict[str, Any]] = None,
    name: str = "service_chain",
) -> ChainResult:
    """Execute a chain of service calls defined by steps.

    This is a convenience function for creating and executing a chain in a single call.

    Args:
        communicator: The communicator to use for service calls
        steps: List of step definitions, each a dict with parameters for add_step
        initial_context: Optional initial context data
        name: Name of this chain for logging purposes

    Returns:
        Result of the chain execution
    """
    builder = ChainBuilder(communicator, name)

    for step_def in steps:
        builder.add_step(**step_def)

    return await builder.execute(initial_context)
