#!/usr/bin/env python
"""Entry point script to run the Telegram bot."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main

if __name__ == "__main__":
    main()


