# OpenMAS Examples

The `examples/` directory within the OpenMAS source code repository plays a crucial role in the development and usability of the framework.

## Purpose of Examples

The examples serve multiple key purposes:

1.  **Contributor Testing & Dogfooding:**
    * Examples provide concrete, runnable scenarios used in the framework's internal testing pipeline (`tox`).
    * Running tests against these examples ensures that core framework features, SDK components, and CLI commands work as expected across different use cases (e.g., various communicators, agent patterns).
    * The process of creating and maintaining these examples acts as a primary "dogfooding" mechanism, forcing developers contributing to OpenMAS to use the framework's own tools and abstractions, thereby identifying usability issues or bugs.

2.  **User Learning & Guidance:**
    * While not installed via `pip`, users can browse the examples directly in the [OpenMAS GitHub repository](https://github.com/dylangames/openmas/tree/main/examples).
    * They serve as practical, self-contained illustrations of how to implement specific features (like using a particular communicator), patterns (like request-response), or integrations.
    * The documentation often references these examples or includes snippets from them to provide concrete context.
    * *(Future Consideration: A command like `openmas examples download <example_name>` might be added to easily fetch example code locally.)*

3.  **Best Practice Demonstration:**
    * Examples showcase recommended ways to structure simple OpenMAS projects, define agents, configure communication, handle basic lifecycle events, and use the `openmas` CLI for local execution.

## Example Structure

The `examples/` directory is organized as follows.  This documentation presents a categorized structure for improved user understanding.

### Conceptual Category View

The examples are organized into the following categories:

    examples/
    ├── example_00_hello_agent/                          # Basic agent run
    │   ├── 00_single/                                   # Leaf example: Single basic agent
    │   │   ├── agents/hello_agent_single/agent.py       # The agent code
    │   │   ├── openmas_project.yml                      # Minimal project config
    │   │   ├── requirements.txt                         # Example-specific Python deps
    │   │   ├── test_example.py                          # Internal test script (pytest)
    │   │   └── README.md                                # How to run THIS example
    │   └── 01_multi_mock/                               # Leaf example: Two agents communicating
    │       └── ... (similar files: agents/, openmas_project.yml, etc.)
    ├── example_01_communication_basics/                 # Communication Basics
    │   ├── http_client_server/                          # HTTP Communication
    │   ├── mcp_stdio_external/                          # MCP stdio Communication
    │   ├── mcp_sse_internal/                            # MCP SSE Communication
    │   ├── grpc_request_reply/                          # gRPC Communication
    │   ├── mq_publish_subscribe/                        # MQ Communication (RabbitMQ/Redis)
    │   └── README.md                                    # Category README
    ├── example_02_configuration/                        # Configuration
    │   └── layered_loading/                             # Layered Configuration
    │   └── README.md                                    # Category README
    ├── example_03_patterns/                             # Core Patterns
    │   ├── orchestrator_worker/                         # Orchestrator Pattern
    │   ├── chaining_sequence/                           # Chaining Pattern
    │   └── README.md                                    # Category README
    ├── example_04_agent_features/                       # Agent Features
    │   ├── mcp_tool_decorator/                          # MCP Tool Decorator
    │   ├── bdi_hooks/                                   # BDI Agent Usage
    │   └── README.md                                    # Category README
    ├── example_05_integrations/                         # Integrations
    │   ├── basic_llm/                                   # LLM Integration (OpenAI/Anthropic)
    │   └── README.md                                    # Category README
    ├── example_06_project_structure/                    # Project Structure
    │   ├── local_plugin/                                # Local Plugin
    │   ├── shared_code_usage/                           # Shared Code Usage
    │   └── README.md                                    # Category README
    ├── example_07_deployment_preview/                   # Deployment Preview
    │   └── simple_compose_setup/                        # Docker Compose Setup
    │   └── README.md                                    # Category README
    ├── example_08_mcp/                                  # MCP examples
    │   └── 01_mcp_sse_tool_call/                        # MCP SSE tool call
    │   └── 02_mcp_stdio_tool_call/                      # MCP stdio tool call
    │   └── README.md                                    # Category README


Each leaf example directory typically contains:

* An `agents/` subdirectory with the agent code (`agent.py`).
* A minimal `openmas_project.yml` defining the agent(s) for that example.
* A `requirements.txt` for any dependencies specific to that example (beyond the core `openmas` framework).
* A `README.md` explaining the purpose of the example and how to run it manually (usually involving `openmas run`).
* A `test_example.py` file used \*internally\* by the framework's `tox` setup to validate the example's correctness.  **This test file is for framework testing, not a template for end-user application testing.**

## Using the Examples

1.  **Browse:** Explore the `examples/` directory on GitHub to find scenarios relevant to your needs.
2.  **Understand:** Read the `README.md` within a specific example directory.
3.  **Adapt:** Copy relevant code snippets (agent structure, communicator configuration, handler registration) into your own OpenMAS project.
4.  **Run Manually (Optional):** To run an example locally, you would typically:
    * Clone the OpenMAS repository (`git clone https://github.com/dylangames/openmas.git`).
    * Navigate into a specific example directory (e.g., `cd openmas/examples/example_00_hello_agent/00_single`).
    * Set up a virtual environment and install dependencies (`python -m venv .venv`, `source .venv/bin/activate`, `pip install -e ../../..`, `pip install -r requirements.txt`).  Note the `-e ../../..` installs the main OpenMAS package from the repo root in editable mode.
    * Run the agent using the `openmas` CLI (`openmas run hello_agent`).  Refer to the example's `README.md` for specific instructions.

## Testing Strategy (`tox` + `pytest`)

The OpenMAS project uses `tox` and `pytest` to automatically test the examples as part of its Continuous Integration (CI) process.

* `tox.ini` in the repository root defines test environments for each example.
* Each environment installs `openmas` and the example's specific dependencies.
* `tox` runs the `pytest` command targeting the `test_example.py` file within the example directory.
* The `test_example.py` scripts use `pytest` fixtures and assertions to instantiate the example agent(s), trigger their logic (e.g., by calling handlers or simulating communication via `MockCommunicator` or `AgentTestHarness`), and verify the expected outcomes. This ensures the framework behaves correctly for that example scenario.
