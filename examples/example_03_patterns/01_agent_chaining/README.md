# Agent Chaining Example

This example demonstrates a simple agent chaining pattern in OpenMAS, where two agents pass data in a sequential workflow:

1. A `ProducerAgent` generates data and sends it to a `ConsumerAgent`
2. The `ConsumerAgent` processes the data and returns a response
3. The `ProducerAgent` receives and handles the response

This pattern is useful for creating data processing pipelines, multi-step workflows, or any scenario where different agents need to collaborate in sequence.

## How It Works

1. **ProducerAgent**:
   - Generates a data payload with a test payload and timestamp
   - Sends the data to the ConsumerAgent using the `send_request` method
   - Logs the response it receives
   - Automatically terminates once the exchange is complete

2. **ConsumerAgent**:
   - Registers a handler for the `process_data` method during setup
   - When it receives data, it modifies it and returns a response
   - Remains running to handle additional requests (until the system shuts down)

## Running the Example

This example is designed to demonstrate the standard OpenMAS pattern for running multiple agents.

> **Note:** As of the current version, there is a known issue with the OpenMAS CLI when running agents that use `await self.stop()`. This will be fixed in a future release of OpenMAS. In the meantime, the example can still be run through the test suite.

To run the automated test that demonstrates agent chaining:

```bash
# From the project root
tox -e example-03-patterns-01-agent-chaining
```

When the CLI issue is resolved, you'll be able to run the agents using:

```bash
# Terminal 1: Start the consumer agent first
openmas run consumer

# Terminal 2: Then start the producer agent
openmas run producer
```

The test demonstrates the following agent chaining behavior:
- Both agents starting up
- The producer sending data to the consumer
- The consumer processing the data
- The producer receiving the response
- The producer automatically shutting down

This agent chaining pattern is typical for OpenMAS applications, where agents run as independent processes that communicate through their configured communicators.

## Key Code Components

### Producer Agent

The producer initiates the chain by sending data:

```python
# Generate data
data = {
    "data": "test_payload",
    "timestamp": "2023-01-01T12:00:00Z"
}

# Send to consumer
response = await self.communicator.send_request(
    target_service="consumer",
    method="process_data",
    params=data
)
```

### Consumer Agent

The consumer registers a handler and processes the request:

```python
# In setup:
self.communicator.register_handler("process_data", self.process_data)

# Handler:
async def process_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
    # Process the data
    processed_result = f"Modified: {params['data']}"

    # Return response
    return {
        "status": "processed",
        "result": processed_result
    }
```

### Configuration

The project configuration specifies HTTP communication, with the producer configured to know the consumer's URL:

```yaml
producer:
  communicator:
    type: http
    port: 8081
    service_urls:
      consumer: "http://localhost:8082"
```

## Extensions

This example demonstrates a simple two-agent chain, but you can extend it to:
- Chain multiple agents in sequence
- Create branching workflows with decision logic
- Implement more complex data transformations
- Add error handling and retries
- Use the `ServiceChain` utility (from `openmas.patterns.chaining`) for more complex chaining scenarios
