"""Read-only fixture inventory for local media or GitHub tree snapshot."""
import argparse,json
from pathlib import Path
VIDEO={".mp4",".mov",".mkv",".insv"}
AUDIO={".mp3",".wav",".flac",".m4a"}
def category(p):
    ext=Path(p).suffix.lower()
    return "video" if ext in VIDEO else "audio" if ext in AUDIO else None
def summarize(rows):
    rows=sorted([r for r in rows if category(r["path"])],key=lambda x:x["path"])
    if not rows:raise ValueError("no media entries")
    return {"schema":"saturno-04-fixture-v1","files":rows,
       "total_bytes":sum(r["bytes"] for r in rows),
       "video_bytes":sum(r["bytes"] for r in rows if category(r["path"])=="video"),
       "audio_bytes":sum(r["bytes"] for r in rows if category(r["path"])=="audio"),
       "video_count":sum(category(r["path"])=="video" for r in rows),
       "audio_count":sum(category(r["path"])=="audio" for r in rows),
       "evidence":"File sizes only; no edit-plan, byte-minimal package, or actual render benchmark"}
def github_tree(obj,prefix="tests/fixtures/much-to-me/"):
    return summarize([{"path":e["path"][len(prefix):],"bytes":e["size"],"git_blob_sha":e.get("sha")}
       for e in obj["tree"] if e.get("type")=="blob" and e.get("path","").startswith(prefix) and category(e["path"])])
def local(root):
    root=Path(root).resolve()
    files=[]
    for p in root.rglob("*"):
        if p.is_symlink():raise ValueError("symlinks disallowed in QA inventory")
        if p.is_file() and category(p.name):
            files.append({"path":str(p.relative_to(root)),"bytes":p.stat().st_size})
    return summarize(files)
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--github-tree",type=Path)
    group.add_argument("--local",type=Path)
    args=parser.parse_args()
    result=github_tree(json.loads(args.github_tree.read_text())) if args.github_tree else local(args.local)
    print(json.dumps(result,indent=2))
