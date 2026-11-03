#!/usr/bin/env python3
"""EX-14H-11: install isolated per-project Stage 360 EX07/EX13 adapter.

Never touches Montara's pinned engine or services. Exact-one-match guard.
"""
from pathlib import Path
import subprocess

ROOT = Path("/home/fer/zucker-videos-ex14h09")
EXPECTED = "25f66a9"
if subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip() != EXPECTED:
    raise SystemExit("STOP: unexpected engine commit")
if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip():
    raise SystemExit("STOP: engine worktree not clean")
target = ROOT / "core/stages/export.py"
tests = ROOT / "tests/test_ex14h11_stage_flags.py"
if tests.exists():
    raise SystemExit("STOP: test file already exists")
before = target.read_text()
anchor = 'def _spherical_uses_original_motion('
helper = '''def _spherical_optional_map_flags(project: Project) -> dict[str, bool]:
    """Per-project, strictly opt-in EX07/EX13 for native 360 motion only.

    No process-global override; each concurrent project carries its own flags.
    """
    settings = (project.data.get("settings") or {}).get("export") or {}
    return {
        "fast_wrap": settings.get("ex14h11_fast_wrap") is True,
        "smart_unwrap": settings.get("ex14h11_smart_unwrap") is True,
    }


'''
if before.count(anchor) != 1:
    raise SystemExit(f"STOP: expected exactly one anchor ({before.count(anchor)})")
after = before.replace(anchor, helper + anchor, 1)
old = '''**({"remap_backend": "metal"} if not force_cpu and project.data.get("settings", {}).get("export", {}).get("spherical_remap_backend", "metal" if sys.platform == "darwin" else "cpu") == "metal" else {}))'''
new = '''**({"remap_backend": "metal"} if not force_cpu and project.data.get("settings", {}).get("export", {}).get("spherical_remap_backend", "metal" if sys.platform == "darwin" else "cpu") == "metal" else {}),
                **_spherical_optional_map_flags(project))'''
if after.count(old) != 1:
    raise SystemExit(f"STOP: renderer call pattern changed ({after.count(old)})")
after = after.replace(old, new, 1)
compile(after, str(target), "exec")
test_content = '''"""EX14H11 - Stage per-project flags are opt-in and project-local."""
from types import SimpleNamespace

from core.stages.export import _spherical_optional_map_flags


def project(settings):
    return SimpleNamespace(data={"settings": {"export": settings}})


def test_absent_settings_preserve_defaults():
    assert _spherical_optional_map_flags(SimpleNamespace(data={})) == {
        "fast_wrap": False, "smart_unwrap": False,
    }


def test_independent_project_flags():
    a = project({})
    b = project({"ex14h11_fast_wrap": True, "ex14h11_smart_unwrap": True})
    c = project({"ex14h11_fast_wrap": True})
    assert _spherical_optional_map_flags(a) == {
        "fast_wrap": False, "smart_unwrap": False,
    }
    assert _spherical_optional_map_flags(b) == {
        "fast_wrap": True, "smart_unwrap": True,
    }
    assert _spherical_optional_map_flags(c) == {
        "fast_wrap": True, "smart_unwrap": False,
    }
    assert _spherical_optional_map_flags(a)["fast_wrap"] is False


def test_strings_do_not_enable_experimental_features():
    assert _spherical_optional_map_flags(
        project({"ex14h11_fast_wrap": "true", "ex14h11_smart_unwrap": 1})
    ) == {"fast_wrap": False, "smart_unwrap": False}
'''
compile(test_content, str(tests), "exec")
target.write_text(after)
tests.write_text(test_content)
print("EX14H_11_ADAPTER_INSTALLED")
print("EX14H_11_SCOPE: core/stages/export.py and tests/test_ex14h11_stage_flags.py")
print("EX14H_11_DEFAULTS_FALSE_PER_PROJECT")
