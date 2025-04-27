"""Simple gRPC integration tests."""

import pytest


@pytest.mark.grpc
def test_grpc_marker_exists():
    """Simple test to ensure the gRPC marker is recognized.

    This test doesn't test any functionality, but ensures
    that the grpc marker is properly registered and works.
    """
    assert True, "This test should always pass"
