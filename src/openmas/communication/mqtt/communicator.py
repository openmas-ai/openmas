"""MQTT communicator module for OpenMAS."""

import asyncio
import json
import ssl
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional, Type, TypeVar

import paho.mqtt.client as mqtt
from pydantic import BaseModel, ValidationError

from openmas.communication.base import BaseCommunicator
from openmas.exceptions import CommunicationError, MethodNotFoundError, RequestTimeoutError, ServiceNotFoundError
from openmas.exceptions import ValidationError as OpenMasValidationError
from openmas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class MqttCommunicator(BaseCommunicator):
    """MQTT-based communicator implementation.

    This communicator uses MQTT for communication between services.
    It can both publish messages and subscribe to topics.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        client_id: Optional[str] = None,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        use_tls: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None,
        topic_prefix: str = "openmas",
        keepalive: int = 60,
        **kwargs: Any,
    ):
        """Initialize the MQTT communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to their topics (not used directly but required by interface)
            client_id: Optional client ID for MQTT connection (defaults to agent_name + random uuid)
            broker_host: The MQTT broker hostname or IP
            broker_port: The MQTT broker port
            use_tls: Whether to use TLS for the connection
            username: Optional username for broker authentication
            password: Optional password for broker authentication
            topic_prefix: Prefix for all MQTT topics
            keepalive: Keepalive interval in seconds
            **kwargs: Additional options for the communicator
        """
        super().__init__(agent_name, service_urls)

        self.client_id = client_id or f"{agent_name}-{str(uuid.uuid4())[:8]}"
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.use_tls = use_tls
        self.username = username
        self.password = password
        self.topic_prefix = topic_prefix
        self.keepalive = keepalive

        # Initialize MQTT client
        self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv5)

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # Set up authentication if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        # Set up TLS if enabled
        if self.use_tls:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

        # Handler registry and pending requests
        self.handlers: Dict[str, Callable] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}

        # Event for tracking connection status
        self._connected_event = asyncio.Event()

        # Track if started
        self._is_started = False
        self._client_thread: Optional[threading.Thread] = None

    async def start(self) -> None:
        """Start the MQTT communicator.

        This connects to the MQTT broker and sets up the message loop in a background thread.
        """
        if self._is_started:
            return

        logger.info(
            "Starting MQTT communicator",
            extra={
                "agent_name": self.agent_name,
                "broker": f"{self.broker_host}:{self.broker_port}",
                "client_id": self.client_id,
            },
        )

        # Start a background thread for the MQTT client loop
        def _mqtt_loop() -> None:
            try:
                self.client.connect(self.broker_host, self.broker_port, self.keepalive)
                self.client.loop_forever()
            except Exception as e:
                logger.error(f"MQTT loop error: {e}")

        self._client_thread = threading.Thread(target=_mqtt_loop, daemon=True)
        self._client_thread.start()

        # Wait for connection to be established
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise CommunicationError(f"Timeout connecting to MQTT broker at {self.broker_host}:{self.broker_port}")

        # Subscribe to all incoming request and response topics for this agent
        request_topic = f"{self.topic_prefix}/{self.agent_name}/request/#"
        response_topic = f"{self.topic_prefix}/{self.agent_name}/response/#"

        self.client.subscribe(request_topic)
        self.client.subscribe(response_topic)

        logger.debug(f"Subscribed to topics: {request_topic}, {response_topic}")

        self._is_started = True
        logger.info("MQTT communicator started successfully")

    async def stop(self) -> None:
        """Stop the MQTT communicator.

        This disconnects from the MQTT broker and cleans up resources.
        """
        if not self._is_started:
            return

        logger.info("Stopping MQTT communicator")

        # Clean up pending requests
        for request_id, future in self._pending_requests.items():
            if not future.done():
                future.set_exception(CommunicationError("Communicator stopped"))

        self._pending_requests.clear()

        # Disconnect client
        self.client.disconnect()

        # Wait for the client thread to complete
        if self._client_thread and self._client_thread.is_alive():
            self._client_thread.join(timeout=2.0)

        self._is_started = False
        self._connected_event.clear()
        logger.info("MQTT communicator stopped")

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a target service.

        Args:
            target_service: The name of the service to send the request to
            method: The method to call on the service
            params: The parameters to pass to the method
            response_model: Optional Pydantic model to validate and parse the response
            timeout: Optional timeout in seconds

        Returns:
            The response from the service

        Raises:
            ServiceNotFoundError: If the target service is not found
            MethodNotFoundError: If the target method is not found
            RequestTimeoutError: If the request times out
            CommunicationError: If there is a problem with the communication
            ValidationError: If the response validation fails
        """
        if not self._is_started:
            raise CommunicationError("MQTT communicator not started")

        if target_service not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{target_service}' not found", target=target_service)

        # Create a request ID
        request_id = str(uuid.uuid4())

        # Create a future for the response
        response_future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = response_future

        # Create request message
        request_message = {
            "id": request_id,
            "source": self.agent_name,
            "target": target_service,
            "method": method,
            "params": params or {},
            "timestamp": int(time.time() * 1000),
        }

        # Publish the request
        request_topic = f"{self.topic_prefix}/{target_service}/request/{method}"

        logger.debug(
            "Publishing MQTT request",
            extra={
                "topic": request_topic,
                "request_id": request_id,
                "target": target_service,
                "method": method,
            },
        )

        # Publish the request as JSON
        self.client.publish(request_topic, json.dumps(request_message).encode())

        # Wait for the response with timeout
        try:
            timeout_seconds = timeout or 30.0  # Default timeout
            response = await asyncio.wait_for(response_future, timeout=timeout_seconds)

            # Debug the response
            logger.debug(f"Received response: {type(response)} - {response}")

            # Remove the request from pending
            self._pending_requests.pop(request_id, None)

            # Ensure response is a dictionary
            if not isinstance(response, dict):
                raise CommunicationError(
                    f"Invalid response format, expected dictionary but got {type(response).__name__}",
                    target=target_service,
                    details={"method": method},
                )

            # Check for errors in the response
            error_field = response.get("error")
            if error_field and isinstance(error_field, dict):
                error_code = error_field.get("code", 0)
                error_message = error_field.get("message", "Unknown error")
                error_details = error_field.get("details", "")

                if error_code == 404:  # Method not found
                    raise MethodNotFoundError(
                        f"Method '{method}' not found on service '{target_service}'",
                        target=target_service,
                        details={"method": method, "error": error_message},
                    )
                elif error_code == 408:  # Request timeout
                    raise RequestTimeoutError(
                        f"Request to '{target_service}' timed out",
                        target=target_service,
                        details={"method": method, "error": error_message},
                    )

                # Generic error
                raise CommunicationError(
                    f"Error from service '{target_service}': {error_message}",
                    target=target_service,
                    details={"method": method, "error_code": error_code, "error_details": error_details},
                )

            # Parse the result
            result = response.get("result")

            # Validate the response if a model was provided
            if response_model is not None and result is not None:
                try:
                    return response_model.model_validate(result)
                except ValidationError as e:
                    raise OpenMasValidationError(f"Response validation failed: {e}")

            return result

        except asyncio.TimeoutError:
            # Remove the request from pending
            self._pending_requests.pop(request_id, None)

            raise RequestTimeoutError(
                f"Request to '{target_service}' timed out after {timeout_seconds} seconds",
                target=target_service,
                details={"method": method, "request_id": request_id},
            )
        except (ServiceNotFoundError, MethodNotFoundError, RequestTimeoutError):
            # Re-raise specific OpenMAS errors without wrapping
            raise
        except Exception as e:
            # Wrap other errors
            raise CommunicationError(
                f"Error sending request to '{target_service}': {str(e)}",
                target=target_service,
                details={"method": method, "error_type": type(e).__name__},
            )

    async def send_notification(
        self, target_service: str, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification to a target service.

        Args:
            target_service: The name of the service to send the notification to
            method: The method to call on the service
            params: The parameters to pass to the method

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        if not self._is_started:
            raise CommunicationError("MQTT communicator not started")

        if target_service not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{target_service}' not found", target=target_service)

        # Create notification message
        notification_message = {
            "id": str(uuid.uuid4()),
            "source": self.agent_name,
            "target": target_service,
            "method": method,
            "params": params or {},
            "timestamp": int(time.time() * 1000),
            "type": "notification",  # Add type field to distinguish from requests
        }

        # Publish the notification
        notification_topic = f"{self.topic_prefix}/{target_service}/notification/{method}"

        logger.debug(
            "Publishing MQTT notification",
            extra={
                "topic": notification_topic,
                "target": target_service,
                "method": method,
            },
        )

        # Publish the notification as JSON
        self.client.publish(notification_topic, json.dumps(notification_message).encode())

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self.handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")

        # Subscribe to method-specific notification topic if communicator is started
        if self._is_started:
            notification_topic = f"{self.topic_prefix}/{self.agent_name}/notification/{method}"
            self.client.subscribe(notification_topic)
            logger.debug(f"Subscribed to topic: {notification_topic}")

    def _on_connect(
        self, client: mqtt.Client, userdata: Any, flags: Dict[str, int], rc: int, properties: Any = None
    ) -> None:
        """Callback for when the client connects to the broker.

        Args:
            client: The MQTT client instance
            userdata: User data set by the client
            flags: Response flags from the broker
            rc: The connection result
            properties: MQTT v5 properties (ignored in v3.1.1)
        """
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            # Set the connected event to unblock the start method
            asyncio.run_coroutine_threadsafe(self._set_connected_event(), asyncio.get_event_loop())
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    async def _set_connected_event(self) -> None:
        """Set the connected event safely in the asyncio loop."""
        self._connected_event.set()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Callback for when a message is received from the broker.

        Args:
            client: The MQTT client instance
            userdata: User data set by the client
            msg: The received message
        """
        try:
            # Decode the message payload
            payload = json.loads(msg.payload.decode())

            # Extract topic parts
            topic_parts = msg.topic.split("/")

            # Handle based on topic structure
            if len(topic_parts) >= 4:
                target = topic_parts[1]  # The agent name
                msg_type = topic_parts[2]  # request, response, or notification

                # Only process messages for this agent
                if target != self.agent_name:
                    return

                if msg_type == "request":
                    # Handle request
                    method = topic_parts[3]
                    asyncio.run_coroutine_threadsafe(self._handle_request(payload, method), asyncio.get_event_loop())

                elif msg_type == "response":
                    # Handle response
                    request_id = topic_parts[3]
                    self._handle_response(payload, request_id)

                elif msg_type == "notification":
                    # Handle notification
                    method = topic_parts[3]
                    asyncio.run_coroutine_threadsafe(
                        self._handle_notification(payload, method), asyncio.get_event_loop()
                    )

        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON message on topic: {msg.topic}")
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}", exc_info=True)

    async def _handle_request(self, payload: Dict[str, Any], method: str) -> None:
        """Handle an incoming request message.

        Args:
            payload: The decoded request message
            method: The requested method name
        """
        request_id = payload.get("id", "")
        source = payload.get("source", "")
        params = payload.get("params", {})

        # Prepare response message
        response = {
            "id": request_id,
            "source": self.agent_name,
            "target": source,
            "timestamp": int(time.time() * 1000),
        }

        # Check if we have a handler for this method
        if method in self.handlers:
            try:
                handler = self.handlers[method]

                # Call the handler and get the result
                result = await handler(**params)

                # Add the result to the response
                response["result"] = result
            except Exception as e:
                # Create an error response
                response["error"] = {
                    "code": 500,  # Internal server error
                    "message": str(e),
                    "details": type(e).__name__,
                }
        else:
            # Method not found error
            response["error"] = {
                "code": 404,  # Not found
                "message": f"Method '{method}' not found",
                "details": "MethodNotFoundError",
            }

        # Publish the response
        response_topic = f"{self.topic_prefix}/{source}/response/{request_id}"
        self.client.publish(response_topic, json.dumps(response).encode())

    def _handle_response(self, payload: Dict[str, Any], request_id: str) -> None:
        """Handle an incoming response message.

        Args:
            payload: The decoded response message
            request_id: The ID of the original request
        """
        # Check if we have a pending request with this ID
        if request_id in self._pending_requests:
            future = self._pending_requests[request_id]

            if not future.done():
                # Set the result on the future
                asyncio.run_coroutine_threadsafe(self._set_future_result(future, payload), asyncio.get_event_loop())
        else:
            logger.warning(f"Received response for unknown request ID: {request_id}")

    async def _set_future_result(self, future: asyncio.Future, result: Any) -> None:
        """Set the result of a future safely in the asyncio loop.

        Args:
            future: The future to set the result on
            result: The result to set
        """
        if not future.done():
            future.set_result(result)

    async def _handle_notification(self, payload: Dict[str, Any], method: str) -> None:
        """Handle an incoming notification message.

        Args:
            payload: The decoded notification message
            method: The notification method name
        """
        params = payload.get("params", {})
        source = payload.get("source", "")

        # Check if we have a handler for this method
        if method in self.handlers:
            try:
                handler = self.handlers[method]

                # Call the handler (don't await the result for notifications)
                asyncio.create_task(handler(**params))
            except Exception as e:
                logger.error(
                    f"Error handling notification from {source}: {e}",
                    extra={"method": method, "source": source},
                    exc_info=True,
                )
        else:
            logger.warning(f"Received notification for unknown method: {method}")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int, properties: Any = None) -> None:
        """Callback for when the client disconnects from the broker.

        Args:
            client: The MQTT client instance
            userdata: User data set by the client
            rc: The disconnection result code
            properties: MQTT v5 properties (ignored in v3.1.1)
        """
        if rc == 0:
            logger.info("Disconnected from MQTT broker")
        else:
            logger.warning(f"Unexpected disconnection from MQTT broker, return code: {rc}")

            # Try to reconnect in a separate thread to avoid blocking
            def _attempt_reconnect() -> None:
                try:
                    self.client.reconnect()
                except Exception as e:
                    logger.error(f"Failed to reconnect to MQTT broker: {e}")

            # Don't attempt to reconnect if we're stopping
            if self._is_started:
                threading.Thread(target=_attempt_reconnect, daemon=True).start()
