# Getting Started: Your First OpenMAS Agent

This guide walks you through creating, running, and interacting with a very simple OpenMAS agent. It assumes you have already installed OpenMAS (see the [Installation Guide](installation.md) if you haven't).

## 1. Create the Agent Code

Create a file named `hello_agent.py` and add the following code:

```python
import asyncio
from openmas.agent import BaseAgent
from openmas.logging import configure_logging, get_logger

# Configure basic logging
configure_logging(log_level="INFO")
logger = get_logger(__name__)

class HelloAgent(BaseAgent):
    """A simple agent that can greet someone."""

    async def setup(self) -> None:
        """Register a handler when the agent starts."""
        logger.info(f"Agent '{self.name}' setting up.")
        # The 'register_handler' method allows other agents (or tools like curl)
        # to call the 'handle_greet' method on this agent.
        await self.communicator.register_handler("greet", self.handle_greet)
        logger.info(f"Agent '{self.name}' setup complete. Ready to handle 'greet' requests.")

    async def run(self) -> None:
        """The main loop for the agent (runs after setup)."""
        logger.info(f"Agent '{self.name}' is running. Waiting for requests...")
        # For this simple agent, we just wait indefinitely.
        # In more complex agents, this is where the main logic loop would go.
        while True:
            await asyncio.sleep(3600) # Sleep for an hour

    async def shutdown(self) -> None:
        """Clean up resources when the agent stops."""
        logger.info(f"Agent '{self.name}' shutting down.")
        # Add any cleanup logic here (e.g., closing connections)

    async def handle_greet(self, name: str = "world") -> dict:
        """Handles the 'greet' request."""
        logger.info(f"Received greet request for '{name}'.")
        return {"message": f"Hello, {name}! From agent '{self.name}'."}

async def main():
    """Creates and runs the agent."""
    # Create an instance of our agent.
    # By default, it uses the HttpCommunicator on port 8000.
    agent = HelloAgent(name="hello-agent-007")

    try:
        # Start the agent (runs setup, then run)
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    finally:
        # Stop the agent (runs shutdown)
        await agent.stop()
        logger.info("Agent stopped.")

if __name__ == "__main__":
    asyncio.run(main())

```

**Explanation:**

*   We define `HelloAgent` inheriting from `BaseAgent`.
*   `setup()`: This runs once when the agent starts. We register a *handler* named `greet` that points to our `handle_greet` method. This makes the method callable externally via the agent's communicator.
*   `run()`: This runs after `setup()`. For this agent, it just waits. Complex agents would perform their main tasks here.
*   `shutdown()`: This runs when the agent is stopped (e.g., by Ctrl+C).
*   `handle_greet()`: This is the actual logic that runs when the `greet` handler is called. It takes an optional `name` parameter and returns a dictionary (which will be serialized, e.g., to JSON for HTTP).
*   `main()`: This asynchronous function creates an instance of `HelloAgent` and uses `agent.start()` and `agent.stop()` to manage its lifecycle.

## 2. Run the Agent

Open your terminal in the same directory where you saved `hello_agent.py` and run:

```bash
python hello_agent.py
```

You should see log output indicating the agent is setting up and running:

```
INFO:hello_agent:Agent 'hello-agent-007' setting up.
INFO:openmas.communication.http:Starting HTTP server on 0.0.0.0:8000
INFO:hello_agent:Agent 'hello-agent-007' setup complete. Ready to handle 'greet' requests.
INFO:hello_agent:Agent 'hello-agent-007' is running. Waiting for requests...
```

The agent is now running and listening for requests on port 8000 (the default for `HttpCommunicator`).

## 3. Interact with the Agent

Open a *second* terminal window. Since our agent uses the default `HttpCommunicator`, we can interact with it using standard HTTP tools like `curl`.

Send a POST request to the agent's `greet` method:

**Without a name:**

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{}' \
     http://localhost:8000/call/greet
```

**Response:**

```json
{"message":"Hello, world! From agent 'hello-agent-007'."}
```

**With a name:**

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"name": "Alice"}' \
     http://localhost:8000/call/greet
```

**Response:**

```json
{"message":"Hello, Alice! From agent 'hello-agent-007'."}
```

In the first terminal (where the agent is running), you'll see log messages corresponding to these requests:

```
INFO:hello_agent:Received greet request for 'world'.
INFO:hello_agent:Received greet request for 'Alice'.
```

## 4. Stop the Agent

Go back to the first terminal (where the agent is running) and press `Ctrl+C`.
You should see the shutdown logs:

```
INFO:hello_agent:Shutdown signal received.
INFO:hello_agent:Agent 'hello-agent-007' shutting down.
INFO:openmas.communication.http:HTTP server stopped.
INFO:hello_agent:Agent stopped.
```

## Next Steps

Congratulations! You've created, run, and interacted with your first OpenMAS agent.

From here, you can explore:

*   **Configuration:** Learn how to configure agent names, ports, and other settings ([Configuration Guide](configuration.md)).
*   **Communication:** Discover how agents can call *each other* using different protocols like MCP, gRPC, or MQTT ([Communication Guide](communication.md), [MCP Guide](mcp_integration.md)).
*   **Agent Patterns:** Explore more advanced agent designs ([Patterns Guide](patterns.md)).
*   **Testing:** Learn how to test your agents ([Testing Utilities Guide](testing-utilities.md)).
