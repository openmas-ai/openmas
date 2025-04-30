# Deploying OpenMAS Systems

This document provides guidance on deploying multi-agent systems built with OpenMAS using common technologies like Docker and Kubernetes.

## Deployment Strategies

Depending on the complexity and requirements of your system, you might choose different deployment strategies:

### Single-Process Deployment

All agents run within the same operating system process. This is suitable for:

*   Simple systems with few agents.
*   Testing and development.
*   Scenarios where high-performance, low-latency communication via in-memory communicators (like a potential future `InMemoryCommunicator` or specific MCP setups) is crucial.

**Example Structure (`main_app.py`):**

```python
import asyncio
from openmas.agent import BaseAgent
# Assume an in-memory or suitable local communicator exists or is mocked
# from openmas.communication.memory import InMemoryCommunicator
from openmas.testing import MockCommunicator # Using Mock for illustration
from openmas.logging import configure_logging

configure_logging()

async def main():
    # Define shared communicator or links
    comm1 = MockCommunicator(agent_name="agent1")
    comm2 = MockCommunicator(agent_name="agent2")
    # Link mock communicators for in-process testing/simulation
    comm1.link_communicator(comm2)
    comm2.link_communicator(comm1)

    # Create agents in the same process
    agent1 = BaseAgent(name="agent1")
    agent1.set_communicator(comm1) # Manually set communicator
    # Register handlers...
    # @agent1.register_handler(...)

    agent2 = BaseAgent(name="agent2")
    agent2.set_communicator(comm2)
    # Register handlers...

    # Start agents
    await agent1.start()
    await agent2.start()

    # System runs here
    try:
        print("Single-process system running. Press Ctrl+C to stop.")
        # Keep the main process alive
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await agent1.stop()
        await agent2.stop()
        print("System stopped.")

if __name__ == "__main__":
    asyncio.run(main())
```

### Multi-Process Deployment

Each agent (or a small group of related agents) runs in its own operating system process on the same machine or different machines. This is the most common approach for non-trivial systems.

*   **Communication:** Requires network-based communicators like `HttpCommunicator`, `McpSseCommunicator`, `GrpcCommunicator`, or `MqttCommunicator`.
*   **Configuration:** Each agent process needs its configuration, especially `service_urls` pointing to the network addresses (host/port) of other agents/services it needs to contact.

**Example (`agent1_main.py`):**

```python
# agent1_main.py
import asyncio
from openmas.agent import BaseAgent
from openmas.config import load_config, AgentConfig
from openmas.logging import configure_logging

configure_logging()

async def main():
    config = load_config(AgentConfig) # Loads from env vars, files
    # Ensure config has necessary communicator_type, http_port, service_urls

    agent = BaseAgent(config=config)
    # Register handlers...

    await agent.start()

    try:
        print(f"Agent '{agent.name}' running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print(f"\nShutting down agent '{agent.name}'...")
        await agent.stop()
        print(f"Agent '{agent.name}' stopped.")

if __name__ == "__main__":
    # Example: Run with specific config via env vars
    # export AGENT_NAME=agent1
    # export COMMUNICATOR_TYPE=http
    # export COMMUNICATOR_OPTION_HTTP_PORT=8000
    # export SERVICE_URL_AGENT2="http://localhost:8001"
    asyncio.run(main())
```

(A similar `agent2_main.py` would be created, typically listening on a different port, e.g., 8001).

## Containerization with Docker

Containerizing agents with Docker is highly recommended for consistent environments and easier deployment.

### Creating a Dockerfile

A typical Dockerfile for an OpenMAS agent using Poetry might look like this:

```dockerfile
# Dockerfile for a single agent
ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/opt/poetry'

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.1 # Use a specific stable version

# Copy only dependency files first for caching
COPY pyproject.toml poetry.lock ./

# Install dependencies
# Use --only main if you don't need dev dependencies in the image
RUN poetry install --no-root --sync

# Copy the rest of the application code
COPY . .

# Default port exposure (can be overridden)
EXPOSE 8000

# Command to run the agent (adjust path if needed)
# Assumes your agent entrypoint script is src/my_project/agent1_main.py
CMD ["poetry", "run", "python", "src/my_project/agent1_main.py"]
```

### Generating a Dockerfile (Experimental)

OpenMAS provides an experimental CLI command to help generate a basic Dockerfile for a specific agent defined in your `openmas_project.yml`:

```bash
poetry run openmas generate-dockerfile <agent_name> --output-file Dockerfile.<agent_name>
```

*Replace `<agent_name>` with the name of the agent defined in your project file.* Review and customize the generated Dockerfile as needed.

### Building and Running

```bash
# Build the image
docker build -t my-agent-image:latest .

# Run the container
docker run -d --rm \
    -p 8000:8000 \
    -e AGENT_NAME=agent1 \
    -e COMMUNICATOR_OPTION_HTTP_PORT=8000 \
    -e SERVICE_URL_AGENT2="http://<agent2_host_or_ip>:8001" \
    --name my-agent1-container \
    my-agent-image:latest
```

## Orchestration with Docker Compose

For running multiple agents locally or in simple deployments, Docker Compose is useful.

