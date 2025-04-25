# Agent Implementation Refactoring

## Overview

This document describes a refactoring of the agent implementation in OpenMAS to consolidate duplicated code and create a more consistent module structure.

## Changes Made

### Consolidation of Duplicated Agent Implementations

We identified and resolved duplicated agent implementations:

1. **BaseAgent**:
   - Consolidated implementation in `src/openmas/agent/base.py`
   - Removed the duplicated `src/openmas/agent.py` file

2. **MCP Agent**:
   - Consolidated implementation in `src/openmas/agent/mcp.py`
   - Removed the duplicated `src/openmas/mcp_agent.py` file
   - McpServerAgent implementation is in `src/openmas/agent/mcp_server.py`

### Direct Re-exports in `__init__.py`

To simplify imports, we've added direct re-exports in the package's `__init__.py`:

```python
from openmas.agent.base import BaseAgent
from openmas.agent.bdi import BdiAgent
from openmas.agent.mcp import McpAgent, mcp_tool, mcp_prompt, mcp_resource
from openmas.agent.mcp_server import McpServerAgent
from openmas.agent.spade_bdi_agent import SpadeBdiAgent
```

This allows users to import directly from the main package:

```python
from openmas import BaseAgent, McpAgent
```

## Import Recommendations

### Recommended Imports

```python
# Direct imports from the main package
from openmas import BaseAgent, McpAgent, McpServerAgent, mcp_tool, mcp_prompt, mcp_resource

# Or specific imports from submodules if needed
from openmas.agent.base import BaseAgent
from openmas.agent.mcp import McpAgent, mcp_tool, mcp_prompt, mcp_resource
from openmas.agent.mcp_server import McpServerAgent
```

## Examples

All example code has been updated to use the new import paths, demonstrating the recommended approach for working with agent implementations.
