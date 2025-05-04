"""Minimal script to run McpSseCommunicator in server mode for integration tests."""

import logging
import sys

# --- Early Logging Setup ---
# Setup basic logging IMMEDIATELY to capture import errors
log_format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger("MCPSSETestServer_EARLY")

try:
    # --- Original Imports ---
    import asyncio
    import random
    from typing import Any, Dict

    # Configure logging (re-configure main logger if needed, or use the early one)
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    #     handlers=[logging.StreamHandler(sys.stderr)],
    # )
    # logger = logging.getLogger("MCPSSETestServer") # Use the main logger name now
    logger = logging.getLogger("MCPSSETestServer")  # Switch to main logger name
    logger.info("Original imports successful.")

    # Need to import the communicator and potentially required types
    try:
        from openmas.communication.mcp.sse_communicator import McpSseCommunicator
    except ImportError as comm_imp_err:
        logger.critical(
            f"Failed to import McpSseCommunicator ({comm_imp_err}). Ensure OpenMAS is installed correctly.",
            exc_info=True,
        )
        sys.exit(1)
    except Exception as comm_err:  # Catch other potential errors during import
        logger.critical(f"Unexpected error importing McpSseCommunicator: {comm_err}", exc_info=True)
        sys.exit(1)
    logger.info("McpSseCommunicator import successful.")

    # --- Rest of the script ---
    communicator: McpSseCommunicator | None = None
    shutdown_event = asyncio.Event()

    async def simple_tool_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """A basic tool handler for testing."""
        logger.info(f"[Server Tool] Received payload: {payload}")
        return {"status": "ok", "echo": payload}

    async def main(port: int):
        """Main function to set up and run the communicator server."""
        global communicator
        logger.info(f"Initializing McpSseCommunicator in server mode on port {port}")
        communicator = McpSseCommunicator(
            agent_name="harness_test_server",
            service_urls={},  # Not used in server mode
            server_mode=True,
            http_port=port,
            server_instructions="Test server run by harness",
        )

        # Register the test tool handler
        await communicator.register_handler("simple_echo", simple_tool_handler)
        logger.info("Registered simple_echo tool handler.")

        try:
            logger.info("Starting communicator server...")
            await communicator.start()  # This starts the Uvicorn task and waits for readiness
            logger.info(f"Communicator server started successfully on port {port}.")

            # Signal readiness to the harness (important!)
            # The harness expects the URL on stderr
            host = "127.0.0.1"  # Assume localhost binding for tests
            sys.stderr.write(f"SSE_SERVER_URL=http://{host}:{port}\n")
            sys.stderr.flush()
            logger.info(f"Signalled readiness to harness: SSE_SERVER_URL=http://{host}:{port}")

            # Keep the server running until shutdown signal
            await shutdown_event.wait()

        except Exception:
            logger.exception("Error during server startup or runtime", exc_info=True)
        finally:
            logger.info("Shutting down communicator server...")
            if communicator:
                await communicator.stop()
            logger.info("Communicator server stopped.")

    def handle_signal(sig, frame):
        logger.warning(f"Received signal {sig}, initiating shutdown...")
        shutdown_event.set()

    # --- Main Execution Guard ---
    if __name__ == "__main__":
        if len(sys.argv) > 1:
            try:
                test_port = int(sys.argv[1])
            except ValueError:
                logger.error(f"Invalid port number: {sys.argv[1]}")
                sys.exit(1)
        else:
            # Use a default port if none provided (e.g., for direct execution)
            test_port = 8700 + random.randint(500, 1000)
            logger.warning(f"No port provided, using random default: {test_port}")

        # Register signal handlers for graceful shutdown (REMOVED FOR TESTING - harness handles termination)
        # signal.signal(signal.SIGINT, handle_signal)
        # signal.signal(signal.SIGTERM, handle_signal)

        try:
            logger.info(f"Starting server main function on port {test_port}")
            asyncio.run(main(test_port))
        except KeyboardInterrupt:  # Catch Ctrl+C specifically
            logger.info("Keyboard interrupt received.")
        except Exception as e:
            # Log any other exceptions that occur at the top level
            logger.exception(f"Server script failed with unhandled exception ({type(e).__name__}): {e}", exc_info=True)
            sys.exit(1)  # Ensure exit code 1 on failure
        finally:
            logger.info("Server script exiting.")

except Exception as early_error:
    # --- Catch ANY error during import or initial setup ---
    logger.critical(f"CRITICAL ERROR DURING SCRIPT INITIALIZATION: {early_error}", exc_info=True)
    sys.exit(1)  # Exit with error code
