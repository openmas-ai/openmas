"""Integration test to validate the Getting Started guide.

This test automates the steps described in the Getting Started guide to ensure
that the guide remains accurate and the functionality works as described.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Set, Tuple

import pytest


@pytest.fixture
def setup_guide_test_env(tmp_path) -> Tuple[Path, Path]:
    """Set up a clean environment for testing the Getting Started guide.

    Creates a temporary directory and a virtual environment,
    installs OpenMAS from the local source.

    Args:
        tmp_path: pytest's builtin temporary path fixture

    Returns:
        Tuple containing:
        - Path to the temporary directory
        - Path to the virtual environment's openmas executable
    """
    # Create a virtual environment
    venv_path = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    # Determine paths to Python and pip in the virtual environment
    if os.name == "nt":  # Windows
        python_path = venv_path / "Scripts" / "python.exe"
        pip_path = venv_path / "Scripts" / "pip.exe"
        openmas_path = venv_path / "Scripts" / "openmas.exe"
    else:  # Unix-like
        python_path = venv_path / "bin" / "python"
        pip_path = venv_path / "bin" / "pip"
        openmas_path = venv_path / "bin" / "openmas"

    # Get the path to the root of the current project
    project_root = Path(__file__).parent.parent.parent

    # Install OpenMAS from the local source
    subprocess.run([str(pip_path), "install", "-e", str(project_root)], check=True)

    # Verify OpenMAS is installed
    subprocess.run(
        [str(python_path), "-c", "import openmas; print(openmas.__version__)"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Ensure the openmas executable is available
    assert openmas_path.exists(), f"OpenMAS executable not found at {openmas_path}"

    # Yield the paths for use in the test
    yield tmp_path, openmas_path

    # Cleanup is handled automatically by pytest through tmp_path


@pytest.mark.integration
def test_getting_started_workflow(setup_guide_test_env):
    """Test the complete workflow from the Getting Started guide."""
    # Get the paths from the fixture
    tmp_path, openmas_path = setup_guide_test_env

    # Step 1: Initialize a new project
    project_name = "my_first_mas"
    project_path = tmp_path / project_name

    # Run the init command
    init_result = subprocess.run(
        [str(openmas_path), "init", project_name], cwd=str(tmp_path), capture_output=True, text=True
    )

    # Check that the command succeeded
    assert init_result.returncode == 0, f"Init command failed with output: {init_result.stderr}"

    # Check that the project directory and key files exist
    assert project_path.exists(), f"Project directory {project_path} was not created"
    assert (project_path / "openmas_project.yml").exists(), "openmas_project.yml not found"
    assert (project_path / "agents").exists(), "agents directory not found"
    assert (project_path / "agents" / "__init__.py").exists(), "agents/__init__.py not found"
    assert (project_path / "agents" / "sample_agent").exists(), "sample_agent directory not found"
    assert (project_path / "agents" / "sample_agent" / "__init__.py").exists(), "sample_agent/__init__.py not found"
    assert (project_path / "agents" / "sample_agent" / "agent.py").exists(), "sample_agent/agent.py not found"

    # Step 3: Run the sample agent
    # Start the agent in a separate process so we can terminate it after checking output
    run_process = subprocess.Popen(
        [str(openmas_path), "run", "sample_agent"],
        cwd=str(project_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
        universal_newlines=True,
    )

    # Wait a few seconds to give the agent time to start and output logs
    start_time = time.time()
    max_wait = 10  # Maximum seconds to wait
    expected_log_messages = ["Sample agent initializing", "Sample agent running", "Sample agent tick 0"]

    # Collect output lines and check for expected messages
    output_lines: List[str] = []
    found_messages: Set[str] = set()

    try:
        # Process output lines until we find all expected messages or timeout
        while time.time() - start_time < max_wait and len(found_messages) < len(expected_log_messages):
            line = run_process.stdout.readline()
            if not line:
                break

            output_lines.append(line)
            for msg in expected_log_messages:
                if msg in line and msg not in found_messages:
                    found_messages.add(msg)
    finally:
        # Terminate the process gracefully
        if run_process.poll() is None:  # Process is still running
            if os.name == "nt":  # Windows
                run_process.send_signal(signal.CTRL_C_EVENT)
            else:  # Unix-like
                run_process.send_signal(signal.SIGINT)

            # Give it a moment to shut down gracefully
            try:
                run_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it didn't shut down gracefully
                run_process.kill()
                run_process.wait()

    # Check that we found all expected log messages
    for msg in expected_log_messages:
        assert msg in found_messages, f"Expected log message '{msg}' not found in output"

    # Step 4: Modify the agent
    agent_file = project_path / "agents" / "sample_agent" / "agent.py"

    # Read the current content
    with open(agent_file, "r") as f:
        content = f.read()

    # Modify the log message
    modified_content = content.replace(
        'self.logger.info("Sample agent running...")', 'self.logger.info("My first agent is running!")'
    )

    # Write the modified content back
    with open(agent_file, "w") as f:
        f.write(modified_content)

    # Step 5: Run the modified agent
    run_modified_process = subprocess.Popen(
        [str(openmas_path), "run", "sample_agent"],
        cwd=str(project_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    # Wait and check for modified log message
    start_time = time.time()
    modified_message_found = False
    modified_output_lines: List[str] = []

    try:
        while time.time() - start_time < max_wait and not modified_message_found:
            line = run_modified_process.stdout.readline()
            if not line:
                break

            modified_output_lines.append(line)
            if "My first agent is running!" in line:
                modified_message_found = True
    finally:
        # Terminate the process
        if run_modified_process.poll() is None:
            if os.name == "nt":
                run_modified_process.send_signal(signal.CTRL_C_EVENT)
            else:
                run_modified_process.send_signal(signal.SIGINT)

            try:
                run_modified_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                run_modified_process.kill()
                run_modified_process.wait()

    # Check that we found the modified log message
    assert modified_message_found, "Modified log message 'My first agent is running!' not found in output"
