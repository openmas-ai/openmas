"""MQTT Communicator example for OpenMAS.

This is an example of a third-party communicator implementation using MQTT.
It demonstrates how to extend BaseCommunicator and integrate with OpenMAS.

Requirements:
    pip install asyncio-mqtt

Usage:
    # Register manually
    from openmas.communication.base import register_communicator
    from mqtt_communicator import MqttCommunicator

    register_communicator("mqtt", MqttCommunicator)

    # Use in agent configuration
    agent = BaseAgent(
        name="my-agent",
        config=AgentConfig(
            name="my-agent",
            communicator_type="mqtt",
            communicator_options={
                "broker_host": "localhost",
                "broker_port": 1883,
                "client_id": "my-client-id"  # Optional
            }
        )
    )
"""

import asyncio
import json
import uuid
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

# Try to import MQTT library, but don't fail if not installed
try:
    import asyncio_mqtt as mqtt

    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

from openmas.communication.base import BaseCommunicator
from openmas.exceptions import CommunicationError, MethodNotFoundError, ServiceNotFoundError
from openmas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class MqttCommunicator(BaseCommunicator):
    """MQTT-based communicator implementation.

    This communicator uses MQTT for communication between services.
    It requires the asyncio-mqtt package to be installed.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: Optional[str] = None,
    ):
        """Initialize the MQTT communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to topics
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            client_id: Optional client ID (if not provided, a UUID will be generated)
        """
        if not HAS_MQTT:
            raise ImportError(
                "asyncio-mqtt package is required for MqttCommunicator. " "Install it with: pip install asyncio-mqtt"
            )

        super().__init__(agent_name, service_urls)
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id or f"{agent_name}-{uuid.uuid4()}"

        self.client = None
        self.handlers: Dict[str, Callable] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.subscription_task: Optional[asyncio.Task] = None

        logger.debug(
            "Initialized MQTT communicator",
            agent_name=agent_name,
            broker=f"{broker_host}:{broker_port}",
            client_id=self.client_id,
        )

    async def send_request(
        self,
        target_service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a request to a target service via MQTT.

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
            CommunicationError: If there is a problem with the communication
        """
        if target_service not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{target_service}' not found", target=target_service)

        request_id = str(uuid.uuid4())
        request_topic = f"{self.service_urls[target_service]}/request"
        response_topic = f"{self.agent_name}/response/{request_id}"

        # Create a future to hold the response
        response_future = asyncio.Future()
        self.pending_requests[request_id] = response_future

        # Create the request payload
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
            "response_topic": response_topic,
        }

        try:
            # Publish the request
            await self.client.publish(request_topic, json.dumps(payload))
            logger.debug(
                "Sent MQTT request",
                target=target_service,
                method=method,
                request_id=request_id,
                request_topic=request_topic,
            )

            # Wait for the response with timeout
            try:
                result = await asyncio.wait_for(response_future, timeout)

                # Validate the response if a model was provided
                if response_model is not None:
                    return response_model.model_validate(result)

                return result
            except asyncio.TimeoutError:
                raise CommunicationError(
                    f"Request to '{target_service}' timed out after {timeout} seconds",
                    target=target_service,
                    details={"method": method},
                )
        finally:
            # Clean up the pending request
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]

    async def send_notification(
        self, target_service: str, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification to a target service via MQTT.

        Args:
            target_service: The name of the service to send the notification to
            method: The method to call on the service
            params: The parameters to pass to the method

        Raises:
            ServiceNotFoundError: If the target service is not found
            CommunicationError: If there is a problem with the communication
        """
        if target_service not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{target_service}' not found", target=target_service)

        notification_topic = f"{self.service_urls[target_service]}/notification"

        # Create the notification payload
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }

        # Publish the notification
        await self.client.publish(notification_topic, json.dumps(payload))
        logger.debug(
            "Sent MQTT notification",
            target=target_service,
            method=method,
            notification_topic=notification_topic,
        )

    async def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method.

        Args:
            method: The method name to handle
            handler: The handler function
        """
        self.handlers[method] = handler
        logger.debug("Registered handler", method=method)

    async def start(self) -> None:
        """Start the MQTT communicator.

        This method connects to the MQTT broker and starts the message handling loop.
        """
        # Connect to the MQTT broker
        self.client = mqtt.Client(self.client_id)
        await self.client.connect(self.broker_host, self.broker_port)
        logger.info(
            "Connected to MQTT broker",
            broker=f"{self.broker_host}:{self.broker_port}",
            client_id=self.client_id,
        )

        # Subscribe to request and response topics
        await self.client.subscribe(f"{self.agent_name}/request/#")
        await self.client.subscribe(f"{self.agent_name}/response/#")
        logger.debug(
            "Subscribed to MQTT topics",
            request_topic=f"{self.agent_name}/request/#",
            response_topic=f"{self.agent_name}/response/#",
        )

        # Start the message handling loop
        self.subscription_task = asyncio.create_task(self._handle_messages())
        logger.info("Started MQTT communicator")

    async def stop(self) -> None:
        """Stop the MQTT communicator.

        This method disconnects from the MQTT broker and stops the message handling loop.
        """
        if self.subscription_task:
            self.subscription_task.cancel()
            try:
                await self.subscription_task
            except asyncio.CancelledError:
                pass
            self.subscription_task = None

        if self.client:
            await self.client.disconnect()
            self.client = None

        logger.info("Stopped MQTT communicator")

    async def _handle_messages(self) -> None:
        """Handle incoming MQTT messages.

        This method runs in the background and processes incoming requests and responses.
        """
        try:
            async with self.client.messages() as messages:
                async for message in messages:
                    try:
                        # Parse the message payload
                        payload = json.loads(message.payload.decode())
                        topic = message.topic

                        # Handle response messages
                        if topic.startswith(f"{self.agent_name}/response/"):
                            request_id = topic.split("/")[-1]
                            if request_id in self.pending_requests:
                                future = self.pending_requests[request_id]
                                if "result" in payload:
                                    future.set_result(payload["result"])
                                elif "error" in payload:
                                    error = payload["error"]
                                    error_code = error.get("code", 0)
                                    error_message = error.get("message", "Unknown error")

                                    if error_code == -32601:  # Method not found
                                        future.set_exception(
                                            MethodNotFoundError(
                                                error_message,
                                                target="unknown",
                                                details={"error": error},
                                            )
                                        )
                                    else:
                                        future.set_exception(
                                            CommunicationError(
                                                error_message,
                                                target="unknown",
                                                details={"error": error},
                                            )
                                        )

                        # Handle request messages
                        elif topic.startswith(f"{self.agent_name}/request/"):
                            method = payload.get("method")
                            params = payload.get("params", {})
                            request_id = payload.get("id")
                            response_topic = payload.get("response_topic")

                            # Process the request
                            if method in self.handlers:
                                handler = self.handlers[method]
                                try:
                                    result = await handler(**params)

                                    # Send response for non-notifications
                                    if request_id and response_topic:
                                        response = {
                                            "jsonrpc": "2.0",
                                            "id": request_id,
                                            "result": result,
                                        }
                                        await self.client.publish(response_topic, json.dumps(response))
                                except Exception as e:
                                    # Send error response for non-notifications
                                    if request_id and response_topic:
                                        error_response = {
                                            "jsonrpc": "2.0",
                                            "id": request_id,
                                            "error": {
                                                "code": -32000,
                                                "message": str(e),
                                            },
                                        }
                                        await self.client.publish(response_topic, json.dumps(error_response))
                            else:
                                # Method not found
                                if request_id and response_topic:
                                    error_response = {
                                        "jsonrpc": "2.0",
                                        "id": request_id,
                                        "error": {
                                            "code": -32601,
                                            "message": f"Method '{method}' not found",
                                        },
                                    }
                                    await self.client.publish(response_topic, json.dumps(error_response))

                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON message", topic=message.topic)
                    except Exception as e:
                        logger.exception("Error processing MQTT message", error=str(e))

        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            logger.debug("MQTT message handler cancelled")
            raise
        except Exception as e:
            logger.exception("Error in MQTT message handler", error=str(e))
