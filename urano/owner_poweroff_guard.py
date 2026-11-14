"""Read-only Owner ledger preflight for VM shutdown integration (I6b).

This is NOT an idle watchdog or a poweroff command. Any unverified Owner
reservation conservatively blocks shutdown until the broker verifies cleanup.
The caller must additionally prevent new Owner admissions during the final
poweroff transaction; a snapshot alone has a TOCTOU window.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


class OwnerPoweroffUnknown(RuntimeError):
    """Untrusted, missing, or unreadable ledger: keep VM running."""


def may_poweroff(*, ledger_paths: tuple[Path, ...]) -> bool:
    """Return True only if each operator-pinned ledger has zero open leases.

    Never accepts a path from a browser. Read-only SQLite (no migrations or
    directory creation), and do not trust a missing database as evidence.
    """
    if not ledger_paths:
        raise OwnerPoweroffUnknown("No operator-pinned Owner ledgers configured")
    if any(not isinstance(p, Path) or not p.is_absolute() for p in ledger_paths):
        raise OwnerPoweroffUnknown("Only absolute trusted ledger paths allowed")
    for path in ledger_paths:
        if path.is_symlink() or not path.is_file():
            raise OwnerPoweroffUnknown("Owner ledger unavailable")
        try:
            with sqlite3.connect(
                path.as_uri() + "?mode=ro", uri=True, timeout=2,
            ) as db:
                db.execute("PRAGMA query_only=ON")
                row = db.execute(
                    "SELECT COUNT(*) FROM urano_engine_jobs "
                    "WHERE state IN ('starting','running','stopping','orphaned')"
                ).fetchone()
                if row is None or type(row[0]) is not int:
                    raise OwnerPoweroffUnknown("Invalid Owner lease snapshot")
                if row[0] != 0:
                    return False
        except (sqlite3.Error, OSError) as exc:
            raise OwnerPoweroffUnknown("Owner ledger could not be verified") from exc
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="I6b read-only Owner poweroff preflight")
    parser.add_argument("--ledger", action="append", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        safe = may_poweroff(ledger_paths=tuple(args.ledger))
    except OwnerPoweroffUnknown:
        print("OWNER UNKNOWN: keep VM running")
        return 2
    if not safe:
        print("OWNER RESERVED: keep VM running")
        return 1
    print("OWNER LEDGERS EMPTY: candidate only; admission-lock required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
