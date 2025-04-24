"""gRPC communicator for SimpleMAS."""

# Define a variable to track if gRPC is available
HAS_GRPC = False

# Try to import the real GrpcCommunicator
try:
    import grpc  # type: ignore[import]

    HAS_GRPC = True
except ImportError:
    pass

# Only try to import the real class if gRPC is available
if HAS_GRPC:
    try:
        from simple_mas.communication.grpc.communicator import GrpcCommunicator

        __all__ = ["GrpcCommunicator"]
    except ImportError as e:
        # This is an unexpected error since gRPC is available
        # Re-raise with more context
        raise ImportError(f"gRPC is installed but failed to import gRPC modules: {e}") from e
else:
    # Define a proxy class when grpc is not available
    class _DummyGrpcCommunicator:
        """Dummy class that raises ImportError when gRPC is not installed."""

        def __init__(self, agent_name: str, service_urls: dict, **kwargs: dict) -> None:
            """Raise ImportError when initialized.

            Args:
                agent_name: The name of the agent
                service_urls: Dictionary of service URLs
                **kwargs: Additional options for the communicator

            Raises:
                ImportError: Always raised since gRPC is not installed
            """
            raise ImportError(
                "gRPC packages are not installed. Install them with: pip install grpcio grpcio-tools protobuf"
            )

    # Export the dummy class with the expected name
    GrpcCommunicator = _DummyGrpcCommunicator  # type: ignore[assignment, misc]
    __all__ = ["GrpcCommunicator"]
