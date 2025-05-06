"""Test for the MCP stdio tool call example."""

import asyncio
from typing import Any, Dict

import pytest
from agents.tool_provider.agent import ToolProviderAgent
from agents.tool_user.agent import ToolUserAgent

from openmas.testing import AgentTestHarness, multi_running_agents


@pytest.mark.asyncio
async def test_mcp_stdio_tool_call() -> None:
    """Test the MCP stdio tool call example.

    This test:
    1. Creates both the tool provider and tool user agents
    2. Sets up expectations for the tool call
    3. Runs both agents
    4. Verifies the tool call was made as expected
    5. Checks the result received by the tool user
    """
    # Create test harnesses for both agents
    provider_harness = AgentTestHarness(ToolProviderAgent)
    user_harness = AgentTestHarness(ToolUserAgent)

    # Create the agents
    provider = await provider_harness.create_agent(name="tool_provider")
    user = await user_harness.create_agent(name="tool_user")

    # Set up the expectation for the tool call
    # When the tool_user agent calls the process_data tool,
    # we set up what response it should receive from the mock communicator
    expected_payload = {"text": "Hello, this is a sample text that needs processing."}

    expected_response = {
        "processed_text": "HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.",
        "word_count": 9,
        "status": "success",
    }

    # Since we're using a mock communicator, we need to set up the expectation
    # for the tool call using the special "tool/call/process_data" method format
    user.communicator.expect_request(
        target_service="tool_provider",
        method="tool/call/process_data",
        params=expected_payload,
        response=expected_response,
    )

    # Run both agents using the multi_running_agents helper
    async with multi_running_agents(provider_harness, provider, user_harness, user):
        # Run the tool user agent, which will call the tool
        await user.run()

        # Verify that all expected calls were made
        user.communicator.verify()

        # Verify that the tool user agent received and stored the expected result
        assert user.result == expected_response, f"Expected {expected_response}, got {user.result}"


@pytest.mark.asyncio
async def test_mcp_stdio_tool_call_missing_text() -> None:
    """Test error handling when the text field is missing from the payload.

    This test verifies that:
    1. The tool provider properly handles missing required fields
    2. The tool user properly processes error responses
    """
    # Create test harnesses for both agents
    provider_harness = AgentTestHarness(ToolProviderAgent)
    user_harness = AgentTestHarness(ToolUserAgent)

    # Create the agents
    provider = await provider_harness.create_agent(name="tool_provider")
    user = await user_harness.create_agent(name="tool_user")

    # Create custom tool_user that sends invalid payload (empty dictionary)
    # Override the run method to change the payload
    async def custom_run() -> None:
        """Modified run method that sends an empty payload."""
        tool_name = "process_data"
        invalid_payload: Dict[str, Any] = {}  # Missing required "text" field

        try:
            result = await user.communicator.send_request(
                target_service="tool_provider", method=f"tool/call/{tool_name}", params=invalid_payload
            )
            user.result = result
        except Exception as e:
            user.error = {"error": str(e), "status": "error"}

    # Replace the run method with our custom version
    user.run = custom_run

    # Set up the expectation for the invalid tool call
    expected_error_response = {"error": "No text field in payload", "status": "error"}

    # Set up the mock expectation for the error case
    user.communicator.expect_request(
        target_service="tool_provider",
        method="tool/call/process_data",
        params={},  # Empty payload
        response=expected_error_response,
    )

    # Run both agents
    async with multi_running_agents(provider_harness, provider, user_harness, user):
        # Run the tool user agent with the invalid payload
        await user.run()

        # Verify that the expected request was made
        user.communicator.verify()

        # Verify the error response was received correctly
        assert user.result == expected_error_response, f"Expected error response not received: {user.result}"


@pytest.mark.asyncio
async def test_mcp_tool_call_timeout() -> None:
    """Test timeout handling for tool calls.

    This test verifies that:
    1. The tool user properly handles timeouts
    2. Error information is captured correctly
    """
    # Create test harness for just the user agent
    user_harness = AgentTestHarness(ToolUserAgent)

    # Create the user agent
    user = await user_harness.create_agent(name="tool_user")

    # Set up the communicator to raise a TimeoutError when called
    async def mock_send_request(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Mock function that simulates a timeout."""
        raise asyncio.TimeoutError("Simulated timeout")

    # Replace the send_request method on the mock communicator
    original_send_request = user.communicator.send_request
    user.communicator.send_request = mock_send_request

    # Set the error field to None to ensure it gets set
    user.error = None

    try:
        # Run the user agent (should catch the timeout)
        async with user_harness.running_agent(user):
            await user.run()

            # Verify that an error was captured
            assert user.error is not None, "Expected timeout error not captured"
            assert "timeout" in user.error.get("status", ""), f"Expected timeout status, got: {user.error}"
    finally:
        # Restore the original method
        user.communicator.send_request = original_send_request