**Example (`docker-compose.yml`):**

```yaml
version: '3.8'

services:
  agent1:
    build:
      context: . # Assumes Dockerfile is in the current directory
      # target: production # Optional: if using multi-stage builds
    container_name: agent1
    ports:
      - "8000:8000" # Expose agent1's port 8000 on the host
    environment:
      # --- OpenMAS Configuration ---
      - OPENMAS_ENV=production # Or development, local, etc.
      - LOG_LEVEL=INFO
      - AGENT_NAME=agent1
      - COMMUNICATOR_TYPE=http
      # --- Agent 1 Specific Options ---
      - COMMUNICATOR_OPTION_HTTP_PORT=8000 # Port inside the container
      # --- Service URLs (using Docker Compose service names) ---
      - SERVICE_URL_AGENT2=http://agent2:8001 # Agent 2 listens on 8001 internally
      # - SERVICE_URL_REDIS=redis://redis_db:6379 # Example external service
    # volumes: # Optional: Mount config files if not using env vars exclusively
      # - ./config:/app/config
    networks:
      - openmas_net

  agent2:
    build:
      context: .
    container_name: agent2
    ports:
      - "8001:8001"
    environment:
      - OPENMAS_ENV=production
      - LOG_LEVEL=INFO
      - AGENT_NAME=agent2
      - COMMUNICATOR_TYPE=http
      - COMMUNICATOR_OPTION_HTTP_PORT=8001
      - SERVICE_URL_AGENT1=http://agent1:8000 # Agent 1 listens on 8000 internally
    networks:
      - openmas_net

  # redis_db: # Example dependency
  #   image: redis:alpine
  #   networks:
  #     - openmas_net

networks:
  openmas_net:
    driver: bridge

```

**Run:**

```bash
docker-compose up -d
```

## Kubernetes Deployment

For production-grade, scalable deployments, Kubernetes is recommended. You will typically define `Deployment` and `Service` resources for each agent.

**Example (`agent1-k8s.yaml`):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent1-deployment
  labels:
    app: agent1
spec:
  replicas: 1 # Adjust as needed
  selector:
    matchLabels:
      app: agent1
  template:
    metadata:
      labels:
        app: agent1
    spec:
      containers:
      - name: agent1-container
        image: your-repo/my-agent-image:latest # Replace with your image registry path
        # If your agent entrypoint is different from Dockerfile CMD:
        # command: ["poetry", "run", "python", "src/my_project/agent1_main.py"]
        ports:
        - name: http # Name the port
          containerPort: 8000 # Agent listens on this port internally
        env:
        # --- OpenMAS Configuration via Env Vars ---
        - name: OPENMAS_ENV
          value: "production"
        - name: LOG_LEVEL
          value: "INFO"
        - name: AGENT_NAME
          value: "agent1"
        - name: COMMUNICATOR_TYPE
          value: "http"
        - name: COMMUNICATOR_OPTION_HTTP_PORT
          value: "8000" # Port inside the container
        # --- Service URLs (using Kubernetes service DNS names) ---
        - name: SERVICE_URL_AGENT2
          # Assumes a K8s Service named 'agent2-service' exists in the same namespace
          value: "http://agent2-service:8001" # agent2 listens on port 8001
        # Add other env vars for API keys, etc.
        # Consider using Secrets or ConfigMaps for sensitive/config data
        resources: # Optional: Define resource requests/limits
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: agent1-service # This is the DNS name other services will use
  labels:
    app: agent1
spec:
  selector:
    app: agent1 # Selects pods with the 'app: agent1' label
  ports:
  - name: http
    port: 8000 # Port the Service exposes within the cluster
    targetPort: http # Name of the container port to target (defined in Deployment)
  type: ClusterIP # Only exposes the service within the cluster
  # Use LoadBalancer or NodePort for external access if needed
```

**(A similar `agent2-k8s.yaml` would define the Deployment and Service for `agent2`, listening on port 8001 and referencing `agent1-service` in its `SERVICE_URL_AGENT1` environment variable).**

**Apply:**

```bash
kubectl apply -f agent1-k8s.yaml
kubectl apply -f agent2-k8s.yaml
```

## Monitoring and Logging

Effective monitoring and logging are crucial for deployed systems.

*   **Logging:** OpenMAS uses standard Python logging. Configure `configure_logging` (e.g., setting `json_format=True`) to output logs in a structured format (like JSON) suitable for log aggregation systems (e.g., Elasticsearch, Loki, Datadog).
    ```python
    from openmas.logging import configure_logging, get_logger

    # In your main entrypoint or agent setup:
    configure_logging(log_level="INFO", json_format=True)

    logger = get_logger(__name__)

    # Logs will now be in JSON format
    logger.info("Agent started", extra={"agent_id": self.name, "status": "active"})
    ```
*   **Metrics:** Integrate with metrics libraries (like `prometheus-client` or `opentelemetry-python`) to expose key agent metrics (e.g., messages processed, queue lengths, task durations). Expose these via an HTTP endpoint scraped by Prometheus or pushed to a monitoring backend.
*   **Tracing:** For complex interactions, consider distributed tracing using OpenTelemetry to track requests across multiple agents and services.
