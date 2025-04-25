"""This conftest.py file helps with pytest imports for the example tests."""

import sys
from pathlib import Path

# Add the example directory to the sys.path so modules can be imported
example_dir = Path(__file__).parent
sys.path.insert(0, str(example_dir))
