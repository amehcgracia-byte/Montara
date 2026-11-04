"""Small Windows-only helpers for the existing Montara Companion.

Keep platform-specific discovery and dialogs separate from its HTTP protocol.
This module has no external dependencies and performs no filesystem writes.
"""
from __future__ import annotations

import os
from pathlib import Path


def drive_types():
    """Return (drive, Win32 GetDriveTypeW value) for locally mounted drives."""
    if os.name != "nt":
        return []
    try:
        import ctypes

        kernel = ctypes.windll.kernel32
        mask = int(kernel.GetLogicalDrives())
        found = []
        for i in range(26):
            if mask & (1 << i):
                drive = f"{chr(65+i)}:\\"
                found.append((drive, int(kernel.GetDriveTypeW(drive))))
        return found
    except (AttributeError, OSError, ValueError):
        return []


def search_roots(home=None, environ=None, drives=None):
    """Windows known folders plus removable/secondary drives, without crawling C:\\.

    A OneDrive redirected Desktop/Documents is common. In addition to the
    USERPROFILE folders, consult the existing OneDrive roots. Paths are
    candidates only; the calling companion filters them using is_dir().
    """
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    roots = []
    custom = env.get("MONTARA_COMPANION_ROOTS", "")
    if custom:
        roots.extend(Path(p).expanduser() for p in custom.split(";") if p)

    known = ("Desktop", "Videos", "Downloads", "Documents", "Pictures")
    roots.extend(home / name for name in known)
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        folder = env.get(key)
        if folder:
            base = Path(folder)
            roots.extend(base / name for name in known)

    system = (env.get("SystemDrive") or "C:").upper().rstrip("\\/")
    for drive, kind in (drive_types() if drives is None else drives):
        # DRIVE_REMOVABLE=2, DRIVE_FIXED=3. Secondary fixed drive includes
        # USB drives that Windows reports as fixed. Skip network/CD/RAM.
        if kind in (2, 3) and drive[:2].upper() != system:
            roots.append(Path(drive))
    return list(dict.fromkeys(roots))


def choose_folder(prompt):
    """Use the native Windows folder picker. Return None on cancellation/failure."""
    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        try:
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(parent=root, title=prompt, mustexist=True)
            return Path(selected) if selected else None
        finally:
            root.destroy()
    except (ImportError, RuntimeError, OSError):
        # No graphical desktop / Tk not installed. Never silently select HOME.
        return None
