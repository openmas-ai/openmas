"""Mock communicator for testing OpenMAS agents.

This module provides a mock communicator that can be used for testing agents
without real network dependencies.
"""

import difflib
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Type, TypeVar

from pydantic import BaseModel

from openmas.communication.base import BaseCommunicator
from openmas.logging import get_logger

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


class ParamsMatcher:
    """Utility class to match parameters with different matching strategies."""

    @staticmethod
    def match(expected: Any, actual: Any) -> Tuple[bool, Optional[str]]:
        """Match expected parameters against actual parameters.

        This method supports different types of matchers:
        - None: Matches any parameters (no validation)
        - Dict: Exact match of dictionary structure
        - Pattern: Regex pattern matching for string values
        - Callable: Custom matcher function that takes actual value and returns bool

        Args:
            expected: The expected parameters or matcher
            actual: The actual parameters to check

        Returns:
            A tuple of (match_successful, mismatch_reason)
        """
        # None matches anything
        if expected is None:
            return True, None

        # For dictionaries, check for nested structure match
        if isinstance(expected, dict) and isinstance(actual, dict):
            for key, value in expected.items():
                if key not in actual:
                    return False, f"Missing expected key '{key}'"

                # Recursively match nested structures
                if isinstance(value, dict) and isinstance(actual[key], dict):
                    submatch, reason = ParamsMatcher.match(value, actual[key])
                    if not submatch:
                        return False, f"Mismatch in nested key '{key}': {reason}"
                elif isinstance(value, Pattern) and isinstance(actual[key], str):
                    # Handle regex pattern matching
                    if not value.match(actual[key]):
                        return False, f"String '{actual[key]}' does not match pattern '{value.pattern}'"
                elif callable(value) and not isinstance(value, type):
                    # Handle custom matcher functions
                    try:
                        result = value(actual[key])
                        if not isinstance(result, bool):
                            return (
                                False,
                                f"Custom matcher for key '{key}' returned {type(result).__name__}, expected bool",
                            )
                        if not result:
                            return False, f"Failed custom matcher check for key '{key}'"
                    except Exception as e:
                        return False, f"Error in custom matcher for key '{key}': {str(e)}"
                elif value != actual[key]:
                    return False, f"Value mismatch for key '{key}': expected {repr(value)}, got {repr(actual[key])}"
            return True, None

        # If expected is a regex pattern, match it against actual
        if isinstance(expected, Pattern):
            if not isinstance(actual, str):
                return False, f"Expected string for regex match, got {type(actual).__name__}"
            if expected.match(actual):
                return True, None
            return False, f"String '{actual}' does not match pattern '{expected.pattern}'"

        # If expected is a callable, use it as a custom matcher
        if callable(expected) and not isinstance(expected, type):
            try:
                result = expected(actual)
                if not isinstance(result, bool):
                    return False, f"Custom matcher returned {type(result).__name__}, expected bool"
                return result, None if result else "Failed custom matcher check"
            except Exception as e:
                return False, f"Error in custom matcher: {str(e)}"

        # For other types, use direct equality comparison
        if expected != actual:
            return False, f"Expected {repr(expected)}, got {repr(actual)}"

        return True, None


