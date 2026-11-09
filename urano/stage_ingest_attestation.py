"""Trusted ingest-side join between real Stage proxies and Companion receipts.

The receipt is produced by a trusted Companion proxy-transfer pipeline, not a
browser request. Without an exact SHA-256 proxy receipt, never certify the
original for a Stage slot. This module does not open an HTTP registration route.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources, _canonical_sources


def attest_stage_ingest(
    provenance: StageSourceProvenance, owner_id: str, project_id: str,
    *, engine_project_file: Path, receipts: list[dict],
) -> str:
    """Register only if completed Engine ingest and every proxy matches its receipt.

    Each receipt has {source_slot, original, proxy_sha256}. The original
    identity must have been paired with the proxy during trusted preprocessing.
    Verifies the Stage input bytes against the trusted receipt AND verifies
    that normalized output exists; the latter may be transcoded. It does not
    authenticate an arbitrary browser assertion or establish trusted transport.
    """
    provenance.catalog.get(owner_id, project_id)
    file = Path(engine_project_file)
    if file.name != "project.json" or file.is_symlink() or not file.is_file():
        raise UnverifiedSources("Trusted Engine project snapshot required")
    try:
        project = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise UnverifiedSources("Invalid Engine project snapshot") from exc
    stage = (project.get("stages") or {}).get("ingest") or {}
    if not isinstance(stage, dict) or stage.get("status") != "done":
        raise UnverifiedSources("Stage Ingest must complete before source attestation")
    videos = (project.get("inputs") or {}).get("videos")
    if (not isinstance(videos, list) or not 1 <= len(videos) <= 16
            or not isinstance(receipts, list) or len(receipts) != len(videos)):
        raise UnverifiedSources("Every Stage proxy needs a trusted receipt")

    identity = _canonical_sources([
        {"source_slot": item.get("source_slot"), "original": item.get("original")}
        for item in receipts if isinstance(item, dict)
    ])
    if len(identity) != len(videos):
        raise UnverifiedSources("Incomplete trusted receipts")
    by_slot = {item["source_slot"]: item for item in receipts}
    proof = []
    for slot, video in enumerate(videos):
        if not isinstance(video, dict) or video.get("status") == "not_a_video":
            raise UnverifiedSources("Unsupported Stage input")
        receipt = by_slot.get(slot)
        expected = receipt.get("proxy_sha256") if isinstance(receipt, dict) else None
        if (not isinstance(expected, str) or len(expected) != 64
                or any(ch not in "0123456789abcdef" for ch in expected)):
            raise UnverifiedSources("Proxy digest required")
        # The source byte stream is what the Companion receipt describes.
        # Engine may normalize/transcode that source into *different* bytes,
        # so verify the source SHA-256, then independently require a completed
        # normalized output with an authenticated Engine project snapshot.
        source_path = video.get("path")
        normalized = video.get("normalized")
        if (not isinstance(source_path, str) or not isinstance(normalized, dict)
                or not isinstance(normalized.get("path"), str)):
            raise UnverifiedSources("Stage source or normalized output unavailable")
        source = Path(source_path)
        output = Path(normalized["path"])
        # The Engine input must live inside this owner's project workspace,
        # not another user's folder or an arbitrary host path. The normalized
        # cache may reside elsewhere under the Engine's own isolation.
        if (not source.is_absolute() or not source.resolve().is_relative_to(file.parent.resolve())
                or not file.parent.is_dir() or file.parent.is_symlink()):
            raise UnverifiedSources("Stage source is outside its private project")
        if any(not item.is_absolute() or item.is_symlink() or not item.is_file()
               for item in (source, output)):
            raise UnverifiedSources("Trusted Stage files missing or linked")
        hashes = []
        for item in (source, output):
            digest = hashlib.sha256()
            try:
                with item.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError as exc:
                raise UnverifiedSources("Cannot verify Stage media bytes") from exc
            hashes.append(digest.hexdigest())
        if hashes[0] != expected:
            raise UnverifiedSources("Stage source bytes do not match Companion receipt")
        proof.append({"slot": slot, "proxy_sha256": expected,
                      "normalized_sha256": hashes[1]})
    stage_revision = hashlib.sha256(json.dumps(
        proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    provenance.register_trusted(
        owner_id, project_id, identity, stage_revision=stage_revision)
    return stage_revision


def attest_authenticated_inbox(
    provenance: StageSourceProvenance,
    bindings: "EngineProjectRegistry", inbox_root: Path,
    owner_id: str, project_id: str, *,
    engine_project_file: Path,
) -> str:
    """Operator-only final attestation after real Stage Ingest has reached DONE.

    A true receipt_authenticated flag can ONLY be written by the private inbox
    after verifying the Companion's operator-provisioned HMAC. This function
    does not expose an HTTP endpoint and never trusts the original_claim alone.
    Both the Engine snapshot and each input must belong to the owner's binding.
    """
    from urano.engine_bindings import EngineProjectRegistry
    if not isinstance(bindings, EngineProjectRegistry):
        raise UnverifiedSources("Trusted Engine binding required")
    root = bindings.resolve_internal(owner_id, project_id)
    expected_project = root / "project.json"
    if (Path(engine_project_file).resolve() != expected_project.resolve()
            or Path(engine_project_file).is_symlink()):
        raise UnverifiedSources("Stage project is not bound to owner")
    owner_dir = Path(inbox_root) / hashlib.sha256(owner_id.encode()).hexdigest()
    folder = owner_dir / project_id
    if (Path(inbox_root).is_symlink() or owner_dir.is_symlink()
            or folder.is_symlink() or not folder.is_dir()):
        raise UnverifiedSources("Private Companion receipts unavailable")
    try:
        state = json.loads(expected_project.read_text(encoding="utf-8"))
        videos = state["inputs"]["videos"]
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise UnverifiedSources("Engine source catalog unavailable") from exc
    if not isinstance(videos, list) or not 1 <= len(videos) <= 16:
        raise UnverifiedSources("Missing Stage sources")
    receipts = []
    for slot, video in enumerate(videos):
        # The worker registers only this exact source name after integrity
        # checking. Do not infer authenticity from matching camera names.
        if not isinstance(video, dict) or not isinstance(video.get("path"), str):
            raise UnverifiedSources("Stage camera source missing")
        source = Path(video["path"])
        pattern = re.fullmatch(
            r"camera-" + str(slot) + r"-([a-f0-9]{64})\.mp4",
            source.name)
        if not pattern:
            raise UnverifiedSources("Stage source is not a trusted proxy")
        digest = pattern.group(1)
        expected_input = root / "inputs" / "urano-staged-proxies" / source.name
        if source != expected_input or source.is_symlink():
            raise UnverifiedSources("Engine source outside certified workspace")
        manifest = folder / f"slot-{slot}-{digest}.json"
        staged = folder / f"slot-{slot}-{digest}.mp4"
        if any(p.is_symlink() or not p.is_file() for p in (manifest, staged)):
            raise UnverifiedSources("Authenticated receipt files missing")
        if manifest.stat().st_size > 4096:
            raise UnverifiedSources("Unexpected receipt size")
        try:
            entry = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UnverifiedSources("Invalid receipt record") from exc
        if (not isinstance(entry, dict) or
                set(entry) != {"source_slot", "proxy_sha256", "original_claim",
                               "attested", "bytes", "receipt_authenticated"} or
                type(entry["source_slot"]) is not int or entry["source_slot"] != slot or
                entry["proxy_sha256"] != digest or
                entry["attested"] is not False or
                entry["receipt_authenticated"] is not True or
                type(entry["bytes"]) is not int or
                entry["bytes"] <= 0 or staged.stat().st_size != entry["bytes"]):
            raise UnverifiedSources("Unauthenticated or inconsistent Companion receipt")
        check = hashlib.sha256()
        with staged.open("rb") as reader:
            for block in iter(lambda: reader.read(1024 * 1024), b""):
                check.update(block)
        if check.hexdigest() != digest:
            raise UnverifiedSources("Companion staged proxy was altered")
        receipts.append({"source_slot": slot, "proxy_sha256": digest,
                         "original": entry["original_claim"]})
    return attest_stage_ingest(provenance, owner_id, project_id,
                               engine_project_file=expected_project, receipts=receipts)
