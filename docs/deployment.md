# Deploying SimpleMas Systems

This document provides guidance on deploying multi-agent systems built with SimpleMas.

## Deployment Architectures

### Single-Process Deployment

Ideal for simpler systems or testing:

```python
import asyncio
from simple_mas import Agent
from simple_mas.communication.mcp import MCPCommunicator

async def main():
    # Create agents in same process
    agent1 = Agent(
        name="agent1",
        communicator=MCPCommunicator(
            agent_name="agent1",
            service_urls={"agent2": "mcp://agent2"}
        )
    )

    agent2 = Agent(
        name="agent2",
        communicator=MCPCommunicator(
            agent_name="agent2",
            service_urls={"agent1": "mcp://agent1"}
        )
    )

    # Start agents
    await agent1.start()
    await agent2.start()

    # System runs here
    try:
        # Keep the system running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Graceful shutdown
        await agent1.stop()
        await agent2.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Multi-Process Deployment

For larger systems with agents running in separate processes:

```python
# agent1.py
import asyncio
from simple_mas import Agent
from simple_mas.communication import HTTPCommunicator

async def main():
    agent = Agent(
        name="agent1",
        communicator=HTTPCommunicator(
            agent_name="agent1",
            service_urls={"agent2": "http://localhost:8001/agent2"}
        ),
        http_port=8000
    )

    await agent.start()

    try:
        # Keep the process running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

```python
# agent2.py
import asyncio
from simple_mas import Agent
from simple_mas.communication import HTTPCommunicator

async def main():
    agent = Agent(
        name="agent2",
        communicator=HTTPCommunicator(
            agent_name="agent2",
            service_urls={"agent1": "http://localhost:8000/agent1"}
        ),
        http_port=8001
    )

    await agent.start()

    try:
        # Keep the process running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Docker Deployment

Containerize each agent for deployment:

```dockerfile
# Dockerfile for agent
FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

COPY . .

EXPOSE 8000

CMD ["poetry", "run", "python", "agent1.py"]
```

## Docker Compose

Deploy multiple agents together:

```yaml
# docker-compose.yml
version: '3'

services:
  agent1:
    build: .
    command: poetry run python agent1.py
    ports:
      - "8000:8000"
    environment:
      - AGENT_NAME=agent1
      - AGENT_PORT=8000
      - AGENT2_URL=http://agent2:8001/agent2

  agent2:
    build: .
    command: poetry run python agent2.py
    ports:
      - "8001:8001"
    environment:
      - AGENT_NAME=agent2
      - AGENT_PORT=8001
      - AGENT1_URL=http://agent1:8000/agent1
```

## Kubernetes Deployment

For production-grade, scalable systems:

```yaml
# agent-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent1
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent1
  template:
    metadata:
      labels:
        app: agent1
    spec:
      containers:
      - name: agent1
        image: simple-mas-agent:latest
        command: ["poetry", "run", "python", "agent1.py"]
        ports:
        - containerPort: 8000
        env:
        - name: AGENT_NAME
          value: "agent1"
        - name: AGENT_PORT
          value: "8000"
        - name: AGENT2_URL
          value: "http://agent2-service:8001/agent2"
---
apiVersion: v1
kind: Service
metadata:
  name: agent1-service
spec:
  selector:
    app: agent1
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

## Monitoring and Logging

Use the SimpleMas logging system to integrate with monitoring tools:

```python
from simple_mas.logging import get_logger

logger = get_logger(__name__)

# Configure logging to send to monitoring systems
logger.add_sink("prometheus", host="monitoring-server", port=9090)

# Log important events
logger.info(
    "Agent started",
    agent_name="agent1",
    connections=["agent2", "agent3"]
)
```
