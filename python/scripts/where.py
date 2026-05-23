"""Prints the current cursor position. Hover over the Buy / Sell buttons
in PaperTradingDesk and read the numbers, then plug them into
scripted_baseline.py.

Usage:
    python -m scripts.where
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import time

user32 = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def main():
    print("Hover over a target. Ctrl+C to quit.")
    try:
        while True:
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            print(f"\r({pt.x}, {pt.y})    ", end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
