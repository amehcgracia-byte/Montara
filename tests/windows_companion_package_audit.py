"""W3P Windows portable acceptance-package audit (no publishing).

Only inspects the just-built laboratory folder. It records a deterministic
file inventory, sizes and SHA-256 checksums and deliberately does not upload
or redistribute bundled third-party binaries.
"""
import hashlib
import json
import os
from pathlib import Path
import sys


REQUIRED = ("MontaraCompanion.exe", "windows_tray.ps1",
            "bin/ffmpeg.exe", "bin/ffprobe.exe")


def main():
    if os.name != "nt":
        raise RuntimeError("W3P package audit must run on Windows")
    directory = Path(sys.argv[1]).resolve()
    assert directory.is_dir(), directory
    for name in REQUIRED:
        file = directory / name
        assert file.is_file() and file.stat().st_size > 100, f"Missing/empty: {name}"
    assert (directory / "_internal").is_dir(), "PyInstaller one-folder libraries absent"
    assert not list(directory.rglob("*.part.mp4")), "Partial media leaked into package"
    assert not list(directory.rglob("*.mp4")), "No user videos may be bundled"
    assert not list(directory.rglob("*.log")), "No personal diagnostics may be bundled"
    assert not list(directory.rglob("*.pyc")) or (directory / "_internal").is_dir()

    manifest = []
    for file in sorted(directory.rglob("*")):
        if not file.is_file():
            continue
        relative = file.relative_to(directory).as_posix()
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append({
            "path": relative,
            "size_bytes": file.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    total = sum(item["size_bytes"] for item in manifest)
    report = {
        "product": "Montara Companion",
        "profile": "windows-one-folder-test-only",
        "redistribution_authorized": False,
        "requires_license_review": True,
        "file_count": len(manifest),
        "total_bytes": total,
        "files": manifest,
    }
    out = directory.parent / "W3P-package-audit.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert len(manifest) >= 6, "Package unexpectedly small"
    print(f"W3P_PACKAGE_AUDIT_PASS files={len(manifest)} bytes={total}")
    for name in REQUIRED:
        row = next(item for item in manifest if item["path"] == name)
        print(f"W3P_CORE_FILE {name} {row['size_bytes']} sha256:{row['sha256']}")
    print("W3P_REDISTRIBUTION_BLOCKED_LICENSE_REVIEW", flush=True)


if __name__ == "__main__":
    main()
