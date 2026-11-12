"""Root entrypoint for Hearth.

Some launchers and framework detectors execute the file that defines the Sanic
app instead of running a module. This shim keeps every documented shape working:

    python3 server.py          # this file
    python3 app/server.py      # the app module, executed as a script
    python3 -m app.server      # the module, run as a package member
    sh start.sh / sh install.sh

All of them boot the same application and bind 0.0.0.0 on $PORT.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.server import app, main  # noqa: E402  (path setup must run first)

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()
