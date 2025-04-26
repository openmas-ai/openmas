"""Mock utilities for gRPC tests.

This module contains mock classes and functions for testing gRPC functionality
without requiring the actual gRPC package to be installed.
"""

import sys
from unittest import mock

# =========================================================================
# Mock the google module and its subdependencies for protobuf
# =========================================================================
mock_google = mock.MagicMock()
mock_protobuf = mock.MagicMock()
mock_runtime_version = mock.MagicMock()

# Create mock for runtime_version.ValidateProtobufRuntimeVersion
mock_validate = mock.MagicMock()
mock_runtime_version.ValidateProtobufRuntimeVersion = mock_validate
mock_runtime_version.VersionError = type("VersionError", (Exception,), {})

# Set up module structure for google.protobuf
mock_google.protobuf = mock_protobuf
mock_protobuf.runtime_version = mock_runtime_version

# Mock the google module
sys.modules["google"] = mock_google
sys.modules["google.protobuf"] = mock_protobuf
sys.modules["google.protobuf.runtime_version"] = mock_runtime_version

# =========================================================================
# Mock gRPC modules
# =========================================================================
mock_grpc = mock.MagicMock()
mock_grpc.aio = mock.MagicMock()
mock_grpc.aio.insecure_channel = mock.MagicMock()
mock_grpc.aio.server = mock.MagicMock()

# Create mock StatusCode enum
mock_status_code = mock.MagicMock()
mock_status_code.OK = 0
mock_status_code.UNIMPLEMENTED = 12
mock_status_code.NOT_FOUND = 5
mock_status_code.UNAVAILABLE = 14
mock_status_code.DEADLINE_EXCEEDED = 4
mock_status_code.INTERNAL = 13
mock_grpc.StatusCode = mock_status_code

# =========================================================================
# Mock the openmas_pb2 and openmas_pb2_grpc modules
# =========================================================================
mock_openmas_pb2 = mock.MagicMock()
mock_openmas_pb2_grpc = mock.MagicMock()


# Create mock message types
class MockRequestMessage:
    """Mock implementation of gRPC RequestMessage."""

    def __init__(self, id="", source="", target="", method="", params=None):
        self.id = id
        self.source = source
        self.target = target
        self.method = method
        self.params = params or b"{}"
        self.timestamp = 0


class MockResponseMessage:
    """Mock implementation of gRPC ResponseMessage."""

    def __init__(self, id="", source="", target="", result=None, error=None):
        self.id = id
        self.source = source
        self.target = target
        self.result = result or b"{}"
        self.error = error or MockErrorMessage()
        self.timestamp = 0


class MockErrorMessage:
    """Mock implementation of gRPC ErrorMessage."""

    def __init__(self, code=0, message="", details=""):
        self.code = code
        self.message = message
        self.details = details


class MockEmpty:
    """Mock implementation of gRPC Empty message."""

    def __init__(self):
        """Initialize Empty message."""
        pass


# Assign mock classes to the mock modules
mock_openmas_pb2.RequestMessage = MockRequestMessage
mock_openmas_pb2.ResponseMessage = MockResponseMessage
mock_openmas_pb2.ErrorMessage = MockErrorMessage
mock_openmas_pb2.Empty = MockEmpty

# Mock the openmas_pb2_grpc.OpenMasServicer_to_server function
mock_openmas_pb2_grpc.add_OpenMasServicerToServer = mock.MagicMock()


# Create mock RpcError
class MockRpcError(Exception):
    """Mock implementation of gRPC's RpcError exception."""

    def __init__(self, code: int = mock_status_code.INTERNAL, details: str = "Mock RPC Error") -> None:
        """Initialize the mock RPC error.

        Args:
            code: Status code
            details: Error details
        """
        self._code = code
        self._details = details
        super().__init__(details)

    def code(self) -> int:
        """Get the status code.

        Returns:
            Status code
        """
        return self._code

    def details(self) -> str:
        """Get the error details.

        Returns:
            Error details
        """
        return self._details


# Assign RpcError to mock_grpc
mock_grpc.RpcError = MockRpcError


# =========================================================================
# Apply mocks to sys.modules
# =========================================================================
def apply_grpc_mocks() -> None:
    """Apply gRPC mocks to sys.modules.

    This function mocks all necessary gRPC dependencies for testing, including:
    - grpc and grpc.aio
    - google.protobuf modules
    - openmas_pb2 and openmas_pb2_grpc generated modules
    """
    # Mock the core gRPC modules
    sys.modules["grpc"] = mock_grpc
    sys.modules["grpc.aio"] = mock_grpc.aio

    # Mock google and protobuf modules
    sys.modules["google"] = mock_google
    sys.modules["google.protobuf"] = mock_protobuf
    sys.modules["google.protobuf.runtime_version"] = mock_runtime_version

    # Mock the generated protobuf modules
    sys.modules["openmas.communication.grpc.openmas_pb2"] = mock_openmas_pb2
    sys.modules["openmas.communication.grpc.openmas_pb2_grpc"] = mock_openmas_pb2_grpc

    # Ensure importable paths exist
    sys.modules["openmas.communication.grpc"] = mock.MagicMock()
    sys.modules["openmas.communication.grpc"].__path__ = []


# Apply mocks when this module is imported
apply_grpc_mocks()
