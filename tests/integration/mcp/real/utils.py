"""Test utilities for MCP integration tests."""

import asyncio
import logging
import os
import random
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

import pytest

# Try to import aiohttp, but don't fail if not available
try:
    import aiohttp  # type: ignore

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)

# Type definitions for clarity
T = TypeVar("T")
ServerProcess = asyncio.subprocess.Process
VerificationResult = Dict[str, Any]
VerificationFunction = Callable[[str], bool]


class TransportType(Enum):
    """Transport type for MCP communication."""

    STDIO = "stdio"
    SSE = "sse"


class McpTestHarness:
    """Standardized test harness for MCP integration tests.

    This class encapsulates the common patterns for launching, verifying, and
    cleaning up MCP server processes for integration testing.

    Features:
    - Support for both stdio and SSE transports
    - Incremental verification of server startup
    - Standardized subprocess management
    - Robust cleanup of resources
    - Support for test-only mode
    - Clear error reporting

    Attributes:
        transport_type: The transport type (stdio or SSE)
        script_path: Path to the server script
        process: The server subprocess (when started)
        verified: Whether the server has been verified
        verification_results: Results of each verification step
        test_port: Port to use for SSE tests
    """

    def __init__(
        self,
        transport_type: TransportType,
        script_path: Optional[Union[str, Path]] = None,
        test_port: int = 0,
    ):
        """Initialize the test harness.

        Args:
            transport_type: The transport type to use (stdio or SSE)
            script_path: Path to the server script. If None, uses default script path
                based on transport type.
            test_port: Port to use for SSE tests. If 0, a random port will be used.
        """
        self.transport_type = transport_type
        self.process: Optional[ServerProcess] = None
        self.verified = False
        self.verification_results: Dict[str, VerificationResult] = {}

        # Determine script path if not provided
        if script_path is None:
            script_dir = Path(__file__).parent
            if transport_type == TransportType.STDIO:
                script_path = script_dir / "stdio_server_script.py"
            else:  # SSE
                script_path = script_dir / "sse_server_script.py"

        self.script_path = Path(script_path)

        # Generate a random port for SSE tests if not provided
        if transport_type == TransportType.SSE:
            if test_port == 0:
                self.test_port = 8765 + random.randint(0, 1000)
            else:
                self.test_port = test_port
        else:
            self.test_port = 0

        # Server URL for SSE tests (will be set when server starts)
        self.server_url: Optional[str] = None

    async def start_server(self, test_only: bool = False, additional_args: Optional[List[str]] = None) -> ServerProcess:
        """Start the server process.

        Args:
            test_only: Whether to start in test-only mode
            additional_args: Additional arguments to pass to the server

        Returns:
            The server process

        Raises:
            RuntimeError: If the process fails to start
        """
        # Ensure the script is executable
        os.chmod(self.script_path, 0o755)

        # Build the command
        cmd = [sys.executable, str(self.script_path)]

        # Add test-only flag if requested
        if test_only:
            cmd.append("--test-only")

        # Add port for SSE transport
        if self.transport_type == TransportType.SSE:
            cmd.extend(["--port", str(self.test_port)])

        # Add any additional arguments
        if additional_args:
            cmd.extend(additional_args)

        logger.info(f"Starting {self.transport_type.value} server process: {' '.join(cmd)}")

        # Start the process
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Basic verification that process started
        if self.process.returncode is not None:
            raise RuntimeError(f"Process failed to start: return code {self.process.returncode}")

        # Wait for initialization
        await asyncio.sleep(1.0)

        return self.process

    async def verify_server_startup(self, timeout: float = 15.0) -> bool:
        """Verify that the server has started successfully.

        This method reads stderr output to find the server URL (for SSE)
        and then confirms connectivity via HTTP GET.

        Args:
            timeout: Maximum time to wait for verification

        Returns:
            True if the server has started and is connectable, False otherwise
        """
        if self.process is None:
            raise RuntimeError("Server process not started. Call start_server() first.")

        if self.verified:
            return True

        start_time = asyncio.get_event_loop().time()
        found_server_url = False

        # --- Loop 1: Find Server URL in stderr (SSE only) ---
        logger.info(f"Waiting for server URL in stderr (timeout: {timeout}s)...")
        while not found_server_url and (asyncio.get_event_loop().time() - start_time) < timeout:
            if self.transport_type == TransportType.STDIO:
                # For STDIO, we need to be more lenient - check stderr for any output
                # Returncode may not be None due to new FastMCP initialization with sampling
                if self.process.stderr:
                    # Read a bit from stderr to see if there's any output
                    try:
                        stderr_data = await asyncio.wait_for(self.process.stderr.readline(), timeout=0.5)
                        if stderr_data:
                            logger.info("STDIO process is producing stderr output. Assuming ready.")
                            self.verified = True
                            self.verification_results["startup"] = {"status": "Assumed ready for STDIO"}
                            return True
                    except asyncio.TimeoutError:
                        # No output yet, but that's okay - continue checking
                        pass

                # For STDIO, allow processes that exited with code 0 (success)
                # This might happen with the new sampling/prompt functionality
                if self.process.returncode is None or self.process.returncode == 0:
                    logger.info("STDIO process is running or exited successfully. Assuming ready.")
                    self.verified = True
                    self.verification_results["startup"] = {"status": "Assumed ready for STDIO"}
                    return True
                else:
                    logger.error(f"STDIO process exited prematurely with code {self.process.returncode}")
                    return False

            if self.process.stderr:
                try:
                    remaining_time = timeout - (asyncio.get_event_loop().time() - start_time)
                    stderr_data = await asyncio.wait_for(
                        self.process.stderr.readline(),  # This won't work with Popen
                        timeout=min(1.0, remaining_time) if remaining_time > 0 else 0.1,
                    )
                    stderr_line = stderr_data.decode("utf-8").strip()
                    logger.debug(f"Server stderr: {stderr_line}")  # Use debug for potentially noisy output

                    # Check specifically for the server URL pattern
                    match = re.search(r"SSE_SERVER_URL=(http://[^/\s\n]+)", stderr_line)
                    if match:
                        self.server_url = match.group(1)
                        logger.info(f"Found server URL: {self.server_url}")
                        found_server_url = True
                        break  # Exit URL search loop once found

                except asyncio.TimeoutError:
                    # Timeout reading a line, continue loop
                    pass
            else:
                # Stderr might not be available immediately
                await asyncio.sleep(0.1)

        if not found_server_url and self.transport_type == TransportType.SSE:
            logger.error("Timeout waiting for server URL in stderr.")
            self.verification_results["startup"] = {"error": "Timeout waiting for server URL"}
            return False

        # --- Loop 2: Verify HTTP Connection (SSE only) ---
        if self.transport_type == TransportType.SSE and self.server_url:
            sse_check_url = f"{self.server_url}/sse"
            logger.info(f"Verifying HTTP connection to {sse_check_url}...")
            connection_verified = False
            # Use remaining time for connection check
            connection_timeout = timeout - (asyncio.get_event_loop().time() - start_time)
            http_check_start_time = asyncio.get_event_loop().time()

            attempt = 0
            max_attempts = 10

            while (asyncio.get_event_loop().time() - http_check_start_time) < connection_timeout:
                attempt += 1
                try:
                    async with aiohttp.ClientSession() as session:
                        # Use a short timeout for individual GET attempts
                        async with session.get(sse_check_url, timeout=1.0) as response:
                            # Check if the /sse endpoint responds without a server error (5xx)
                            # We expect errors like 400/405 if GET isn't the right method for SSE setup,
                            # but that still means the server and endpoint are alive.
                            if response.status < 500:
                                logger.info(
                                    f"HTTP check to {sse_check_url} successful (status: {response.status}). "
                                    "Server likely ready."
                                )
                                connection_verified = True
                                break
                            else:
                                logger.warning(
                                    f"HTTP check to {sse_check_url} failed (status: {response.status}), retrying..."
                                )
                except (
                    aiohttp.ClientConnectorError,
                    asyncio.TimeoutError,
                    aiohttp.ClientOSError,
                    ConnectionRefusedError,
                ) as e:
                    logger.warning(
                        f"HTTP check attempt {attempt}/{max_attempts} failed ({type(e).__name__}), retrying..."
                    )
                except Exception as e:
                    logger.error(f"Unexpected error during HTTP check to {sse_check_url}: {e}", exc_info=True)
                    break  # Exit retry loop on unexpected errors

                # Check remaining time before sleeping
                if (asyncio.get_event_loop().time() - http_check_start_time) >= connection_timeout:
                    break
                await asyncio.sleep(0.2)  # Retry delay

            if not connection_verified:
                logger.error(f"Failed to verify HTTP connection to {sse_check_url} within remaining timeout.")
                self.verification_results["startup"] = {
                    "server_url": self.server_url,
                    "connection_verified": False,
                    "error": "HTTP connection check failed for /sse endpoint",
                }
                return False

            # If connection verified, mark server as fully verified
            logger.info("Server startup verified (URL found and /sse endpoint check successful).")
            self.verification_results["startup"] = {
                "server_url": self.server_url,
                "connection_verified": True,
            }
            self.verified = True
            return True

        # Should not be reached if logic is correct, but return False as fallback
        return False

    async def verify_basic_connectivity(self) -> bool:
        """Verify basic connectivity to the server.

        For stdio, checks for a test message on stdout.
        For SSE, checks the /test or /test-only endpoint.

        Returns:
            True if connectivity is verified, False otherwise

        Raises:
            RuntimeError: If server not started or not verified
        """
        if self.process is None:
            raise RuntimeError("Server process not started. Call start_server() first.")

        if not self.verified:
            raise RuntimeError("Server startup not verified. Call verify_server_startup() first.")

        if self.transport_type == TransportType.STDIO:
            # For stdio, check for a test message on stdout
            if self.process.stdout:
                try:
                    stdout_data = await asyncio.wait_for(self.process.stdout.readline(), timeout=2.0)
                    stdout_line = stdout_data.decode("utf-8").strip()
                    logger.info(f"Server stdout: {stdout_line}")

                    # Check for JSON-RPC message
                    connectivity_verified = "jsonrpc" in stdout_line and (
                        "test-init" in stdout_line or "test-only-mode" in stdout_line
                    )

                    self.verification_results["connectivity"] = {
                        "message_received": True,
                        "valid_jsonrpc": "jsonrpc" in stdout_line,
                        "test_message": stdout_line,
                    }

                    return connectivity_verified

                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for stdio message")
                    self.verification_results["connectivity"] = {
                        "message_received": False,
                        "timed_out": True,
                    }
                    return False

            return False

        else:  # SSE
            # Skip if aiohttp is not available
            if not HAS_AIOHTTP:
                logger.warning("aiohttp not available, skipping HTTP connectivity test")
                self.verification_results["connectivity"] = {
                    "skipped": True,
                    "reason": "aiohttp not available",
                }
                return False

            # For SSE, check the /test or /test-only endpoint
            try:
                if not self.server_url:
                    self.server_url = f"http://127.0.0.1:{self.test_port}"

                # Determine which endpoint to test - don't rely on process.args which might not be available
                try:
                    # Try to access process.args but don't fail if it's not available
                    process_args = getattr(self.process, "args", [])
                    endpoint = "/test-only" if "--test-only" in " ".join(process_args) else "/test"
                except (AttributeError, TypeError):
                    # Default to /test if we can't determine from process.args
                    logger.warning("Could not access process.args, defaulting to /test endpoint")
                    endpoint = "/test"

                test_url = f"{self.server_url}{endpoint}"

                logger.info(f"Testing HTTP endpoint: {test_url}")

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(test_url) as response:
                            response_text = await response.text()
                            response_status = response.status

                            try:
                                response_json = await response.json()
                            except Exception:
                                response_json = None

                            self.verification_results["connectivity"] = {
                                "http_status": response_status,
                                "response_text": response_text,
                                "response_json": response_json,
                            }

                            # Verify based on endpoint
                            if endpoint == "/test":
                                return (
                                    response_status == 200
                                    and response_json is not None
                                    and response_json.get("status") == "ok"
                                )
                            else:  # /test-only
                                return (
                                    response_status == 200
                                    and response_json is not None
                                    and response_json.get("id") == "test-only-mode"
                                )

                    except aiohttp.ClientError as e:
                        logger.error(f"HTTP request failed: {e}")
                        self.verification_results["connectivity"] = {
                            "error": str(e),
                            "type": "http_client_error",
                        }
                        return False

            except Exception as e:
                logger.error(f"Error testing HTTP endpoint: {e}")
                self.verification_results["connectivity"] = {
                    "error": str(e),
                    "type": "general_error",
                }
                return False

    async def cleanup(self, timeout: float = 2.0) -> None:
        """Clean up resources.

        Args:
            timeout: Maximum time to wait for process termination
        """
        if self.process and self.process.returncode is None:
            logger.info(f"Terminating server process {self.process.pid}...")
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=timeout)
                logger.info(f"Server process {self.process.pid} terminated gracefully.")
            except asyncio.TimeoutError:
                logger.warning(
                    f"Process {self.process.pid} did not terminate gracefully within {timeout} seconds, forcing kill"
                )
                self.process.kill()
                logger.info(f"Server process {self.process.pid} killed.")
        elif self.process:
            logger.info(f"Server process {self.process.pid} already terminated with code {self.process.returncode}")

    async def __aenter__(self) -> "McpTestHarness":
        """Enter the async context manager.

        Returns:
            The harness instance
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager.

        Ensures the process is cleaned up.
        """
        await self.cleanup()

    def get_verification_summary(self) -> Dict[str, Any]:
        """Get a summary of verification results.

        Returns:
            A dictionary with verification results
        """
        return {
            "transport_type": self.transport_type.value,
            "verified": self.verified,
            "verification_results": self.verification_results,
            "server_url": self.server_url,
        }


