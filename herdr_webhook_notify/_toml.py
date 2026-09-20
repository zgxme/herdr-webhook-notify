"""TOML reading that works on Python 3.9 and newer.

`tomllib` is part of the standard library from Python 3.11. Older interpreters
fall back to the vendored copy of tomli (MIT) that ships with the plugin.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

try:  # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - depends on interpreter version
    from vendor import tomli as _toml

loads = _toml.loads
TOMLDecodeError = _toml.TOMLDecodeError

__all__ = ["loads", "TOMLDecodeError"]
