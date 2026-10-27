"""Bridge between a Montara editing session and persistent proxy preparation.

Input is a private local manifest listing videos. The returned manifest includes
only public proxy metadata and IDs; original paths remain in private cache files.
This prepares sources for a future preview integration, not a browser API.
"""
from __future__ import annotations

import json
from pathlib import Path

from local_media.proxies import prepare


def prepare_session(sources, cache_dir, *, sphere=False):
    if not isinstance(sources, (list, tuple)) or not 1 <= len(sources) <= 64:
        raise ValueError("A session must contain between 1 and 64 videos")
    prepared = []
    seen = set()
    for item in sources:
        source = Path(item).resolve()
        if source in seen:
            raise ValueError("Duplicate video source")
        seen.add(source)
        record = prepare(source, cache_dir, sphere=sphere)
        prepared.append(record["public"])
    return {"version": 1, "sources": prepared}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("sources_json", type=Path,
                        help="Private JSON array of local source paths")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="Public metadata JSON (no original file paths)")
    args = parser.parse_args()
    result = prepare_session(json.loads(args.sources_json.read_text()), args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"prepared": len(result["sources"]), "manifest": str(args.output)}))


if __name__ == "__main__":
    main()
