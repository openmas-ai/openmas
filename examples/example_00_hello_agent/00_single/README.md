# Hello World Single Agent Example

This is a minimal OpenMAS example demonstrating a single agent that simply logs a "Hello" message.

## Description

The example contains one agent:
- `hello_agent_single`: A simple agent that logs "Hello from Single Agent!" and exits.

## Running the Example

Run this example using tox from the project root:

```bash
# From the openmas/ directory
tox -e example-00a-hello-single
```

The example runs the agent without any communicators, focusing purely on the
most basic agent lifecycle.

## Learning Goals

This example demonstrates:
1. The minimal structure of an OpenMAS agent
2. How to implement the `run()` method
3. How to use OpenMAS logging
4. The basics of OpenMAS project configuration
