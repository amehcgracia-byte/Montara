"""Trusted operator-side promotion of unverified private inbox proxies.

Copies verified staged bytes into a pre-bound Engine project workspace. This
does NOT attest Companion original provenance. Engine must then register these
inputs through a fixed worker operation before Ingest can run.
No HTTP route and no arbitrary path or filename originates from a browser.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.stage_source_provenance import UnverifiedSources, _canonical_sources

_SHA = re.compile(r"^[0-9a-f]{64}$")
_SLOT = re.compile(r"^slot-([0-9]|1[0-5])-([0-9a-f]{64})\.json$")
_LIMIT = 128 * 1024 * 1024


def prepare_trusted_stage_inputs(
    bindings: EngineProjectRegistry, inbox_root: Path,
    owner_id: str, project_id: str, *, source_slots: set[int],
) -> list[Path]:
    """Verify an owner's inbox, then install deterministic, path-free input files.

    The original claims remain *untrusted*. This is strictly proxy integrity
    and private project input provisioning, not a provenance certificate.
    """
    if (not isinstance(source_slots, set) or not source_slots
            or len(source_slots) > 16
            or any(type(s) is not int or not 0 <= s <= 15 for s in source_slots)):
        raise UnverifiedSources("Invalid Stage input slots")
    project_dir = bindings.resolve_internal(owner_id, project_id)
    root = Path(inbox_root)
    owner_dir = root / hashlib.sha256(owner_id.encode()).hexdigest()
    inbox = owner_dir / project_id
    if (root.is_symlink() or owner_dir.is_symlink() or inbox.is_symlink()
            or not inbox.is_dir() or not inbox.resolve().is_relative_to(root.resolve())):
        raise UnverifiedSources("Private inbox unavailable")
    prepared = []
    for slot in sorted(source_slots):
        candidates = [f for f in inbox.iterdir() if _SLOT.fullmatch(f.name)
                      and int(_SLOT.fullmatch(f.name).group(1)) == slot]
        # Multiple uploads for a slot are ambiguous until operator resolves them.
        if len(candidates) != 1:
            raise UnverifiedSources("Missing or ambiguous Stage proxy")
        metadata = candidates[0]
        if metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size > 4096:
            raise UnverifiedSources("Invalid private proxy metadata")
        try:
            item = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UnverifiedSources("Invalid Stage proxy metadata") from exc
        digest = _SLOT.fullmatch(metadata.name).group(2)
        if (not isinstance(item, dict) or set(item) !=
                {"source_slot", "proxy_sha256", "original_claim", "attested", "bytes"}
                or item["source_slot"] != slot or type(item["source_slot"]) is not int
                or item["proxy_sha256"] != digest or item["attested"] is not False
                or type(item["bytes"]) is not int or not 0 < item["bytes"] <= _LIMIT):
            raise UnverifiedSources("Invalid proxy manifest")
        _canonical_sources([{"source_slot": slot, "original": item["original_claim"]}])
        proxy = inbox / f"slot-{slot}-{digest}.mp4"
        if proxy.is_symlink() or not proxy.is_file() or proxy.stat().st_size != item["bytes"]:
            raise UnverifiedSources("Stage proxy missing or modified")
        # Read a trusted host path in streaming mode. SHA-256 must match exact
        # bytes, not a caller-supplied filename or browser claim.
        actual = hashlib.sha256()
        with proxy.open("rb") as reader:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                actual.update(chunk)
        if actual.hexdigest() != digest:
            raise UnverifiedSources("Staged proxy digest mismatch")
        prepared.append((slot, proxy, digest))

    input_dir = project_dir / "inputs" / "urano-staged-proxies"
    if (project_dir.is_symlink() or input_dir.is_symlink()
            or input_dir.parent.is_symlink()):
        raise UnverifiedSources("Unsafe Engine input workspace")
    input_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = []
    for slot, source, digest in prepared:
        target = input_dir / f"camera-{slot}-{digest}.mp4"
        if target.is_symlink():
            raise UnverifiedSources("Stage target linked")
        staged = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=input_dir, prefix=".incoming-", delete=False
            ) as output, source.open("rb") as reader:
                staged = Path(output.name)
                os.chmod(staged, 0o600)
                check = hashlib.sha256()
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    output.write(chunk)
                    check.update(chunk)
            if check.hexdigest() != digest:
                raise UnverifiedSources("Staged proxy changed during copy")
            os.replace(staged, target)
            staged = None
            result.append(target)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
    return result
