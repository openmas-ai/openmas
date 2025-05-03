"""CLI module for OpenMAS."""

import os
import sys

# Only load the CLI main entry point if not in test mode
# This avoids circular imports when testing individual CLI components
if "pytest" not in sys.modules:  # pragma: no cover
    from openmas.cli.main import main

    __all__ = ["main"]
else:
    __all__ = []
