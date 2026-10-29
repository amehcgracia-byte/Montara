"""SATURNO-17: scoped QA-only decoder argv override; never edits Zucker files.

Use within a single worker process around a real 360 render call.
The guard rejects unexpected decoder arguments and records each intervention.
"""
from contextlib import contextmanager
import subprocess

@contextmanager
def cpu_decoder_passthrough_guard():
    original_popen = subprocess.Popen
    evidence = {"interventions": [], "other_processes": 0}

    def guarded_popen(args, *pos, **kw):
        if isinstance(args, (list, tuple)) and len(args) >= 10:
            argv = list(args)
            is_decoder = (
                "-vf" in argv and
                "-frames:v" in argv and
                len(argv) >= 3 and
                argv[-3:] == ["-f", "rawvideo", "pipe:1"] and
                any(str(x).startswith("fps=") and "format=bgr24" in str(x) for x in argv)
            )
            if is_decoder:
                if "-fps_mode" in argv:
                    raise AssertionError("Decoder already specifies fps_mode; inspect engine version")
                modified = argv[:-3] + ["-fps_mode", "passthrough"] + argv[-3:]
                assert modified[:len(argv)-3] == argv[:-3]
                assert modified[-3:] == argv[-3:]
                evidence["interventions"].append({"original": argv, "effective": modified})
                return original_popen(modified, *pos, **kw)
        evidence["other_processes"] += 1
        return original_popen(args, *pos, **kw)

    subprocess.Popen = guarded_popen
    try:
        yield evidence
    finally:
        subprocess.Popen = original_popen
