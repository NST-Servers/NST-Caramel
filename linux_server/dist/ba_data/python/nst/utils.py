"""Mixed utilities module."""

from __future__ import annotations

import bascenev1 as bs
from bascenev1lib.gameutils import SharedObjects

import bauiv1 as bui

import babase

import ctypes
import os
import random
import math

COLOR_ATTENTION = (1, 1, 0.3)
COLOR_ERROR = (1, 0.2, 0.2)


def send(msg: str, condition: bool = True) -> None:
    """Print something on-screen and log it in console."""
    if not condition:
        return
    # Get source file's name
    import inspect

    source = inspect.getmodule(inspect.stack()[1][0]).__name__ or 'file' + '.py'
    # Send the messages wherever!
    print(f"[{source}]: {msg}")
    bs.broadcastmessage(f'{msg}')


def clone_object(cls) -> object:
    """Clone an object."""
    return type(cls.__name__, cls.__bases__, dict(cls.__dict__))


def replace_methods(target_object: object, source_object: object) -> None:
    """Replace an object's methods."""
    for name, v in source_object.__dict__.items():
        if callable(v) or isinstance(v, (staticmethod, classmethod)):
            setattr(target_object, name, v)