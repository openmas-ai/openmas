"""Test for the MCP SSE tool call example."""

import logging

import pytest
from agents.tool_provider.agent import ToolProviderAgent
from agents.tool_user.agent import ToolUserAgent

from openmas.testing import AgentTestHarness, multi_running_agents

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
)


@pytest.mark.asyncio
async def test_mcp_sse_tool_call() -> None:
    """Test the MCP SSE tool call example.

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
async def test_mcp_sse_tool_call_missing_text() -> None:
    """Test error handling when the text field is missing from the payload.

    This test verifies that the tool provider correctly returns an error
    when the required 'text' field is missing from the payload.
    """
    # Create test harnesses for both agents
    provider_harness = AgentTestHarness(ToolProviderAgent)
    user_harness = AgentTestHarness(ToolUserAgent)

    # Create the agents
    provider = await provider_harness.create_agent(name="tool_provider")
    user = await user_harness.create_agent(name="tool_user")

    # Override the tool_user agent's run method to send an invalid payload
    async def modified_run() -> None:
        logger = user.logger
        logger.info("ToolUserAgent running with invalid payload")

        # Payload without the required 'text' field
        invalid_payload = {"missing_field": "This payload is missing the text field"}
        tool_name = "process_data"

        try:
            # Call the tool with the invalid payload
            result = await user.communicator.send_request(
                target_service="tool_provider",
                method=f"tool/call/{tool_name}",
                params=invalid_payload,
            )
            user.result = result
            logger.info(f"Received result: {result}")
        except Exception as e:
            logger.error(f"Error calling tool: {e}")
            user.error = {"error": str(e), "status": "error"}

    # Replace the run method
    user.run = modified_run  # type: ignore

    # Set up the expected error response
    expected_error_response = {
        "error": "No text field in payload",
        "status": "error",
    }

    # Set up the expectation for the invalid tool call
    user.communicator.expect_request(
        target_service="tool_provider",
        method="tool/call/process_data",
        params={"missing_field": "This payload is missing the text field"},
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
