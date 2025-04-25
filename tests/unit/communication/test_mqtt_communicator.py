"""Tests for the MQTT communicator."""

import asyncio
from unittest import mock

import pytest

# Check if MQTT module is available
try:
    # First, check if we can import paho.mqtt
    import paho.mqtt.client as mqtt  # noqa: F401

    # Then try to import the MqttCommunicator class
    from openmas.communication.mqtt import MqttCommunicator

    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    # Skip all tests in this module if MQTT is not available
    pytest.skip("MQTT dependencies are not available", allow_module_level=True)

from openmas.logging import get_logger

# Get logger for tests
test_logger = get_logger(__name__)


@pytest.fixture
def mqtt_communicator():
    """Create a test MQTT communicator with mocked client."""
    service_urls = {
        "test-service": "mqtt://test-service",
        "other-service": "mqtt://other-service",
    }

    # Create the communicator
    with mock.patch("paho.mqtt.client.Client") as mock_client_class:
        # Set up the mock client
        mock_client = mock_client_class.return_value
        mock_client.subscribe = mock.MagicMock()
        mock_client.publish = mock.MagicMock()
        mock_client.disconnect = mock.MagicMock()
        mock_client.connect = mock.MagicMock()
        mock_client.loop_forever = mock.MagicMock()
        mock_client.username_pw_set = mock.MagicMock()
        mock_client.tls_set = mock.MagicMock()

        # Create a communicator with the mock client
        communicator = MqttCommunicator("test-agent", service_urls)

        # For testing, store the mock client directly on the communicator
        communicator.client = mock_client

        # Patch the wait_for method to avoid timeout issues
        with mock.patch("asyncio.wait_for") as mock_wait_for:
            # Mock wait_for to just return True (successful wait)
            mock_wait_for.return_value = True

            # Setup patching for threading module
            with mock.patch("threading.Thread"):
                yield communicator


class TestMqttCommunicator:
    """Tests for the MqttCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {
            "test-service": "mqtt://test-service",
            "other-service": "mqtt://other-service",
        }

        with mock.patch("paho.mqtt.client.Client"):
            communicator = MqttCommunicator("test-agent", service_urls)

            assert communicator.agent_name == "test-agent"
            assert communicator.service_urls == service_urls
            assert communicator.broker_host == "localhost"
            assert communicator.broker_port == 1883
            assert communicator.topic_prefix == "openmas"
            assert communicator._is_started is False
            assert communicator.handlers == {}

    @pytest.mark.asyncio
    async def test_start_and_stop(self, mqtt_communicator):
        """Test starting and stopping the communicator."""
        # Start the communicator
        await mqtt_communicator.start()

        # Check the internal state
        assert mqtt_communicator._is_started is True

        # The client.subscribe should be called for request and response topics
        mqtt_communicator.client.subscribe.assert_any_call(
            f"{mqtt_communicator.topic_prefix}/{mqtt_communicator.agent_name}/request/#"
        )
        mqtt_communicator.client.subscribe.assert_any_call(
            f"{mqtt_communicator.topic_prefix}/{mqtt_communicator.agent_name}/response/#"
        )

        # Stop the communicator
        await mqtt_communicator.stop()

        # Check the internal state after stopping
        assert mqtt_communicator._is_started is False
        mqtt_communicator.client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_handler(self, mqtt_communicator):
        """Test registering a handler."""
        # Start the communicator first
        await mqtt_communicator.start()

        # Clear the mock calls from start
        mqtt_communicator.client.subscribe.reset_mock()

        # Register a handler
        handler = mock.AsyncMock()
        await mqtt_communicator.register_handler("test_method", handler)

        # Check that the handler was registered
        assert mqtt_communicator.handlers["test_method"] == handler

        # Verify that subscribing to the notification topic happens during registration
        # when the communicator is already started
        expected_notification_topic = (
            f"{mqtt_communicator.topic_prefix}/{mqtt_communicator.agent_name}/notification/test_method"
        )
        mqtt_communicator.client.subscribe.assert_called_once_with(expected_notification_topic)

        # Reset mock to test registering another handler
        mqtt_communicator.client.subscribe.reset_mock()

        # Register another handler
        another_handler = mock.AsyncMock()
        await mqtt_communicator.register_handler("another_method", another_handler)

        # Verify that subscription happens for the new handler too
        expected_notification_topic_2 = (
            f"{mqtt_communicator.topic_prefix}/{mqtt_communicator.agent_name}/notification/another_method"
        )
        mqtt_communicator.client.subscribe.assert_called_once_with(expected_notification_topic_2)

        # Now test what happens when registering a handler before starting
        # Create a new communicator
        service_urls = {
            "test-service": "mqtt://test-service",
            "other-service": "mqtt://other-service",
        }

        with mock.patch("paho.mqtt.client.Client") as mock_client_class:
            # Set up the mock client
            mock_client = mock_client_class.return_value
            mock_client.subscribe = mock.MagicMock()

            new_communicator = MqttCommunicator("test-agent", service_urls)
            new_communicator.client = mock_client

            # Register a handler before starting
            pre_start_handler = mock.AsyncMock()
            await new_communicator.register_handler("pre_start_method", pre_start_handler)

            # Verify no subscription happens yet (communicator not started)
            mock_client.subscribe.assert_not_called()

            # Start the communicator with patched wait_for
            with mock.patch("asyncio.wait_for", return_value=True), mock.patch("threading.Thread"):
                await new_communicator.start()

            # Now subscription should happen for both standard topics and the notification topic
            mock_client.subscribe.assert_any_call(
                f"{new_communicator.topic_prefix}/{new_communicator.agent_name}/request/#"
            )
            mock_client.subscribe.assert_any_call(
                f"{new_communicator.topic_prefix}/{new_communicator.agent_name}/response/#"
            )

            # But there should be no separate subscribe call for notification topics

        # Stop the first communicator
        await mqtt_communicator.stop()

    @pytest.mark.asyncio
    async def test_send_request(self, mqtt_communicator):
        """Test sending a request."""
        # Start the communicator
        await mqtt_communicator.start()

        # Mock the publish method to simply capture the request
        mqtt_communicator.client.publish = mock.MagicMock()

        # Prepare a mock response
        mock_response = {"id": "test-id", "result": {"status": "success", "data": {"test": "value"}}, "error": None}

        # Mock asyncio.wait_for to return our response directly
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(coro, timeout):
            return mock_response

        # Apply the patch
        asyncio.wait_for = mock_wait_for

        try:
            # Send the request
            result = await mqtt_communicator.send_request(
                target_service="test-service", method="test_method", params={"param": "value"}, timeout=1.0
            )

            # Verify the result
            assert result == {"status": "success", "data": {"test": "value"}}
            assert mqtt_communicator.client.publish.call_count == 1

            # Check that the request was properly formatted
            call_args = mqtt_communicator.client.publish.call_args
            topic = call_args[0][0]
            assert topic == f"{mqtt_communicator.topic_prefix}/test-service/request/test_method"

        finally:
            # Restore the original function
            asyncio.wait_for = original_wait_for

            # Stop the communicator
            await mqtt_communicator.stop()
