#!/usr/bin/env python
"""Entry point script to run the Flask webapp."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp.app import run_webapp

if __name__ == "__main__":
    run_webapp()


