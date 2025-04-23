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

## Deployment Metadata Definition

SimpleMas provides a standardized way to define deployment requirements for each component through the `simplemas.deploy.yaml` file. This metadata format allows the SimpleMas deployment tooling to automatically generate configurations for Docker Compose, Kubernetes, and other orchestration systems.

### Metadata File Format (simplemas.deploy.yaml)

The deployment metadata is defined using a YAML file at the root of your SimpleMas component:

```yaml
# simplemas.deploy.yaml - Component deployment metadata
version: "1.0"  # SimpleMas deployment metadata version

component:
  name: "agent-name"  # Logical name of the component
  type: "agent"       # Component type: agent, service, etc.
  description: "Description of what this component does"

docker:
  build:
    context: "."      # Docker build context relative to this file
    dockerfile: "Dockerfile"  # Optional, defaults to "Dockerfile"
  # Alternative: use existing image
  # image: "name:tag"  # Docker image to use instead of building

environment:
  # Required environment variables
  - name: "AGENT_NAME"
    value: "${component.name}"  # Variables can reference other properties
  - name: "LOG_LEVEL"
    value: "INFO"
    description: "Logging level for the agent"
  # Secret environment variables (will be handled securely in deployment)
  - name: "API_KEY"
    secret: true
    description: "API key for external service"

ports:
  - port: 8000
    protocol: "http"
    description: "Main API endpoint"
  - port: 8001
    protocol: "websocket"
    description: "WebSocket for real-time communication"

volumes:
  - name: "data-volume"
    path: "/app/data"
    description: "Storage for persistent data"
  - name: "logs"
    path: "/app/logs"
    description: "Log storage"

dependencies:
  # Other SimpleMas components this component depends on
  - name: "knowledge-base"
    required: true
    description: "Knowledge base service for retrieving information"
  - name: "reasoning-engine"
    required: false
    description: "Optional reasoning engine for complex decisions"
```

### Using Variables and Templating

The metadata format supports variable references using `${var.path}` syntax to make configurations DRY and maintainable:

- Component properties: `${component.name}`, `${component.type}`
- Environment references: `${env.VARIABLE_NAME}`
- Dependency references: `${dependencies.name.property}`

### Example Metadata for a Hypothetical Agent

Here's an example `simplemas.deploy.yaml` file for a hypothetical chess playing agent:

```yaml
version: "1.0"

component:
  name: "chess-player"
  type: "agent"
  description: "An agent that can play chess using MCP protocol"

docker:
  build:
    context: "."
    dockerfile: "Dockerfile"

environment:
  - name: "AGENT_NAME"
    value: "${component.name}"
  - name: "LOG_LEVEL"
    value: "INFO"
  - name: "COMMUNICATOR_TYPE"
    value: "mcp_stdio"
  - name: "COMMUNICATOR_OPTIONS"
    value: '{"model": "claude-3-opus-20240229"}'
  - name: "MCP_API_KEY"
    secret: true
    description: "API key for MCP service"

ports:
  - port: 8000
    protocol: "http"
    description: "HTTP API for agent interaction"

volumes:
  - name: "chess-memory"
    path: "/app/data/memory"
    description: "Persistent memory for chess games"

dependencies:
  - name: "mcp-server"
    required: true
    description: "MCP server for model access"
  - name: "game-coordinator"
    required: true
    description: "Service that coordinates chess games"
```

### CLI for Deployment Generation

The SimpleMas deployment tooling provides a CLI for generating deployment configurations:

```bash
# Generate Docker Compose configuration for a single component
simplemas compose --input simplemas.deploy.yaml --output docker-compose.yml

# Generate Kubernetes manifests for a single component
simplemas k8s --input simplemas.deploy.yaml --output k8s/

# Validate deployment metadata
simplemas validate --input simplemas.deploy.yaml
```

## Multi-component Deployment Orchestration

SimpleMas provides powerful tools for orchestrating the deployment of multi-agent systems consisting of multiple components.

### Component Discovery

You can automatically discover all SimpleMas components in a directory structure:

```bash
# Discover all components in the current directory and subdirectories
simplemas discover

# Discover components in a specific directory
simplemas discover --directory path/to/project

# Use a custom pattern to match metadata files
simplemas discover --pattern "agent*/simplemas.deploy.yaml"
```

### Orchestrating Multiple Components

Generate a combined Docker Compose file for multiple components with automatic dependency resolution:

```bash
# Orchestrate all components in the current directory
simplemas orchestrate --output docker-compose.yml

# Orchestrate components in a specific directory with dependency validation
simplemas orchestrate --directory path/to/project --validate --output docker-compose.yml
```

This automatically configures:
- Service dependencies
- Environment variables for inter-service communication
- Shared volumes
- Networking between services

### Central Manifest Orchestration

For more complex deployments, you can define a central manifest file that coordinates multiple components:

```yaml
# simplemas.manifest.yaml
version: "1.0"

# Define the components to orchestrate
components:
  - name: agent1
    path: agent1/simplemas.deploy.yaml
    # Optional overrides for specific values
    overrides:
      environment:
        - name: SERVICE_URL_AGENT2
          value: http://agent2:8001

  - name: agent2
    path: agent2/simplemas.deploy.yaml

# Global configuration (applied to all components)
global:
  networks:
    - name: agent-network
      driver: bridge
```

Generate a deployment from the manifest:

```bash
# Generate Docker Compose from a manifest
simplemas manifest --manifest simplemas.manifest.yaml --output docker-compose.yml
```

## Examples

### Multi-agent System Example

Here's an example of a multi-agent system with two agents:

**Agent 1 (agent1/simplemas.deploy.yaml):**
```yaml
version: "1.0"
component:
  name: "agent1"
  type: "agent"
  description: "First agent in a multi-agent system"
environment:
  - name: "SERVICE_URL_AGENT2"
    value: "http://agent2:8001"
dependencies:
  - name: "agent2"
    required: true
# ... other configuration ...
```

**Agent 2 (agent2/simplemas.deploy.yaml):**
```yaml
version: "1.0"
component:
  name: "agent2"
  type: "agent"
  description: "Second agent in a multi-agent system"
environment:
  - name: "SERVICE_URL_AGENT1"
    value: "http://agent1:8000"
# ... other configuration ...
```

**Orchestrating the system:**
```bash
# Discover and verify the components
simplemas discover --directory .

# Generate a combined Docker Compose file
simplemas orchestrate --directory . --output docker-compose.yml --validate
```
