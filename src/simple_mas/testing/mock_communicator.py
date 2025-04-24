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

        # Record of sent messages for testing
        self._sent_messages: List[Any] = []

        # Linked communicators for direct communication
        self._linked_communicators: List["MockCommunicator"] = []

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
        self._sent_messages = []
        self._linked_communicators = []
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

        # Store the message for inspection in tests
        message = {
            "sender_id": self.agent_name,
            "recipient_id": target_service,
            "content": params or {},
            "message_type": method,
        }
        self._sent_messages.append(message)

        # Check if we should forward this message to linked communicators
        for linked_comm in self._linked_communicators:
            if linked_comm.agent_name == target_service:
                # If the linked communicator is the intended recipient, trigger its handler
                await linked_comm.trigger_handler(method, params)

        key = f"{target_service}:{method}"

        # Check if we have expectations set up
        if key in self._expected_notifications and self._expected_notifications[key]:
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
        logger.debug(
            "Registered handler for method",
            agent_name=self.agent_name,
            method=method,
            handler=handler.__qualname__,
        )

    async def trigger_handler(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Trigger a registered handler with the given parameters.

        This method is used for testing to simulate incoming messages.

        Args:
            method: The method name to trigger
            params: The parameters to pass to the handler

        Returns:
            The return value from the handler, if any

        Raises:
            KeyError: If no handler is registered for the method
        """
        if method not in self._handlers:
            raise KeyError(f"No handler registered for method '{method}'")

        handler = self._handlers[method]

        # Create a message dictionary to pass to the handler
        message = {
            "sender_id": "test_sender"
            if not params or not isinstance(params, dict)
            else params.get("sender_id", "test_sender"),
            "recipient_id": self.agent_name,
            "content": params or {},
            "message_type": method,
            "conversation_id": None,
            "get": lambda key, default=None: (params or {}).get(key, default) if isinstance(params, dict) else default,
        }

        return await handler(message)

    def verify_all_expectations_met(self) -> None:
        """Verify that all expected requests and notifications were met.

        Raises:
            AssertionError: If any expectations were not met
        """
        # Check for unmet request expectations
        unmet_requests = {k: v for k, v in self._request_responses.items() if v}
        if unmet_requests:
            unmet_str = "\n".join([f"{k}: {len(v)} expectations" for k, v in unmet_requests.items()])
            raise AssertionError(f"Unmet request expectations:\n{unmet_str}")

        # Check for unmet notification expectations
        unmet_notifications = {k: v for k, v in self._expected_notifications.items() if v}
        if unmet_notifications:
            unmet_str = "\n".join([f"{k}: {len(v)} expectations" for k, v in unmet_notifications.items()])
            raise AssertionError(f"Unmet notification expectations:\n{unmet_str}")

    def verify(self) -> None:
        """Verify that all expected requests and notifications were met.

        Alias for verify_all_expectations_met() for backward compatibility.
        """
        self.verify_all_expectations_met()

    def expect_request_exception(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Set up an expected request with an exception response.

        Alias for expect_request(..., exception=exception) for backward compatibility.

        Args:
            target_service: The expected target service
            method: The expected method
            params: The expected parameters (or None to match any parameters)
            exception: The exception to raise, defaults to AssertionError
        """
        self.expect_request(target_service, method, params, None, exception or AssertionError("Expected failure"))

    async def start(self) -> None:
        """Start the communicator.

        This method is called when the agent starts and can be used to initialize connections.
        In the mock implementation, this is a no-op.
        """
        self._record_call("start")
        logger.debug("Started mock communicator", agent_name=self.agent_name)

    async def stop(self) -> None:
        """Stop the communicator.

        This method is called when the agent stops and can be used to clean up connections.
        In the mock implementation, this is a no-op.
        """
        self._record_call("stop")
        logger.debug("Stopped mock communicator", agent_name=self.agent_name)

    def get_sent_messages(self) -> List[Any]:
        """Get all the messages that were sent by this communicator.

        Returns:
            List of message objects that were sent
        """
        return self._sent_messages

    def link_communicator(self, other_communicator: "MockCommunicator") -> None:
        """Link this communicator with another one for direct communication.

        When linked, messages sent from this communicator to the other will
        automatically trigger handlers in the other communicator.

        Args:
            other_communicator: The communicator to link with
        """
        if not isinstance(other_communicator, MockCommunicator):
            raise TypeError("Can only link with another MockCommunicator")

        self._linked_communicators.append(other_communicator)
        # Also link the other way if not already linked
        if self not in other_communicator._linked_communicators:
            other_communicator._linked_communicators.append(self)

        logger.debug("Linked communicators", agent1=self.agent_name, agent2=other_communicator.agent_name)

    async def simulate_receive_message(self, message: Any) -> Any:
        """Simulate receiving a message by triggering the appropriate handler.

        Args:
            message: The message to simulate receiving (can be a dictionary or an object with attributes)

        Returns:
            The handler result, if any
        """
        # Support both dictionary-style messages and object-style messages
        if isinstance(message, dict):
            method = message["message_type"]
            params = message["content"]
        else:
            # Object-style message (for backward compatibility)
            if not hasattr(message, "message_type") or not hasattr(message, "content"):
                raise ValueError(
                    "Message must have message_type and content attributes or be a properly formatted dictionary"
                )
            method = message.message_type
            params = message.content

        # Call the handler
        return await self.trigger_handler(method, params)
