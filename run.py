#!/usr/bin/env python3
"""Entry point used by the Herdr plugin manifest.

Herdr runs this file as `python3 run.py`, and `run.py` dispatches by itself:

- event hooks: HERDR_PLUGIN_EVENT / HERDR_PLUGIN_EVENT_JSON are set
- plugin actions: the first argv item is the action id (init/test/status/toggle)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from herdr_webhook_notify.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
