# Getting Started with OpenMAS

This guide will walk you through the standard OpenMAS workflow to create and run your first agent using the official OpenMAS CLI tools.

## Prerequisites

Ensure you have OpenMAS installed:

```bash
pip install openmas
```

If you haven't installed OpenMAS yet, see the detailed [Installation Guide](installation.md) for more information on virtual environments and optional dependencies.

## Step 1: Initialize Your Project

First, let's create a new OpenMAS project:

```bash
openmas init my_first_mas
```

This command creates a new directory `my_first_mas` with the standard OpenMAS project structure:

```
my_first_mas/
├── agents/              # Directory for your agents
│   └── sample_agent/    # A pre-generated sample agent
├── config/              # Configuration files
├── extensions/          # Custom framework extensions
├── packages/            # External dependencies
├── shared/              # Shared code between agents
├── tests/               # Project tests
├── openmas_project.yml  # Main project configuration
└── README.md            # Project documentation
```

The most important files are:
- `openmas_project.yml` - The central project configuration
- `agents/sample_agent/agent.py` - A sample agent ready to run

## Step 2: Explore the Sample Agent

When you initialize a project, OpenMAS automatically creates a sample agent for you. Let's examine its code:

```python
# agents/sample_agent/agent.py
import asyncio
from openmas.agent import BaseAgent

class Agent(BaseAgent):
    '''Sample agent implementation.'''

    async def setup(self) -> None:
        '''Set up the agent.'''
        self.logger.info("Sample agent initializing...")

    async def run(self) -> None:
        '''Run the agent.'''
        self.logger.info("Sample agent running...")

        # Example periodic task
        for i in range(5):
            self.logger.info(f"Sample agent tick {i}...")
            await asyncio.sleep(1)

        self.logger.info("Sample agent completed.")

    async def shutdown(self) -> None:
        '''Clean up when the agent stops.'''
        self.logger.info("Sample agent shutting down...")
```

This is a simple agent with three lifecycle methods:

- **setup()**: Runs once when the agent starts - use this for initialization
- **run()**: The main agent logic - this sample counts to 5 and exits
- **shutdown()**: Cleanup logic that runs when the agent stops

## Step 3: Run the Agent

Navigate into your project directory:

```bash
cd my_first_mas
```

Run the sample agent using the OpenMAS CLI:

```bash
openmas run sample_agent
```

You should see output similar to:

```
2023-09-24 15:30:45 [info     ] Loaded project config from ./openmas_project.yml
2023-09-24 15:30:45 [info     ] Initialized agent              [Agent] agent_name=sample_agent agent_type=Agent
2023-09-24 15:30:45 [info     ] Starting agent                 [Agent] agent_name=sample_agent
2023-09-24 15:30:45 [info     ] Started HTTP communicator      [openmas.communication.http]
2023-09-24 15:30:45 [info     ] Sample agent initializing...   [Agent]
2023-09-24 15:30:45 [info     ] Agent started                  [Agent] agent_name=sample_agent
Agent is running. Waiting for completion or Ctrl+C...
2023-09-24 15:30:45 [info     ] Sample agent running...        [Agent]
2023-09-24 15:30:45 [info     ] Sample agent tick 0...         [Agent]
2023-09-24 15:30:46 [info     ] Sample agent tick 1...         [Agent]
2023-09-24 15:30:47 [info     ] Sample agent tick 2...         [Agent]
2023-09-24 15:30:48 [info     ] Sample agent tick 3...         [Agent]
2023-09-24 15:30:49 [info     ] Sample agent tick 4...         [Agent]
2023-09-24 15:30:50 [info     ] Sample agent completed.        [Agent]
```

The sample agent runs, counts from 0 to 4, and then completes. You can also stop the agent at any time by pressing `Ctrl+C`. This will trigger the `shutdown()` method to be called.

## Step 4: Modify the Agent

Let's make a simple change to the agent. Open the `agents/sample_agent/agent.py` file in your editor and modify the log message in the `run()` method:

```python
async def run(self) -> None:
    '''Run the agent.'''
    self.logger.info("My first agent is running!")  # Changed message

    # Example periodic task
    for i in range(5):
        self.logger.info(f"Sample agent tick {i}...")
        await asyncio.sleep(1)

    self.logger.info("Sample agent completed.")
```

## Step 5: Run the Modified Agent

Run the agent again to see your changes:

```bash
openmas run sample_agent
```

Now you should see your modified message in the output:

```
2023-09-24 15:32:45 [info     ] Initialized agent              [Agent] agent_name=sample_agent agent_type=Agent
2023-09-24 15:32:45 [info     ] Starting agent                 [Agent] agent_name=sample_agent
2023-09-24 15:32:45 [info     ] Started HTTP communicator      [openmas.communication.http]
2023-09-24 15:32:45 [info     ] Sample agent initializing...   [Agent]
2023-09-24 15:32:45 [info     ] Agent started                  [Agent] agent_name=sample_agent
Agent is running. Waiting for completion or Ctrl+C...
2023-09-24 15:32:45 [info     ] My first agent is running!     [Agent]  # Your modified message
2023-09-24 15:32:45 [info     ] Sample agent tick 0...         [Agent]
2023-09-24 15:32:46 [info     ] Sample agent tick 1...         [Agent]
2023-09-24 15:32:47 [info     ] Sample agent tick 2...         [Agent]
2023-09-24 15:32:48 [info     ] Sample agent tick 3...         [Agent]
2023-09-24 15:32:49 [info     ] Sample agent tick 4...         [Agent]
2023-09-24 15:32:50 [info     ] Sample agent completed.        [Agent]
```

## Conclusion & Next Steps

Congratulations! You've successfully:
1. Created a new OpenMAS project with the standard structure
2. Examined the sample agent
3. Run the agent using the OpenMAS CLI
4. Modified the agent and verified your changes

From here, you can explore more advanced topics:

- [**Configuration Guide**](configuration.md) - Learn how to configure your agents
- [**Communication Guide**](communication.md) - Understand how agents communicate
- [**Patterns Guide**](patterns.md) - Explore common agent patterns
- [**MCP Integration**](mcp_integration.md) - Connect your agents to AI models using MCP
- [**Testing Utilities**](testing-utilities.md) - Learn how to test your agents
- [**Project Structure**](../project_structure.md) - Understand the OpenMAS project layout
