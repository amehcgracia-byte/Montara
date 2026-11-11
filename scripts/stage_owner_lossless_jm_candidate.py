"""Build a separate, immutable-versioned Owner JM candidate for lossless audio.

Does not mutate source, main, Engine, systemd, jobs or user data.
The installed worker continues to run from the previous pinned JM bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from urano.jm_bundle_manifest import (
    verify_jm_bundle_files, verify_pinned_chema_manifest,
)
from urano.jm_private_proxy_overlay import (
    patched_reviewed_private_audio_overlay,
)


def stage_candidate(source: Path, destination: Path) -> dict:
    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Reviewed JM bundle directory required")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Never overwrite an existing JM bundle")
    if destination == source or source in destination.parents:
        raise ValueError("Candidate must be outside reviewed source")
    original_manifest_path = source / "montara-jm-bundle.json"
    manifest = json.loads(original_manifest_path.read_text(encoding="utf-8"))
    verify_pinned_chema_manifest(
        manifest,
        expected_editor_commit=manifest["editor_commit"],
        expected_engine_commit=manifest["engine_commit"],
        expected_private_preview_limit_mib=manifest["private_proxy_limit_mib"],
    )
    verify_jm_bundle_files(source, manifest)
    if source.name != "jm-" + manifest["editor_commit"]:
        raise ValueError("JM source directory does not match pinned editor")
    if destination.name != source.name:
        raise ValueError("Keep exact pinned JM directory name under a new parent")

    original_path = source / "resumable_upload.py"
    old_content = original_path.read_bytes()
    candidate_content = patched_reviewed_private_audio_overlay(
        old_content.decode("utf-8")).encode("utf-8")
    if candidate_content == old_content:
        raise ValueError("No reviewed source change")

    pending = destination.with_name(destination.name + ".staging")
    if pending.exists() or pending.is_symlink():
        raise FileExistsError("Refuse to replace an existing staging directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Source submodule .git internals are root-owned and unnecessary for
        # running a pinned JM worker. Copy application files, not Git object
        # stores or cached bytecode; keep the checked-in mixer code itself.
        shutil.copytree(source, pending, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__"))
        candidate_upload = pending / "resumable_upload.py"
        # This file must be a separate inode; never write through a link.
        if candidate_upload.is_symlink() or not candidate_upload.is_file():
            raise ValueError("Unexpected candidate uploader")
        candidate_upload.write_bytes(candidate_content)
        new_manifest = dict(manifest)
        new_manifest["patched_resumable_sha256"] = hashlib.sha256(
            candidate_content).hexdigest()
        (pending / "montara-jm-bundle.json").write_text(
            json.dumps(new_manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        verify_jm_bundle_files(pending, new_manifest)
        if original_path.read_bytes() != old_content:
            raise RuntimeError("Reviewed JM source unexpectedly changed")
        os.rename(pending, destination)
        return new_manifest
    except BaseException:
        # Pending was uniquely allocated by this process only; no existing
        # installation and no user project is ever removed.
        if pending.is_dir() and not pending.is_symlink():
            shutil.rmtree(pending)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(stage_candidate(args.source, args.destination),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
