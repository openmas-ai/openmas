"""Test for the MCP stdio tool call example."""

import pytest
from agents.tool_provider.agent import ToolProviderAgent
from agents.tool_user.agent import ToolUserAgent

from openmas.testing import AgentTestHarness, multi_running_agents


@pytest.mark.asyncio
async def test_mcp_stdio_tool_call():
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
