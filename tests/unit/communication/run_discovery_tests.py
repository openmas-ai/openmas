#!/usr/bin/env python
"""Script to run communicator discovery tests with mocked MCP dependencies."""

import sys
import unittest
from unittest import mock

# Import the test module - add this early to avoid the E402 issue
from tests.unit.communication import test_communicator_discovery

# Mock all MCP dependencies
sys.modules["mcp"] = mock.MagicMock()
sys.modules["mcp.client"] = mock.MagicMock()
sys.modules["mcp.client.session"] = mock.MagicMock()
sys.modules["mcp.client.sse"] = mock.MagicMock()
sys.modules["mcp.server"] = mock.MagicMock()
sys.modules["mcp.server.context"] = mock.MagicMock()
sys.modules["mcp.server.fastmcp"] = mock.MagicMock()
sys.modules["mcp.types"] = mock.MagicMock()

# Create mock classes
ClientSession = mock.MagicMock()
sys.modules["mcp.client.session"].ClientSession = ClientSession

if __name__ == "__main__":
    # Load tests from the imported module
    suite = unittest.TestLoader().loadTestsFromModule(test_communicator_discovery)
    unittest.TextTestRunner().run(suite)
