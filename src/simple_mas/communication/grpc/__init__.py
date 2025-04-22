"""gRPC communicator for SimpleMAS."""

try:
    import grpc

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False

if HAS_GRPC:
    try:
        from simple_mas.communication.grpc.communicator import GrpcCommunicator

        __all__ = ["GrpcCommunicator"]
    except ImportError as e:
        # This is an unexpected error since gRPC is available
        # Re-raise with more context
        raise ImportError(f"gRPC is installed but failed to import gRPC modules: {e}") from e
else:

    class GrpcCommunicator:
        """Dummy class that raises ImportError when gRPC is not installed."""

        def __init__(self, agent_name, service_urls, **kwargs):
            """Raise ImportError when initialized.

            Args:
                agent_name: The name of the agent
                service_urls: Dictionary of service URLs
                **kwargs: Additional options for the communicator

            Raises:
                ImportError: Always raised since gRPC is not installed
            """
            raise ImportError(
                "gRPC packages are not installed. Install them with: " "pip install grpcio grpcio-tools protobuf"
            )

    __all__ = ["GrpcCommunicator"]
