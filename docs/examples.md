# OpenMAS Examples

The `examples/` directory within the OpenMAS source code repository plays a crucial role in the development and usability of the framework.

*(Based on Section 10 of the OpenMAS Design Document v0.2.3)*

## Purpose of Examples

The examples serve multiple key purposes:

1.  **Contributor Testing & Dogfooding:**
    * Examples provide concrete, runnable scenarios used in the framework's internal testing pipeline (via `tox`).
    * Running tests against these examples ensures that core framework features, SDK components, and CLI commands work as expected across different use cases (e.g., various communicators, basic agent patterns).
    * The process of creating and maintaining these examples acts as a primary "dogfooding" mechanism, forcing developers contributing to OpenMAS to use the framework's own tools and abstractions, thereby identifying usability issues or bugs.

2.  **User Learning & Guidance:**
    * While not installed via `pip`, users can browse the examples directly in the [OpenMAS GitHub repository](https://github.com/dylangames/openmas/tree/main/examples).
    * They serve as practical, self-contained illustrations of how to implement specific features (like using a particular communicator), patterns (like basic request-response), or integrations.
    * The documentation often references these examples or includes snippets from them to provide concrete context.
    * *(Future Consideration: A command like `openmas examples download <example_name>` might be added to easily fetch example code locally.)*

3.  **Best Practice Demonstration:**
    * Examples showcase recommended ways to structure simple OpenMAS projects, define agents, configure communication, handle basic lifecycle events, and use the `openmas` CLI for local execution.

## Example Structure

Examples are organized by topic or feature within the `examples/` directory. Each specific, runnable scenario resides in its own subdirectory (a "leaf example directory").

    examples/
    ├── 00_hello_agent/
    │   ├── hello_agent/          # Leaf example: Single basic agent
    │   │   ├── agents/hello_agent/agent.py # The agent code
    │   │   ├── openmas_project.yml # Minimal project config for this example
    │   │   ├── requirements.txt      # Example-specific Python deps (often empty)
    │   │   ├── test_example.py       # Internal test script (uses pytest)
    │   │   └── README.md             # How to run THIS specific example manually
    │   └── hello_multiagent/     # Leaf example: Two agents communicating
    │       └── ... (similar files: agents/, openmas_project.yml, etc.)
    ├── 01_communication_basics/
    │   ├── http_client_server/   # Leaf example: HTTP request/response
    │   │   └── ...
    │   └── mcp/
    │       ├── mcp_sse_client_server/ # Leaf example: MCP over SSE
    │       │   └── ...
    │       └── mcp_stdio_tool/      # Leaf example: MCP over stdio
    │           └── ...
    ├── 02_configuration/
    │   └── layered_config/       # Leaf example: Demonstrating config sources
    │       └── ...
    ├── ... (other categories like patterns, specific integrations) ...
    └── README.md                   # Explains overall example structure & how to run tests

Each leaf example directory typically contains:
* An `agents/` subdirectory with the agent code (`agent.py`).
* A minimal `openmas_project.yml` defining the agent(s) for that example.
* A `requirements.txt` for any dependencies specific to that example (beyond the core `openmas` framework).
* A `README.md` explaining the purpose of the example and how to run it manually (usually involving `openmas run`).
* A `test_example.py` file used *internally* by the framework's `tox` setup to validate the example's correctness. **This test file is for framework testing, not a template for end-user application testing.**

## Using the Examples

1.  **Browse:** Explore the `examples/` directory on GitHub to find scenarios relevant to your needs.
2.  **Understand:** Read the `README.md` within a specific example directory.
3.  **Adapt:** Copy relevant code snippets (agent structure, communicator configuration, handler registration) into your own OpenMAS project.
4.  **Run Manually (Optional):** To run an example locally, you would typically:
    * Clone the OpenMAS repository (`git clone https://github.com/dylangames/openmas.git`).
    * Navigate into a specific example directory (e.g., `cd openmas/examples/00_hello_agent/hello_agent/`).
    * Set up a virtual environment and install dependencies (`python -m venv .venv`, `source .venv/bin/activate`, `pip install -e ../../..`, `pip install -r requirements.txt`). Note the `-e ../../..` installs the main OpenMAS package from the repo root in editable mode.
    * Run the agent using the `openmas` CLI (`openmas run hello_agent`). Refer to the example's `README.md` for specific instructions.

## Testing Strategy (`tox` + `pytest`)

The OpenMAS project uses `tox` and `pytest` to automatically test the examples as part of its Continuous Integration (CI) process.

* `tox.ini` in the repository root defines test environments for each example.
* Each environment installs `openmas` and the example's specific dependencies.
* `tox` runs the `pytest` command targeting the `test_example.py` file within the example directory.
* The `test_example.py` scripts use `pytest` fixtures and assertions to instantiate the example agent(s), trigger their logic (e.g., by calling handlers or simulating communication via `MockCommunicator` or `AgentTestHarness`), and verify the expected outcomes. This ensures the framework behaves correctly for that example scenario.
