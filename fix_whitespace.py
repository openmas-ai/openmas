#!/usr/bin/env python3
"""Utility script to remove trailing whitespace from source files."""

with open("src/openmas/agent/base.py", "r") as f:
    content = f.read()
content = content.replace("        \n", "\n")
content = content.replace("    \n", "\n")
with open("src/openmas/agent/base.py", "w") as f:
    f.write(content)

with open("src/openmas/cli/main.py", "r") as f:
    content = f.read()
content = content.replace("        \n", "\n")
content = content.replace("    \n", "\n")
with open("src/openmas/cli/main.py", "w") as f:
    f.write(content)

with open("tests/unit/agent/test_agent.py", "r") as f:
    content = f.read()
content = content.replace("        \n", "\n")
content = content.replace("    \n", "\n")
with open("tests/unit/agent/test_agent.py", "w") as f:
    f.write(content)

print("Whitespace fixed in source files.")
