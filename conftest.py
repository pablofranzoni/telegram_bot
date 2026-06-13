"""Root conftest.py — adds the project root to sys.path so all modules are importable."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
