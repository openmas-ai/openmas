# Common Patterns in SimpleMas

This document describes common patterns and best practices for building multi-agent systems with SimpleMas.

## Basic Patterns

### Request-Response

The most common pattern is request-response:

```python
# Agent 1 sends a request
response = await agent1.send_request(
    target_service="agent2",
    method="get_data",
    params={"query": "weather"}
)

# Agent 2 handles the request
@agent2.handler("get_data")
async def handle_get_data(params):
    query = params.get("query")
    # Process the query
    return {"result": f"Data for {query}"}
```

### Notification

For one-way communication without expecting a response:

```python
# Agent 1 sends a notification
await agent1.send_notification(
    target_service="agent2",
    method="log_event",
    params={"event": "system_started"}
)

# Agent 2 handles the notification
@agent2.handler("log_event")
async def handle_log_event(params):
    event = params.get("event")
    # Process the event, no return value needed
```

## Advanced Patterns

### Pub-Sub Pattern

Implementing a publish-subscribe pattern:

```python
# Publisher agent
@publisher_agent.handler("subscribe")
async def handle_subscribe(params):
    topic = params.get("topic")
    subscriber = params.get("subscriber")
    # Add subscriber to topic
    return {"status": "subscribed"}

# Publisher sends updates
async def publish_update(topic, data):
    for subscriber in get_subscribers(topic):
        await publisher_agent.send_notification(
            target_service=subscriber,
            method="update",
            params={"topic": topic, "data": data}
        )

# Subscriber agent
@subscriber_agent.handler("update")
async def handle_update(params):
    topic = params.get("topic")
    data = params.get("data")
    # Process the update
```

### Service Discovery

Implementing dynamic service discovery:

```python
# Registry agent
@registry_agent.handler("register")
async def handle_register(params):
    service_name = params.get("service_name")
    service_url = params.get("service_url")
    # Register the service
    return {"status": "registered"}

@registry_agent.handler("discover")
async def handle_discover(params):
    service_name = params.get("service_name")
    # Find the service
    return {"service_url": get_service_url(service_name)}
```

## Best Practices

1. **Error Handling**: Always handle communication errors in your agents
2. **Timeout Management**: Set appropriate timeouts for requests
3. **Resource Cleanup**: Make sure to call `agent.stop()` when shutting down
4. **Message Validation**: Use Pydantic models to validate message structures
