# Installation

Install OpenMAS using pip:

```bash
pip install openmas
```

## Prerequisites

*   Python 3.9+

## Virtual Environments

It is highly recommended to install OpenMAS within a virtual environment to avoid conflicts with other packages.

Using `venv`:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install openmas
```

Using `conda`:

```bash
conda create -n openmas-env python=3.10
conda activate openmas-env
pip install openmas
```

Using `Poetry` (for managing project dependencies):

Poetry manages environments automatically. If you are starting a new project with Poetry that will use OpenMAS:

```bash
# Initialize your project (if new)
poetry new my-openmas-project
cd my-openmas-project

# Add openmas - Poetry handles the virtualenv
poetry add openmas

# Activate the environment (optional, needed for direct script execution)
poetry shell
# Now you can run python scripts or use openmas commands directly
```
If adding to an existing Poetry project, simply run `poetry add openmas` within the project directory.

Using `uv` (a fast Python package installer and resolver):

```bash
# Create a virtual environment using uv
uv venv

# Activate the environment
source .venv/bin/activate # On Windows use `.venv\Scripts\activate`

# Install openmas using uv
uv pip install openmas
```

## Optional Dependencies

OpenMAS has a modular design. The core package is lightweight, and you can install optional features based on your needs:

*   **MCP Integration:** For using the Model Context Protocol.
*   **gRPC Communication:** For using gRPC for agent communication.
*   **MQTT Communication:** For using MQTT for agent communication.

Install optional dependencies using brackets:

```bash
# Install MCP support
pip install 'openmas[mcp]'

# Install gRPC support
pip install 'openmas[grpc]'

# Install MQTT support
pip install 'openmas[mqtt]'

# Install multiple optional dependencies
pip install 'openmas[mcp,grpc]'

# Install all optional dependencies
pip install 'openmas[all]'
```

If you are using Poetry in your project:

```bash
# Add core openmas
poetry add openmas

# Add optional dependencies
poetry add 'openmas[mcp]'
poetry add 'openmas[mcp,grpc,mqtt]'
```
