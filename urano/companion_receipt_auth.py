"""Operator-only verification of a Companion's scoped signed proxy receipt.

HMAC secrets are 32 bytes, provisioned by a trusted operator for a specific
owner and local Companion. NEVER accept public enrollment, HTTP key material or
a secret from a browser-supplied header. No silent trust-on-first-use.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path

from urano.stage_source_provenance import UnverifiedSources, _canonical_sources

_HASH = re.compile(r"^[a-f0-9]{64}$")
_PROJECT = re.compile(r"^[0-9a-f-]{36}$")
_SCHEMA = "montara-companion-proxy-receipt-v1"


class CompanionReceiptVerifier:
    def __init__(self, owner_keys: dict[str, Path]):
        # Explicit trusted configuration; only file paths supplied by the
        # operator, and no interactive enrollment or write API.
        self._keys = dict(owner_keys)

    def verify(self, owner_id: str, project_id: str, source_slot: int,
               proxy_sha256: str, original: dict, envelope: object) -> dict:
        if (owner_id not in self._keys or not isinstance(envelope, dict)
                or set(envelope) != {"receipt", "signature"}):
            raise UnverifiedSources("No trusted Companion receipt")
        payload, signature = envelope["receipt"], envelope["signature"]
        if (not isinstance(payload, dict) or
                set(payload) != {"schema", "project_id", "source_slot", "original", "proxy_sha256"}
                or payload["schema"] != _SCHEMA
                or not _PROJECT.fullmatch(project_id)
                or payload["project_id"] != project_id
                or type(payload["source_slot"]) is not int
                or payload["source_slot"] != source_slot
                or not isinstance(proxy_sha256, str) or not _HASH.fullmatch(proxy_sha256)
                or payload["proxy_sha256"] != proxy_sha256
                or payload["original"] != original
                or not isinstance(signature, str) or not _HASH.fullmatch(signature)):
            raise UnverifiedSources("Companion receipt scope mismatch")
        _canonical_sources([{"source_slot": source_slot, "original": original}])
        path = Path(self._keys[owner_id])
        if path.is_symlink() or not path.is_file():
            raise UnverifiedSources("Trusted receipt key not found")
        if path.stat().st_mode & 0o077:
            raise UnverifiedSources("Trusted receipt key permissions unsafe")
        secret = path.read_bytes()
        if len(secret) != 32:
            raise UnverifiedSources("Invalid trusted receipt key")
        message = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode()
        correct = hmac.new(secret, message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(correct, signature):
            raise UnverifiedSources("Companion receipt signature invalid")
        return {"source_slot": source_slot, "original": dict(original),
                "proxy_sha256": proxy_sha256, "receipt_authenticated": True}
