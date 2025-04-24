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
simplemas deploy compose --input simplemas.deploy.yaml --output docker-compose.yml

# Generate Kubernetes manifests for a single component
simplemas deploy k8s --input simplemas.deploy.yaml --output k8s/

# Validate deployment metadata
simplemas deploy validate --input simplemas.deploy.yaml
```

## Project-Based Deployment

SimpleMas provides a simplified way to generate deployment configurations directly from your `simplemas_project.yml` file. This approach ensures that all agents defined in your project are properly included in the deployment with correct networking configuration.

### Using the `simplemas deploy generate-compose` Command

The `generate-compose` command reads your project configuration and generates a Docker Compose file with all the agents connected:

```bash
# Basic usage
simplemas deploy generate-compose

# Specify custom project file and output location
simplemas deploy generate-compose --project-file=my-project.yml --output=compose/docker-compose.yml

# Fail if any agent is missing deployment metadata
simplemas deploy generate-compose --strict

# Use agent names from the project file instead of names in the metadata
simplemas deploy generate-compose --use-project-names
```

#### Command Options

- `--project-file`, `-p`: Path to the SimpleMas project file (default: simplemas_project.yml)
- `--output`, `-o`: Path to save the Docker Compose configuration file (default: docker-compose.yml)
- `--strict`, `-s`: Fail if any agent is missing deployment metadata
- `--use-project-names`, `-n`: Use agent names from project file instead of names in metadata

#### How It Works

The command performs the following steps:

1. Reads the `simplemas_project.yml` file to get agent definitions and their paths
2. Looks for a `simplemas.deploy.yaml` file in each agent's directory
3. Parses each metadata file and collects the deployment information
4. Automatically generates and configures `SERVICE_URL_*` environment variables based on dependencies
5. Creates a Docker Compose file with all the services properly connected

#### Example

For a project structure like:

```
my_project/
├── simplemas_project.yml
├── agents/
│   ├── orchestrator/
│   │   ├── agent.py
│   │   └── simplemas.deploy.yaml
│   └── worker/
│       ├── agent.py
│       └── simplemas.deploy.yaml
└── ...
```

Where `simplemas_project.yml` contains:

```yaml
name: "my_project"
version: "0.1.0"
agents:
  orchestrator: "agents/orchestrator"
  worker: "agents/worker"
# ...
```

Running `simplemas deploy generate-compose` will:

1. Read metadata for both agents
2. Configure the Docker Compose file with proper service URLs
3. Set up dependencies so that services start in the correct order

The resulting Docker Compose file will include both agents with networking automatically configured between them.

## Multi-component Deployment Orchestration

SimpleMas provides powerful tools for orchestrating the deployment of multi-agent systems consisting of multiple components.

### Component Discovery

You can automatically discover all SimpleMas components in a directory structure:

```bash
# Discover all components in the current directory and subdirectories
simplemas deploy discover

# Discover components in a specific directory
simplemas deploy discover --directory path/to/project

# Use a custom pattern to match metadata files
simplemas deploy discover --pattern "agent*/simplemas.deploy.yaml"
```

### Orchestrating Multiple Components

Generate a combined Docker Compose file for multiple components with automatic dependency resolution:

```bash
# Orchestrate all components in the current directory
simplemas deploy orchestrate --output docker-compose.yml

# Orchestrate components in a specific directory with dependency validation
simplemas deploy orchestrate --directory path/to/project --validate --output docker-compose.yml
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
simplemas deploy manifest --manifest simplemas.manifest.yaml --output docker-compose.yml
```

## Dockerfile Generation

SimpleMas provides a command to generate standardized, best-practice Dockerfiles for your agents. This ensures consistent containerization across your multi-agent system.

### Using the `simplemas deploy generate-dockerfile` Command

You can use the `generate-dockerfile` command to create a Dockerfile customized for your specific agent:

```bash
# Basic usage - creates a standard Dockerfile in the current directory
simplemas deploy generate-dockerfile

# Customize Python version
simplemas deploy generate-dockerfile --python-version 3.11

# Specify a different entrypoint (default is agent.py)
simplemas deploy generate-dockerfile --app-entrypoint main.py

# Specify a different requirements file
simplemas deploy generate-dockerfile --requirements-file requirements-prod.txt

# Generate a Dockerfile that uses Poetry for dependency management
simplemas deploy generate-dockerfile --use-poetry

# Change the output path
simplemas deploy generate-dockerfile --output ./docker/Dockerfile
```

### Command Options

- `--python-version`, `-p`: Python version to use (default: "3.10")
- `--app-entrypoint`, `-e`: Application entrypoint file (default: "agent.py")
- `--requirements-file`, `-r`: Path to requirements file (default: "requirements.txt")
- `--output`, `-o`: Output file path (default: "Dockerfile")
- `--use-poetry`: Generate Dockerfile using Poetry instead of pip
- `--port`: Port to expose in the Dockerfile (default: 8000)

### Generated Dockerfile Examples

#### Standard Pip-based Dockerfile

```dockerfile
# SimpleMas Agent Dockerfile
# Generated with simplemas deploy generate-dockerfile

FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_PORT=8000

# Run the application
CMD ["python", "agent.py"]
```

#### Poetry-based Dockerfile

```dockerfile
# SimpleMas Agent Dockerfile
# Generated with simplemas deploy generate-dockerfile

FROM python:3.10-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_PORT=8000

# Run the application
CMD ["poetry", "run", "python", "agent.py"]
```

These Dockerfiles follow best practices for Python applications:
- Using the slim image variant to reduce size
- Installing dependencies before copying application code for better layer caching
- Setting appropriate environment variables for Python applications
- Following a multi-stage build pattern
- Proper configuration of the workdir and port exposure

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
simplemas deploy discover --directory .

# Generate a combined Docker Compose file
simplemas deploy orchestrate --directory . --output docker-compose.yml --validate
```
