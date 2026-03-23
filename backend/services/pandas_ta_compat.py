from __future__ import annotations

import sys
import types
from typing import Any


def _install_windows_posix_shim() -> None:
    """Provide a minimal 'posix' module for broken pandas_ta imports on Windows."""
    if sys.platform != "win32" or "posix" in sys.modules:
        return

    shim = types.ModuleType("posix")

    def _pread(*_args: Any, **_kwargs: Any):
        raise NotImplementedError("posix.pread is not available on Windows")

    shim.pread = _pread  # type: ignore[attr-defined]
    sys.modules["posix"] = shim


def load_pandas_ta():
    """Import pandas_ta with compatibility guards."""
    _install_windows_posix_shim()
    import pandas_ta as ta  # type: ignore

    return ta
