"""I56 build manifest: pin original Chema editor + gitlink Engine + Mixer.

No cloud, VM, CPU or Cloudflare assumptions. Never modifies a checkout,
submodule, root-owned bundle or live service. Manifest is a build artifact
verified by the trusted Linux broker before enabling a full JM worker.

The source pin prevents silently pairing new Chema UI with an old Engine,
especially when export/recovery behavior has changed between commits.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from urano.jm_private_proxy_overlay import (
    patched_original_resumable_upload, private_proxy_limit_mib,
)

_SHA = re.compile(r"[a-f0-9]{40}\Z")
_MANIFEST_KEYS = frozenset({
    "schema", "editor_commit", "engine_commit", "mixer_commit",
    "private_proxy_limit_mib", "patched_resumable_sha256",
})


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=30,
    ).stdout


def build_pinned_chema_manifest(
    repository: Path, editor_commit: str, *,
    private_preview_limit_mib: int = 256,
) -> dict:
    """Read only pinned objects from Chema's Git tree. No working tree edits."""
    private_proxy_limit_mib(private_preview_limit_mib)
    if not isinstance(editor_commit, str) or not _SHA.fullmatch(editor_commit):
        raise ValueError("Full reviewed Chema commit required")
    repo=Path(repository).resolve(strict=True)
    if _git(repo, "rev-parse", editor_commit).decode().strip() != editor_commit:
        raise ValueError("Not the requested Chema commit")
    def gitlink(name):
        line=_git(repo,"ls-tree",editor_commit,name).decode().strip()
        if not re.fullmatch(
                r"160000 commit ([a-f0-9]{40})\t"+name, line):
            raise ValueError("Missing immutable "+name+" submodule revision")
        return line.split()[2]
    original=_git(repo,"show",editor_commit+":resumable_upload.py").decode("utf-8")
    patched=patched_original_resumable_upload(original)
    if not _git(repo,"show",editor_commit+":app.py"):
        raise ValueError("Missing Chema original Flask application")
    if not _git(repo,"show",editor_commit+":web/montara.js"):
        raise ValueError("Missing Chema original editor")
    return {
        "schema":1,
        "editor_commit":editor_commit,
        "engine_commit":gitlink("engine"),
        "mixer_commit":gitlink("mixer"),
        "private_proxy_limit_mib":private_preview_limit_mib,
        "patched_resumable_sha256":hashlib.sha256(
            patched.encode("utf-8")).hexdigest(),
    }


def verify_pinned_chema_manifest(
    manifest: dict, *,
    expected_editor_commit: str,
    expected_engine_commit: str,
    expected_private_preview_limit_mib: int,
) -> None:
    """Root broker checks exact approved source matrix, never client input."""
    if (not isinstance(manifest,dict)
            or set(manifest)!=_MANIFEST_KEYS
            or type(manifest.get("schema")) is not int
            or manifest["schema"]!=1
            or any(not isinstance(manifest.get(x),str)
                   or not _SHA.fullmatch(manifest[x])
                   for x in ("editor_commit","engine_commit","mixer_commit"))
            or not isinstance(manifest.get("patched_resumable_sha256"),str)
            or not re.fullmatch(r"[0-9a-f]{64}",
                                manifest["patched_resumable_sha256"])
            or type(manifest.get("private_proxy_limit_mib")) is not int):
        raise ValueError("Untrusted original JM bundle manifest")
    private_proxy_limit_mib(expected_private_preview_limit_mib)
    if (manifest["editor_commit"] != expected_editor_commit
            or manifest["engine_commit"] != expected_engine_commit
            or manifest["private_proxy_limit_mib"]
                 != expected_private_preview_limit_mib):
        raise ValueError("Chema editor, Engine or private proxy profile mismatch")


def verify_jm_bundle_files(bundle_root: Path, manifest: dict) -> None:
    """Check source hash of actual staged upload module before launching."""
    root=Path(bundle_root)
    if (root.is_symlink() or not root.is_dir()
            or not (root/"app.py").is_file()
            or not (root/"web/montara.js").is_file()
            or (root/"resumable_upload.py").is_symlink()):
        raise ValueError("Incomplete or linked JM bundle")
    actual=hashlib.sha256((root/"resumable_upload.py").read_bytes()).hexdigest()
    if actual != manifest.get("patched_resumable_sha256"):
        raise ValueError("JM private upload overlay changed after review")


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True,type=Path)
    p.add_argument("--editor-commit",required=True)
    p.add_argument("--private-preview-limit-mib",type=int,default=256)
    a=p.parse_args()
    result=build_pinned_chema_manifest(
        a.repo,a.editor_commit,
        private_preview_limit_mib=a.private_preview_limit_mib)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
