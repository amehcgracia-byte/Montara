"""Check integrity of a SATURNO-02/03 research ZIP against its own SHA manifest.

Usage: python experiments/saturno_03/verify_archive.py path/to/SATURNO.zip
The external expected archive digest must be checked independently; the internal
manifest alone cannot attest authenticity. Never execute archived code automatically.
"""
import argparse,hashlib,json,sys,zipfile
from pathlib import PurePosixPath,Path

def verify(path,expected_sha=None):
    path=Path(path)
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha and actual!=expected_sha:
        raise ValueError("archive SHA-256 mismatch")
    with zipfile.ZipFile(path) as z:
        entries=z.namelist()
        if len(entries)!=len(set(entries)):raise ValueError("duplicate zip entries")
        if "MANIFEST.json" not in entries:raise ValueError("missing manifest")
        doc=json.loads(z.read("MANIFEST.json"))
        expected=doc.get("sha256",{})
        if not isinstance(expected,dict) or not expected:raise ValueError("empty checksum map")
        if set(entries)!=(set(expected)|{"MANIFEST.json"}):
            raise ValueError("missing or unexpected archive entries")
        for name,digest in expected.items():
            p=PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or len(digest)!=64:
                raise ValueError("unsafe entry or digest")
            computed=hashlib.sha256(z.read(name)).hexdigest()
            if computed!=digest:raise ValueError(f"hash mismatch: {name}")
    return {"archive_sha256":actual,"files_verified":len(expected),"status":"PASS"}

def main():
    p=argparse.ArgumentParser();p.add_argument("archive");p.add_argument("--sha256")
    a=p.parse_args()
    print(json.dumps(verify(a.archive,a.sha256),indent=2))
if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}",file=sys.stderr);sys.exit(1)
