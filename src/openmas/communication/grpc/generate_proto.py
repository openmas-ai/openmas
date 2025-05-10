#!/usr/bin/env python
"""Script to generate Python code from the gRPC proto file."""

import os
import subprocess
import sys
from pathlib import Path

# Check for the environment variable to skip proto generation
if os.environ.get("SKIP_PROTO_GEN") == "true":
    print("Skipping proto generation as SKIP_PROTO_GEN is set to true")
    sys.exit(0)


def generate_proto(proto_file: str, output_dir: str) -> None:
    """Generate Python code from a proto file.

    Args:
        proto_file: Path to the proto file
        output_dir: Directory where the generated code should be placed
    """
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Command to generate the Python code
    command = [
        "python",
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={os.path.dirname(proto_file)}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        proto_file,
    ]

    print(f"Running command: {' '.join(command)}")

    # Run the command
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Successfully generated proto code.")
    except subprocess.CalledProcessError as e:
        print(f"Error generating proto code: {e}")
        print(e.stdout)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

    # Fix imports in the generated files
    fix_imports(output_dir)


def fix_imports(output_dir: str) -> None:
    """Fix relative imports in generated files.

    Args:
        output_dir: Directory containing the generated code
    """
    # We only need to fix the pb2_grpc file
    pb2_grpc_file = os.path.join(output_dir, "openmas_pb2_grpc.py")

    # Fix imports in the pb2_grpc file
    if os.path.exists(pb2_grpc_file):
        with open(pb2_grpc_file, "r") as f:
            content = f.read()

        # Replace 'import openmas_pb2' with relative import
        content = content.replace("import openmas_pb2 as openmas__pb2", "from . import openmas_pb2 as openmas__pb2")

        with open(pb2_grpc_file, "w") as f:
            f.write(content)

        print(f"Fixed imports in {pb2_grpc_file}")


if __name__ == "__main__":
    # Get the current directory (where this script is located)
    current_dir = Path(__file__).parent.absolute()

    # Path to the proto file
    proto_file = os.path.join(current_dir, "openmas.proto")

    # Output directory (same as current directory)
    output_dir = str(current_dir)

    if not os.path.exists(proto_file):
        print(f"Proto file not found: {proto_file}", file=sys.stderr)
        sys.exit(1)

    generate_proto(proto_file, output_dir)
