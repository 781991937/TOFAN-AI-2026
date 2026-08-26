"""TOFAN AI core layer.

The core layer contains Python services that are independent from Telegram.
Telegram handlers are adapters around these services.
"""

from .runtime import PythonRuntime

__all__ = ["PythonRuntime"]
