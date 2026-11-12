"""Launch the pinned, isolated SMART beta Companion without changing old installs.

Use Python 3.11+; the proxy and local HTTP protocol only require stdlib +
FFmpeg on PATH. Original-quality Stage rendering requires a separately
installed, revision-matched native renderer (see README in package).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ORIGIN = "https://montara-owner.memoriainvalida001.workers.dev"
ENGINE = "b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b"


def main() -> int:
    if sys.platform != "win32":
        print("This SMART beta launcher is intended for Windows.")
        return 2

    install = Path(__file__).resolve().parent
    old_port = os.environ.get("MONTARA_COMPANION_PORT", "47820")
    if old_port != "47820":
        print("The beta requires localhost port 47820; refusing a different port.")
        return 2

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("FFmpeg / FFprobe not on PATH. Existing Companion was not changed.")
        return 3

    # A distinct HOME means no modification or migration of old Companion
    # cache, project bindings, local render jobs or original locations.
    os.environ["MONTARA_COMPANION_HOME"] = str(
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MontaraSMARTBeta"
    )
    os.environ["MONTARA_COMPANION_PORT"] = "47820"
    # Explicitly allow only the original Owner beta and isolated H4 origin.
    os.environ["MONTARA_COMPANION_ORIGINS"] = (
        "https://montara-owner(?:-h4)?\\.memoriainvalida001\\.workers\\.dev"
    )
    print("Montara SMART Beta - original Chema Companion, private isolated data")
    print("Beta origin:", ORIGIN)
    print("State folder:", os.environ["MONTARA_COMPANION_HOME"])
    print("Engine required for Stage final:", ENGINE)
    print("The window must remain open while editing. Ctrl+C closes the beta.")
    print("If another Companion already listens on 47820, this beta will not replace it.")
    try:
        import companion
        return companion.main()
    except Exception as exc:
        print("Companion failed:", type(exc).__name__, str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
