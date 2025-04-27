"""Simple MQTT integration tests."""

import pytest


@pytest.mark.mqtt
def test_mqtt_marker_exists():
    """Simple test to ensure the MQTT marker is recognized.

    This test doesn't test any functionality, but ensures
    that the mqtt marker is properly registered and works.
    """
    assert True, "This test should always pass"
