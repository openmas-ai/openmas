# Installation

This guide explains how to install the `openmas` package.

## Prerequisites

* Python 3.10 or newer.

## Standard Installation

The quickest way to install OpenMAS is using pip:

```bash
pip install openmas
```

## Using Virtual Environments (Recommended)

=== "venv (Built-in)"

    Python's built-in tool for creating lightweight virtual environments.

    1.  **Create the environment:**
        ```bash
        python -m venv .venv # Or choose a different name like 'venv'
        ```

    2.  **Activate the environment:**
        * macOS/Linux: `source .venv/bin/activate`
        * Windows (Command Prompt): `.venv\Scripts\activate.bat`
        * Windows (PowerShell): `.venv\Scripts\Activate.ps1`

    3.  **Install OpenMAS:**
        ```bash
        pip install openmas
        ```

=== "Poetry"

    A modern tool for Python dependency management and packaging, which automatically handles virtual environments.

    1.  **Add OpenMAS to your Poetry project:**
        (Run this command inside your project directory where `pyproject.toml` is located)
        ```bash
        poetry add openmas
        ```
        * Poetry will create a virtual environment if one doesn't exist for the project and install `openmas` into it.
        * If you haven't initialized your project with Poetry yet, run `poetry init` first or `poetry new your-project-name`.

    2.  **Run commands within the environment:**
        * Either prefix commands with `poetry run` (e.g., `poetry run python your_script.py`)
        * Or activate the shell explicitly: `poetry shell`

=== "uv"

    An extremely fast Python package installer and resolver, capable of replacing pip and venv.

    1.  **Create the environment:**
        ```bash
        uv venv
        ```

    2.  **Activate the environment:**
        * macOS/Linux: `source .venv/bin/activate`
        * Windows (Command Prompt): `.venv\Scripts\activate.bat`
        * Windows (PowerShell): `.venv\Scripts\Activate.ps1`

    3.  **Install OpenMAS using uv:**
        ```bash
        uv pip install openmas
        ```

=== "conda"

    A popular package and environment manager, often used in data science.

    1.  **Create the environment:**
        ```bash
        conda create -n openmas-env python=3.10 # Or your preferred Python version
        ```

    2.  **Activate the environment:**
        ```bash
        conda activate openmas-env
        ```

    3.  **Install OpenMAS:**
        ```bash
        pip install openmas
        # Note: You can use pip within a conda environment.
        ```

---

## Optional Dependencies

OpenMAS is modular. Install optional features as needed:

* `mcp`: Model Context Protocol integration.
* `grpc`: gRPC communication support.
* `mqtt`: MQTT communication support.
* `all`: All optional dependencies.

Install these extras using brackets `[]`. The specific command depends on how you manage your environment:

* **If using `pip` or `uv`:**
    ```bash
    # Example: Install MCP and gRPC support
    pip install 'openmas[mcp,grpc]'
    # Or using uv:
    # uv pip install 'openmas[mcp,grpc]'

    # Example: Install all extras
    pip install 'openmas[all]'
    # Or using uv:
    # uv pip install 'openmas[all]'
    ```

* **If using `Poetry`:**
    ```bash
    # Example: Add MCP and gRPC support (Poetry handles the environment)
    poetry add 'openmas[mcp,grpc]'

    # Example: Add all extras
    poetry add 'openmas[all]'
    ```

## Verify Installation (Optional)

After installation, you can verify it using one of these methods:

1. Use the `--version` flag to quickly check the installed version:

```bash
openmas --version
```

2. Use the `info` command which shows detailed information about the installation including version and module information:

```bash
openmas info
```

Example output:
```
OpenMAS version: 0.1.0
Python version: 3.10.17 (CPython)
Platform: macOS-15.4.1-arm64-arm-64bit

Optional modules:
  base       ✓
  http       ✓
  mcp        ✓
  grpc       ✗
  mqtt       ✓

For more information, visit: https://docs.openmas.ai/
```

For JSON output (useful for scripting), use:
```bash
openmas info --json
```

3. You can also verify installation by importing the package:

```bash
python -c "import openmas; print(openmas.__version__)"
```
