#!/usr/bin/python
import importlib
from pathlib import Path
import sys

sys.path.insert(0, "/usr/lib/lynux")
from lynux.common import main_guard

module = {"lynux-state": "state", "lynux-iso": "iso", "lynux-harness": "harness",
          "lynux-welcome": "welcome"}[Path(sys.argv[0]).name]
main_guard(importlib.import_module(f"lynux.{module}").main)
