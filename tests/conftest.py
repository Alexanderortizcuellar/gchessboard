"""
conftest.py — pytest configuration for the tests/ folder.

Adds the project root to sys.path so that `from src.xxx import ...`
works correctly when pytest is run from either the root or the tests/ dir.
"""

import sys
import os

# Insert the project root (one level up from this file) at the front of sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
