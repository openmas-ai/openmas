"""Tests for src/openmas/communication/mqtt/__init__.py."""

import pytest

# Import the module under test
import openmas.communication.mqtt as mqtt_module


def test_mqtt_getattr_attribute_error():
    """Test that accessing an unknown attribute raises AttributeError."""
    with pytest.raises(AttributeError) as excinfo:
        _ = mqtt_module.NonExistentAttribute

    assert "'openmas.communication.mqtt' has no attribute 'NonExistentAttribute'" in str(excinfo.value)


# Note: Testing the ImportError path within __getattr__ is difficult due to
# challenges in reliably simulating missing dependencies in the test environment,
# similar to the issues encountered with the lazy loaders in communication/__init__.py.
# We will skip that specific test case for now.
