# Hello Agent Example

This is a simple example demonstrating how to create and run a basic agent using the SimpleMAS framework.

## What This Example Demonstrates

- Creating a project structure with the `simplemas init` command
- Defining a simple agent that inherits from `BaseAgent`
- Implementing lifecycle methods: `setup()`, `run()`, and `shutdown()`
- Running the agent using the `simplemas run` command
- Generating a Dockerfile for containerizing the agent

## Running the Example

Navigate to the example directory and run the agent:

```bash
cd hello_agent_example
python -m simple_mas.cli run hello_agent
```

## Containerizing the Agent

You can generate a Dockerfile for the agent:

```bash
cd hello_agent_example
python -m simple_mas.cli generate-dockerfile hello_agent
```

This will create a `Dockerfile` in the current directory. You can build and run it with:

```bash
docker build -t hello-agent .
docker run --name hello-agent-container hello-agent
```

## What Happens

The agent will:
1. Initialize and set up
2. Print a hello message
3. Start a countdown from 10 to 0
4. Display a fun explosion message at the end
5. Exit gracefully

## Code Structure

- `hello_agent_example/`: The project root directory
  - `simplemas_project.yml`: Project configuration
  - `agents/hello_agent/`: The agent directory
    - `agent.py`: The agent implementation

## Key Concepts

- **Agent Lifecycle**: The agent implements the three key lifecycle methods:
  - `setup()`: Initial setup when the agent starts
  - `run()`: The main execution loop
  - `shutdown()`: Cleanup when the agent terminates

- **Project Configuration**: The `simplemas_project.yml` file defines:
  - Project metadata (name, version)
  - Agent locations and paths
  - Default configuration settings