class MockCommunicator(BaseCommunicator):
    """Mock communicator for testing OpenMAS agents.

    This communicator allows setting up expected requests and predefined responses
    for testing purposes. It also records all calls made to it for later assertions.

    Features:
    - Define expected requests with specific responses or exceptions
    - Configure expected notifications with parameter validation
    - Record all calls for later verification
    - Simulate handler registration and message triggering
    - Link communicators to test multi-agent interactions
    - Verify expectations were met

    Example:
        ```python
        # Create a mock communicator
        mock_comm = MockCommunicator(agent_name="test-agent")

        # Set up expected requests and responses
        mock_comm.expect_request(
            target_service="data-service",
            method="get_user",
            params={"user_id": "123"},
            response={"name": "Test User", "email": "test@example.com"}
        )

        # Set up with regex pattern matching
        mock_comm.expect_request(
            target_service="data-service",
            method="search_users",
            params={"query": re.compile(r"^test.*")},
            response={"results": [{"id": "123", "name": "Test User"}]}
        )

        # Use it in tests
        response = await mock_comm.send_request(
            target_service="data-service",
            method="get_user",
            params={"user_id": "123"}
        )
        assert response["name"] == "Test User"

        # Verify all expectations were met
        mock_comm.verify()
        ```
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Optional[Dict[str, str]] = None,
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the mock communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs (optional for mocking)
            config: Optional agent config (ignored for mock)
            **kwargs: Additional keyword arguments (ignored)
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
        Useful between tests or when reusing the same communicator instance.
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
        params: Any = None,
        response: Any = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Set up an expected request and its response.

        Args:
            target_service: The expected target service
            method: The expected method
            params: The expected parameters. Can be:
                   - None: Match any parameters
                   - Dict: Exactly match the dict structure
                   - Pattern: Regex pattern for string matching
                   - Callable: Custom matcher function(actual) -> bool
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
        params: Any = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Set up an expected notification.

        Args:
            target_service: The expected target service
            method: The expected method
            params: The expected parameters. Can be:
                   - None: Match any parameters
                   - Dict: Exactly match the dict structure
                   - Pattern: Regex pattern for string matching
                   - Callable: Custom matcher function(actual) -> bool
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
                # Found a linked communicator that matches the target service
                # Check if it has an expectation for this request
                key = f"{target_service}:{method}"
                if key in linked_comm._request_responses and linked_comm._request_responses[key]:
                    # Get the next expectation
                    expectation = linked_comm._request_responses[key][0]

                    # Check if parameters match using the matcher
                    expected_params = expectation["params"]
                    match_result, _ = ParamsMatcher.match(expected_params, params)

                    if match_result:
                        # Remove this expectation since it's being used
                        linked_comm._request_responses[key].pop(0)

                        # If an exception was set, raise it
                        if expectation["exception"]:
                            raise expectation["exception"]

                        # Return the response (validating if a model was provided)
                        response = expectation["response"]
                        if response_model is not None and response is not None:
                            return response_model.parse_obj(response)
                        return response

        # If we didn't find a response from linked communicators, check local expectations
        key = f"{target_service}:{method}"

        if key not in self._request_responses or not self._request_responses[key]:
            available = ", ".join([k for k in self._request_responses.keys() if self._request_responses[k]])
            raise AssertionError(
                f"Unexpected request: {target_service}:{method} with params: {params}.\n"
                f"Available requests: {available or 'none'}"
            )

        # Get the next expectation for this request
        expectation = self._request_responses[key][0]

        # Check if parameters match using the matcher
        expected_params = expectation["params"]
        match_result, mismatch_reason = ParamsMatcher.match(expected_params, params)

        if not match_result:
            # Keep the expectation and raise a detailed error
            raise AssertionError(
                f"Parameter mismatch for {target_service}:{method}\n"
                f"Reason: {mismatch_reason}\n"
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
                # using the full message to preserve sender information
                await linked_comm.simulate_receive_message(message)

        key = f"{target_service}:{method}"

        # Check if we have expectations set up
        if key in self._expected_notifications and self._expected_notifications[key]:
            # Get the next expectation for this notification
            expectation = self._expected_notifications[key][0]

            # Check if parameters match using the matcher
            expected_params = expectation["params"]
            match_result, mismatch_reason = ParamsMatcher.match(expected_params, params)

            if not match_result:
                # Keep the expectation and raise a detailed error
                raise AssertionError(
                    f"Parameter mismatch for notification {target_service}:{method}\n"
                    f"Reason: {mismatch_reason}\n"
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
            sender_id = message.get("sender_id", "test_sender")
        else:
            # Object-style message (for backward compatibility)
            if not hasattr(message, "message_type") or not hasattr(message, "content"):
                raise ValueError(
                    "Message must have message_type and content attributes or be a properly formatted dictionary"
                )
            method = message.message_type
            params = message.content
            sender_id = getattr(message, "sender_id", "test_sender")

        # Create a message with the sender_id
        message_dict = {
            "sender_id": sender_id,
            "recipient_id": self.agent_name,
            "content": params or {},
            "message_type": method,
        }

        # Call the handler with the full message
        return await self.trigger_handler(method, message_dict)

    async def trigger_handler(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Trigger a registered handler with the given parameters.

        This method is used for testing to simulate incoming messages.

        Args:
            method: The method name to trigger
            params: The parameters to pass to the handler (can be message content or a full message dict)

        Returns:
            The result of the handler call

        Raises:
            KeyError: If no handler is registered for the method
        """
        if method not in self._handlers:
            raise KeyError(
                f"No handler registered for method '{method}'. Available handlers: {list(self._handlers.keys())}"
            )

        handler = self._handlers[method]

        # Check if params is already a full message dict
        if isinstance(params, dict) and "sender_id" in params and "content" in params:
            # Already a message dict, use it directly
            message = params
        else:
            # Create a message dictionary to pass to the handler
            message = {
                "sender_id": (
                    "test_sender"
                    if not params or not isinstance(params, dict)
                    else params.get("sender_id", "test_sender")
                ),
                "recipient_id": self.agent_name,
                "content": params or {},
                "message_type": method,
                "conversation_id": None,
                "get": lambda key, default=None: (
                    (params or {}).get(key, default) if isinstance(params, dict) else default
                ),
            }

        return await handler(message)

    def verify_all_expectations_met(self) -> None:
        """Verify that all expected requests and notifications were met.

        Raises:
            AssertionError: If any expectations were not met
        """
        # Check for unmet request expectations
        unmet_requests = {k: v for k, v in self._request_responses.items() if v}
        unmet_notifications = {k: v for k, v in self._expected_notifications.items() if v}

        if not unmet_requests and not unmet_notifications:
            return

        error_message = ""

        if unmet_requests:
            request_details = "\n".join(
                [
                    f"  • {k}: {len(v)} expectations remaining"
                    + "".join([f"\n    - params: {exp['params']}, response: {exp['response']}" for exp in v[:3]])
                    + (f"\n    - ... and {len(v) - 3} more" if len(v) > 3 else "")
                    for k, v in unmet_requests.items()
                ]
            )
            error_message += f"Unmet request expectations:\n{request_details}\n"

        if unmet_notifications:
            notification_details = "\n".join(
                [
                    f"  • {k}: {len(v)} expectations remaining"
                    + "".join([f"\n    - params: {exp['params']}" for exp in v[:3]])
                    + (f"\n    - ... and {len(v) - 3} more" if len(v) > 3 else "")
                    for k, v in unmet_notifications.items()
                ]
            )
            error_message += f"Unmet notification expectations:\n{notification_details}"

        raise AssertionError(error_message.strip())

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


# Enhance MockCommunicator with better error messages for method typos
def _get_similar_methods(obj: Any, name: str) -> List[str]:
    """Find methods with similar names to the requested one."""
    methods = [m for m in dir(obj) if callable(getattr(obj, m)) and not m.startswith("_")]
    return difflib.get_close_matches(name, methods, n=3, cutoff=0.6)


# Patch MockCommunicator to provide better error messages
original_getattr = getattr(MockCommunicator, "__getattr__", None)
