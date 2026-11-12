"""Alias entrypoint: `python3 main.py` behaves exactly like `python3 server.py`."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.server import app, main  # noqa: E402  (path setup must run first)

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()
