#!/usr/bin/env python3
"""Guarded EX14H11 per-project native-call audit (isolated test branch only)."""
from pathlib import Path
import subprocess

repo = Path("/home/fer/zucker-videos-ex14h09")
run = lambda *args: subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
if run("rev-parse", "--short", "HEAD") != "2e76003" or run("status", "--porcelain"):
    raise SystemExit("STOP: expected clean worktree at 2e76003")
file = repo / "core/stages/export.py"
s = file.read_text()
anchor = '''            run_reprojected_command(command, str(source["source_path"]),'''
injection = '''            # EX14H11 audit: project-local; no global hooks or runtime overrides.
            project.data.setdefault("_ex14h11_native_calls", []).append({
                "flags": _spherical_optional_map_flags(project),
                "source_original": str(source["source_path"]) == str(base_source["source_path"]),
                "frame_count": frame_count,
            })
'''
if s.count(anchor) != 1 or "def _spherical_optional_map_flags(" not in s:
    raise SystemExit("STOP: unexpected Stage source, no modifications made")
s = s.replace(anchor, injection + anchor, 1)
compile(s, str(file), "exec")
file.write_text(s)
print("EX14H_11_NATIVE_CALL_AUDIT_INSTALLED")
