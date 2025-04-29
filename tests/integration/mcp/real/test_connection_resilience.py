"""Integration tests for MCP server connection resilience against abrupt client disconnections."""

import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent

# Skip test if dependencies not available
SKIP_REASON = "mcp or aiohttp not installed"
HAS_MCP = True
HAS_AIOHTTP = True
try:
    import aiohttp
except ImportError:
    HAS_AIOHTTP = False
    SKIP_REASON += " (aiohttp)"

try:
    import mcp
except ImportError:
    HAS_MCP = False
    SKIP_REASON += " (mcp)"

# Import test harness after dependency checks
from tests.integration.mcp.real.utils import McpTestHarness, TransportType

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Constants
CLIENT_TIMEOUT = 10.0  # Reduced timeout for client operations in seconds


async def make_tool_call(
    session: ClientSession, 
    tool_name: str, 
    params: Dict[str, Any],
    timeout: float = CLIENT_TIMEOUT
) -> Tuple[bool, Dict[str, Any]]:
    """
    Make a tool call and process the result.
    
    Args:
        session: Initialized ClientSession
        tool_name: Name of the tool to call
        params: Parameters to pass to the tool
        timeout: Timeout for the tool call
        
    Returns:
        Tuple of (success, result_data)
    """
    try:
        result = await asyncio.wait_for(
            session.call_tool(tool_name, params),
            timeout=timeout
        )
        logger.info(f"Received tool call result: {result}")
        
        # Process result
        if result and not result.isError and result.content:
            if isinstance(result.content[0], TextContent):
                response_text = result.content[0].text
                try:
                    response_data = json.loads(response_text)
                    return True, response_data
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON decode error: {json_err}")
                    return False, {"error": f"JSON decode error: {json_err}", "raw_response": response_text}
            else:
                logger.warning(f"Unexpected content type: {type(result.content[0])}")
                return False, {"error": f"Unexpected content type: {type(result.content[0])}"}
        elif result and result.isError:
            logger.error(f"Tool call failed: {result.content}")
            return False, {"error": "Tool call failed", "error_content": str(result.content)}
        else:
            logger.error("Tool call returned None or unexpected structure")
            return False, {"error": "Tool call returned None or unexpected structure"}
            
    except asyncio.TimeoutError:
        logger.error(f"Timeout calling tool '{tool_name}'")
        return False, {"error": f"Timeout calling tool '{tool_name}'"}
    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}': {e}", exc_info=True)
        return False, {"error": f"Error calling tool '{tool_name}': {e}"}


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP or not HAS_MCP, reason=SKIP_REASON)
async def test_sse_connection_resilience() -> None:
    """
    Test SSE server resilience to abrupt client disconnections.
    
    Steps:
    1. Start the server
    2. Connect a client and make a successful tool call
    3. Simulate an abrupt client disconnection
    4. Verify the server remains operational
    5. Connect a new client and make another successful tool call
    """
    test_port = 8765 + random.randint(0, 1000)
    logger.info(f"Using test port: {test_port}")
    
    # Create test harness for SSE
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)
    
    try:
        # 1. Start server subprocess
        logger.info("Starting server subprocess")
        process = await harness.start_server(
            additional_args=["--host", "127.0.0.1", "--port", str(test_port)]
        )
        
        # Basic check if process started immediately
        if process.returncode is not None:
            pytest.fail(f"Process failed to start with return code {process.returncode}")
            return
            
        # Wait for server to be ready
        logger.info("Server process started, waiting for readiness signal & HTTP check...")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed (check harness logs)"
        assert harness.server_url, "Server URL not found via harness"
        logger.info(f"Server ready, URL: {harness.server_url}")
        
        # 2. Connect first client and make successful tool call
        logger.info("=== FIRST CLIENT ===")
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"Connecting first client to SSE endpoint: {sse_endpoint_url}")
        
        # Use a subprocess for the first client to allow forced termination
        # This simulates a client crash or sudden network disconnect more realistically
        import subprocess
        import tempfile
        import os
        
        # Create a temporary script for the client
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as client_script:
            client_script.write(f"""
import asyncio
import json
import sys
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent

async def main():
    try:
        # Connect to server
        sse_endpoint_url = "{sse_endpoint_url}"
        print(f"Connecting to {{sse_endpoint_url}}")
        
        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            print("SSE streams obtained")
            
            async with ClientSession(read_stream, write_stream) as session:
                print("ClientSession created")
                await session.initialize()
                print("Session initialized")
                
                # Make tool call
                result = await session.call_tool("echo", {{"message": "Hello from subprocess client"}})
                print(f"Tool call result: {{result}}")
                
                # Verify result has the expected data
                if result and not result.isError and result.content:
                    if isinstance(result.content[0], TextContent):
                        response_text = result.content[0].text
                        response_data = json.loads(response_text)
                        if response_data.get("echoed") == "Hello from subprocess client":
                            print("SUCCESS: Tool call returned expected result")
                            # Exit with success - we'll kill the process before this completes
                            sys.exit(0)
                
                print("ERROR: Tool call failed or returned unexpected result")
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
""")
            client_script_path = client_script.name
        
        try:
            # Start the client subprocess
            logger.info(f"Starting first client as subprocess: {client_script_path}")
            client_process = subprocess.Popen(
                [sys.executable, client_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for the client to connect and make a successful call
            timeout = CLIENT_TIMEOUT
            success_seen = False
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                if client_process.poll() is not None:
                    # Process has terminated
                    stdout, stderr = client_process.communicate()
                    logger.info(f"Client process terminated with code {client_process.returncode}")
                    logger.info(f"STDOUT: {stdout}")
                    logger.info(f"STDERR: {stderr}")
                    if "SUCCESS: Tool call returned expected result" in stdout:
                        success_seen = True
                    break
                
                # Check stdout for success message
                stdout_line = client_process.stdout.readline() if client_process.stdout else ""
                if stdout_line:
                    logger.info(f"Client: {stdout_line.strip()}")
                    if "SUCCESS: Tool call returned expected result" in stdout_line:
                        success_seen = True
                        break
                
                # Brief pause before checking again
                await asyncio.sleep(0.1)
            
            # Verify client made a successful call
            if not success_seen:
                if client_process.poll() is None:
                    stdout, stderr = client_process.communicate(timeout=1.0)
                    logger.warning(f"Client process timed out, STDOUT: {stdout}")
                    logger.warning(f"STDERR: {stderr}")
                pytest.fail("First client did not complete a successful tool call")
            
            # 3. Simulate abrupt disconnection by forcibly terminating the process
            logger.info("Simulating abrupt client disconnection by terminating process...")
            if client_process.poll() is None:
                client_process.kill()
                logger.info("First client process forcibly terminated")
            
            # 4. Allow server time to detect the disconnection and log errors
            logger.info("Waiting for server to detect disconnection...")
            await asyncio.sleep(2.0)  # Give server time to detect and log the disconnect
            
            # 5. Connect a new client to verify server is still operational
            logger.info("=== SECOND CLIENT ===")
            logger.info(f"Connecting second client to SSE endpoint: {sse_endpoint_url}")
            
            # Use proper context managers for the second client
            async with sse_client(sse_endpoint_url) as second_streams:
                read_stream, write_stream = second_streams
                logger.info("Second client: SSE streams obtained")
                
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info("Second client: ClientSession created")
                    
                    # Initialize session
                    await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                    logger.info("Second client: Session initialized successfully")
                    
                    # Make tool call
                    success, data = await make_tool_call(
                        session, 
                        "echo", 
                        {"message": "Hello from second client"}
                    )
                    assert success, f"Second client tool call failed: {data.get('error', 'Unknown error')}"
                    assert data.get("echoed") == "Hello from second client", "Unexpected response data"
                    logger.info("Second client: Tool call succeeded")
            
            logger.info("Test completed successfully: Server handled abrupt disconnection properly")
            
        finally:
            # Clean up the temporary client script
            try:
                os.unlink(client_script_path)
            except Exception as e:
                logger.warning(f"Error removing temporary client script: {e}")
                    
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # Ensure cleanup of server process with timeout to avoid hanging
        logger.info("Cleaning up test harness...")
        try:
            cleanup_task = asyncio.create_task(harness.cleanup())
            await asyncio.wait_for(cleanup_task, timeout=5.0)
            logger.info("Test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Harness cleanup timed out - process may still be running")
            # Try to forcibly kill the server process if it's still running
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}")


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_MCP, reason=SKIP_REASON + " (mcp)")
async def test_stdio_connection_resilience() -> None:
    """
    Test Stdio server resilience to abrupt client disconnections.
    
    Steps:
    1. Start the server (expect the test harness to handle this)
    2. Connect first client and make a successful tool call
    3. Simulate an abrupt client disconnection
    4. Start a new server (since stdio servers likely terminate when client disconnects)
    5. Connect a new client and make another successful tool call
    """
    # Create test harness for Stdio
    harness = McpTestHarness(TransportType.STDIO)
    
    try:
        # 1. Start server subprocess
        logger.info("Starting Stdio server subprocess")
        process = await harness.start_server()
        
        # Basic check if process started immediately
        if process.returncode is not None:
            pytest.fail(f"Process failed to start with return code {process.returncode}")
            return
            
        # Wait for server to be ready
        logger.info("Server process started, waiting for readiness signal...")
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed (check harness logs)"
        logger.info("Stdio server ready")
        
        # Get script path for stdio client parameters
        script_path = str(harness.script_path)
        
        # 2. Connect first client and make successful tool call
        logger.info("=== FIRST CLIENT ===")
        logger.info(f"Connecting first client to Stdio server: {script_path}")
        
        # Use a separate process for the first client
        import subprocess
        import tempfile
        import os
        
        # Create a temporary script for the client
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as client_script:
            client_script.write(f"""
import asyncio
import json
import sys
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent

async def main():
    try:
        # Connect to server
        script_path = "{script_path}"
        print(f"Connecting to stdio server: {{script_path}}")
        
        server_params = StdioServerParameters(
            command=[sys.executable, script_path]
        )
        
        async with stdio_client(server_params) as streams:
            read_stream, write_stream = streams
            print("Stdio streams obtained")
            
            async with ClientSession(read_stream, write_stream) as session:
                print("ClientSession created")
                await session.initialize()
                print("Session initialized")
                
                # Make tool call
                result = await session.call_tool("echo", {{"message": "Hello from subprocess stdio client"}})
                print(f"Tool call result: {{result}}")
                
                # Verify result has the expected data
                if result and not result.isError and result.content:
                    if isinstance(result.content[0], TextContent):
                        response_text = result.content[0].text
                        response_data = json.loads(response_text)
                        if response_data.get("echoed") == "Hello from subprocess stdio client":
                            print("SUCCESS: Tool call returned expected result")
                            # Exit with success - we'll kill the process before this completes
                            sys.exit(0)
                
                print("ERROR: Tool call failed or returned unexpected result")
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
""")
            client_script_path = client_script.name
        
        try:
            # Start the client subprocess
            logger.info(f"Starting first stdio client as subprocess: {client_script_path}")
            client_process = subprocess.Popen(
                [sys.executable, client_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for the client to connect and make a successful call
            timeout = CLIENT_TIMEOUT
            success_seen = False
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                if client_process.poll() is not None:
                    # Process has terminated
                    stdout, stderr = client_process.communicate()
                    logger.info(f"Client process terminated with code {client_process.returncode}")
                    logger.info(f"STDOUT: {stdout}")
                    logger.info(f"STDERR: {stderr}")
                    if "SUCCESS: Tool call returned expected result" in stdout:
                        success_seen = True
                    break
                
                # Check stdout for success message
                stdout_line = client_process.stdout.readline() if client_process.stdout else ""
                if stdout_line:
                    logger.info(f"Client: {stdout_line.strip()}")
                    if "SUCCESS: Tool call returned expected result" in stdout_line:
                        success_seen = True
                        break
                
                # Brief pause before checking again
                await asyncio.sleep(0.1)
            
            # Verify client made a successful call
            if not success_seen:
                if client_process.poll() is None:
                    stdout, stderr = client_process.communicate(timeout=1.0)
                    logger.warning(f"Client process timed out, STDOUT: {stdout}")
                    logger.warning(f"STDERR: {stderr}")
                pytest.fail("First client did not complete a successful tool call")
            
            # 3. Simulate abrupt disconnection by forcibly terminating the process
            logger.info("Simulating abrupt client disconnection by terminating process...")
            if client_process.poll() is None:
                client_process.kill()
                logger.info("First client process forcibly terminated")
            
            # 4. Allow server time to detect the disconnection
            logger.info("Waiting for server to detect disconnection...")
            await asyncio.sleep(2.0)  # Give server time to detect and log the disconnect
            
            # Check if server process is still running - for stdio it likely terminated
            if harness.process is None or harness.process.returncode is not None:
                logger.info("Server process terminated after client disconnection (expected for stdio)")
                # Start a new server process
                logger.info("Starting a new Stdio server subprocess")
                process = await harness.start_server()
                
                # Basic check if process started immediately
                if process.returncode is not None:
                    pytest.fail(f"Second server process failed to start with return code {process.returncode}")
                    return
                    
                # Wait for server to be ready
                logger.info("Second server process started, waiting for readiness signal...")
                startup_ok = await harness.verify_server_startup(timeout=15.0)
                assert startup_ok, "Second server startup verification failed (check harness logs)"
                logger.info("Second Stdio server ready")
            
            # 5. Connect a new client to verify server is still operational (or new server works)
            logger.info("=== SECOND CLIENT ===")
            logger.info(f"Connecting second client to Stdio server: {script_path}")
            
            # Use proper context managers for the second client
            async with stdio_client(StdioServerParameters(command=[sys.executable, script_path])) as second_streams:
                read_stream, write_stream = second_streams
                logger.info("Second client: Stdio streams obtained")
                
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info("Second client: ClientSession created")
                    
                    # Initialize session
                    await asyncio.wait_for(session.initialize(), timeout=CLIENT_TIMEOUT)
                    logger.info("Second client: Session initialized successfully")
                    
                    # Make tool call
                    success, data = await make_tool_call(
                        session, 
                        "echo", 
                        {"message": "Hello from second stdio client"}
                    )
                    assert success, f"Second client tool call failed: {data.get('error', 'Unknown error')}"
                    assert data.get("echoed") == "Hello from second stdio client", "Unexpected response data"
                    logger.info("Second client: Tool call succeeded")
            
            logger.info("Test completed successfully")
            
        finally:
            # Clean up the temporary client script
            try:
                os.unlink(client_script_path)
            except Exception as e:
                logger.warning(f"Error removing temporary client script: {e}")
                    
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # Ensure cleanup of server process with timeout to avoid hanging
        logger.info("Cleaning up test harness...")
        try:
            cleanup_task = asyncio.create_task(harness.cleanup())
            await asyncio.wait_for(cleanup_task, timeout=5.0)
            logger.info("Test harness cleaned up")
        except asyncio.TimeoutError:
            logger.warning("Harness cleanup timed out - process may still be running")
            # Try to forcibly kill the server process if it's still running
            if harness.process and harness.process.returncode is None:
                try:
                    harness.process.kill()
                    logger.warning("Forcibly killed server process")
                except Exception as kill_err:
                    logger.warning(f"Error killing server process: {kill_err}") 