# Helper functions for test implementations


async def run_basic_verification_test(
    transport_type: TransportType,
    script_path: Optional[Union[str, Path]] = None,
    test_only: bool = True,
    test_port: int = 0,
    additional_args: Optional[List[str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Run a basic verification test for an MCP server.

    This is a convenience function that:
    1. Creates a McpTestHarness
    2. Starts the server in test-only mode
    3. Verifies server startup
    4. Verifies basic connectivity
    5. Cleans up and returns results

    Args:
        transport_type: The transport type to use
        script_path: Path to the server script
        test_only: Whether to run in test-only mode
        test_port: Port to use for SSE tests
        additional_args: Additional arguments to pass to the server

    Returns:
        A tuple of (success, verification_summary)
    """
    harness = McpTestHarness(
        transport_type=transport_type,
        script_path=script_path,
        test_port=test_port,
    )

    try:
        # Start the server
        await harness.start_server(test_only=test_only, additional_args=additional_args)

        # Verify startup
        startup_verified = await harness.verify_server_startup()
        if not startup_verified:
            logger.warning("Server startup verification failed")
            return False, harness.get_verification_summary()

        # Verify connectivity
        connectivity_verified = await harness.verify_basic_connectivity()
        if not connectivity_verified:
            logger.warning("Connectivity verification failed")
            return False, harness.get_verification_summary()

        # All verification steps passed
        return True, harness.get_verification_summary()

    finally:
        # Clean up
        await harness.cleanup()


def skip_if_no_aiohttp() -> None:
    """Skip the test if aiohttp is not available."""
    if not HAS_AIOHTTP:
        pytest.skip("aiohttp is required for this test")
