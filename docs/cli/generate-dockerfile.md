# `openmas generate-dockerfile` Command

The `openmas generate-dockerfile` command helps you create a Dockerfile for an OpenMAS agent, making it easy to containerize your agent for deployment.

## Usage

```bash
openmas generate-dockerfile <agent_name> [OPTIONS]
```

Where:
- `<agent_name>` is the name of an agent defined in your project's `openmas_project.yml` file.

## Options

- `--output-file TEXT`: Name of the output Dockerfile (default: "Dockerfile")
- `--project-dir PATH`: Explicit path to the project directory containing `openmas_project.yml`
- `--python-version TEXT`: Python version to use (default: "3.10")
- `--use-poetry`: Use Poetry for dependency management instead of pip requirements.txt

## Purpose

This command provides a standardized way to create a Dockerfile for your agent by:

1. Finding your project root (location of `openmas_project.yml`)
2. Identifying the agent's location and dependencies
3. Creating a Dockerfile with appropriate build steps
4. Configuring the container for proper runtime behavior

## Example Usage

### Basic Usage

```bash
# Generate a Dockerfile for the 'orchestrator' agent in the current project
openmas generate-dockerfile orchestrator
```

This will create a `Dockerfile` in the current directory.

### Specifying an Output File

```bash
# Generate a Dockerfile with a custom name
openmas generate-dockerfile worker --output-file Dockerfile.worker
```

### Using Poetry for Dependencies

```bash
# Generate a Dockerfile that uses Poetry for dependency management
openmas generate-dockerfile orchestrator --use-poetry
```

### Specifying Python Version

```bash
# Generate a Dockerfile using Python 3.11
openmas generate-dockerfile orchestrator --python-version 3.11
```

## Example Dockerfile Output

Here's an example of a generated Dockerfile:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copy project files
COPY . /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV AGENT_NAME="orchestrator"
ENV PYTHONPATH="/app"

# Expose port (if your agent uses HTTP)
EXPOSE 8000

# Run the agent
CMD ["openmas", "run", "orchestrator"]
```

## Best Practices

1. **Review the generated Dockerfile**: While the command creates a good starting point, you might need to modify it for specific requirements.
2. **Add any required environment variables**: Add environment variables for API keys, service URLs, etc.
3. **Consider multi-stage builds**: For more complex applications, you might want to use multi-stage builds to reduce the final image size.

## Related Commands

- `openmas run`: Run an agent locally
- `openmas deps`: Manage project dependencies
