"""Mock communicator for testing SimpleMAS agents.

This module provides a mock communicator that can be used for testing agents
without real network dependencies.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from simple_mas.communication.base import BaseCommunicator
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class RecordedCall:
    """Record of a call made to the communicator."""

    def __init__(
        self,
        method_name: str,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ):
        """Initialize a recorded call.

        Args:
            method_name: The name of the method that was called
            args: The positional arguments passed to the method
            kwargs: The keyword arguments passed to the method
        """
        self.method_name = method_name
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        """Return a string representation of the recorded call.

        Returns:
            A string representation
        """
        args_str = ", ".join([repr(arg) for arg in self.args])
        kwargs_str = ", ".join([f"{key}={repr(value)}" for key, value in self.kwargs.items()])

        all_args = []
        if args_str:
            all_args.append(args_str)
        if kwargs_str:
            all_args.append(kwargs_str)

        return f"{self.method_name}({', '.join(all_args)})"


class MockCommunicator(BaseCommunicator):
    """Mock communicator for testing SimpleMAS agents.

    This communicator allows setting up expected requests and predefined responses
    for testing purposes. It also records all calls made to it for later assertions.
    """

    def __init__(self, agent_name: str, service_urls: Optional[Dict[str, str]] = None):
        """Initialize the mock communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs (optional for mocking)
        """
        super().__init__(agent_name, service_urls or {})

        # Record of all calls made to this communicator
        self.calls: List[RecordedCall] = []

        # Registered handlers for incoming requests
        self._handlers: Dict[str, Callable] = {}

        # Expected requests and their responses
        self._request_responses: Dict[str, List[Dict[str, Any]]] = {}

        # Expected notifications
        self._expected_notifications: Dict[str, List[Dict[str, Any]]] = {}

        logger.debug("Initialized mock communicator", agent_name=agent_name)

    def _record_call(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        """Record a call to this communicator.

        Args:
            method_name: The name of the method that was called
            *args: The positional arguments passed to the method
            **kwargs: The keyword arguments passed to the method
        """
        self.calls.append(RecordedCall(method_name, args, kwargs))

    def reset(self) -> None:
        """Reset the mock communicator's state.

        This clears all recorded calls, expected requests/responses, and handlers.
        """
        self.calls = []
        self._handlers = {}
        self._request_responses = {}
        self._expected_notifications = {}
        logger.debug("Reset mock communicator", agent_name=self.agent_name)

    def expect_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response: Any = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Set up an expected request and its response.

        Args:
            target_service: The expected target service
            method: The expected method
            params: The expected parameters (or None to match any parameters)
            response: The response to return (ignored if exception is provided)
            exception: An exception to raise instead of returning a response

        Note:
            If multiple matching expectations exist, they will be used in the order
            they were added. If no matching expectation exists, an AssertionError
            will be raised.
        """
        key = f"{target_service}:{method}"
        if key not in self._request_responses:
            self._request_responses[key] = []

        self._request_responses[key].append(
            {
                "params": params,
                "response": response,
                "exception": exception,
            }
        )

        logger.debug(
            "Added expected request",
            target_service=target_service,
            method=method,
            params=params,
            has_response="yes" if response is not None else "no",
            has_exception="yes" if exception else "no",
        )

    def expect_notification(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Set up an expected notification.

        Args:
            target_service: The expected target service
            method: The expected method
            params: The expected parameters (or None to match any parameters)
            exception: An exception to raise when this notification is sent

        Note:
            If multiple matching expectations exist, they will be used in the order
            they were added. If no matching expectation exists, an AssertionError
            will be raised.
        """
        key = f"{target_service}:{method}"
        if key not in self._expected_notifications:
            self._expected_notifications[key] = []

        self._expected_notifications[key].append(
            {
                "params": params,
                "exception": exception,
            }
        )

        logger.debug(
            "Added expected notification",
            target_service=target_service,
            method=method,
            params=params,
            has_exception="yes" if exception else "no",
        )

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a mock request and return the predefined response.

        Args:
            target_service: The name of the service to send the request to
            method: The method to call on the service
            params: The parameters to pass to the method
            response_model: Optional Pydantic model to validate and parse the response
            timeout: Optional timeout in seconds (ignored in mock)

        Returns:
            The predefined response for this request

        Raises:
            AssertionError: If no matching expectation was found
            Exception: If a predefined exception was set for this request
        """
        self._record_call("send_request", target_service, method, params, response_model, timeout)

        key = f"{target_service}:{method}"

        if key not in self._request_responses or not self._request_responses[key]:
            available = ", ".join([k for k in self._request_responses.keys() if self._request_responses[k]])
            raise AssertionError(
                f"Unexpected request: {target_service}:{method} with params: {params}.\n"
                f"Available requests: {available or 'none'}"
            )

        # Get the next expectation for this request
        expectation = self._request_responses[key][0]

        # Check if parameters match (if provided)
        expected_params = expectation["params"]
        if expected_params is not None and expected_params != params:
            # Keep the expectation and raise an error
            raise AssertionError(
                f"Parameter mismatch for {target_service}:{method}\n"
                f"Expected: {expected_params}\n"
                f"Received: {params}"
            )

        # Remove this expectation since it's been used
        self._request_responses[key].pop(0)

        # If an exception was set, raise it
        if expectation["exception"]:
            raise expectation["exception"]

        # Return the response (validating if a model was provided)
        response = expectation["response"]
        if response_model is not None and response is not None:
            return response_model.parse_obj(response)
        return response

    async def send_notification(
        self, target_service: str, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a mock notification.

        Args:
            target_service: The name of the service to send the notification to
            method: The method to call on the service
            params: The parameters to pass to the method

        Raises:
            AssertionError: If no matching expectation was found
            Exception: If a predefined exception was set for this notification
        """
        self._record_call("send_notification", target_service, method, params)

        key = f"{target_service}:{method}"

        if key not in self._expected_notifications or not self._expected_notifications[key]:
            available = ", ".join([k for k in self._expected_notifications.keys() if self._expected_notifications[k]])
            raise AssertionError(
                f"Unexpected notification: {target_service}:{method} with params: {params}.\n"
                f"Available notifications: {available or 'none'}"
            )

        # Get the next expectation for this notification
        expectation = self._expected_notifications[key][0]

        # Check if parameters match (if provided)
        expected_params = expectation["params"]
        if expected_params is not None and expected_params != params:
            # Keep the expectation and raise an error
            raise AssertionError(
                f"Parameter mismatch for {target_service}:{method}\n"
                f"Expected: {expected_params}\n"
                f"Received: {params}"
            )

        # Remove this expectation since it's been used
        self._expected_notifications[key].pop(0)

        # If an exception was set, raise it
        if expectation["exception"]:
            raise expectation["exception"]

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self._record_call("register_handler", method, handler)
        self._handlers[method] = handler
        logger.debug("Registered handler", agent_name=self.agent_name, method=method)

    async def trigger_handler(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Trigger a registered handler with the given parameters.

        This method is specific to the mock communicator and allows testing
        how an agent responds to incoming requests.

        Args:
            method: The method to trigger
            params: The parameters to pass to the handler

        Returns:
            The result of the handler call

        Raises:
            AssertionError: If no handler has been registered for the method
        """
        if method not in self._handlers:
            available = ", ".join(self._handlers.keys())
            raise AssertionError(
                f"No handler registered for method: {method}.\n" f"Available handlers: {available or 'none'}"
            )

        handler = self._handlers[method]
        result = await handler(params or {})
        return result

    def verify_all_expectations_met(self) -> None:
        """Verify that all expected requests and notifications have been met.

        Raises:
            AssertionError: If any expected requests or notifications haven't been matched
        """
        unmet_requests = {}
        for key, expectations in self._request_responses.items():
            if expectations:
                unmet_requests[key] = len(expectations)

        unmet_notifications = {}
        for key, expectations in self._expected_notifications.items():
            if expectations:
                unmet_notifications[key] = len(expectations)

        if unmet_requests or unmet_notifications:
            msg = []
            if unmet_requests:
                req_list = ", ".join([f"{k} ({v})" for k, v in unmet_requests.items()])
                msg.append(f"Unmet request expectations: {req_list}")
            if unmet_notifications:
                notif_list = ", ".join([f"{k} ({v})" for k, v in unmet_notifications.items()])
                msg.append(f"Unmet notification expectations: {notif_list}")

            raise AssertionError("\n".join(msg))

    def verify(self) -> None:
        """Alias for verify_all_expectations_met() for backwards compatibility.

        Raises:
            AssertionError: If any expected requests or notifications haven't been matched
        """
        self.verify_all_expectations_met()

    def expect_request_exception(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Alias for expect_request with exception parameter for backwards compatibility.

        Args:
            target_service: The expected target service
            method: The expected method
            params: The expected parameters (or None to match any parameters)
            exception: An exception to raise when this request is received
        """
        self.expect_request(target_service, method, params, None, exception)

    async def start(self) -> None:
        """Start the mock communicator.

        This method records the call but doesn't perform any actions.
        """
        self._record_call("start")
        logger.debug("Started mock communicator", agent_name=self.agent_name)

    async def stop(self) -> None:
        """Stop the mock communicator.

        This method records the call but doesn't perform any actions.
        """
        self._record_call("stop")
        logger.debug("Stopped mock communicator", agent_name=self.agent_name)
