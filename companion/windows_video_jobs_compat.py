"""Small, opt-in Windows compatibility patch for Chema's original video_jobs.

Apply only when assembling the authorized Companion beta package. The original
JM source and already-installed Companion remain untouched. Fail closed if a
future Chema version changes an expected anchor.
"""
from __future__ import annotations


def patched_windows_video_jobs(source: str) -> str:
    if not isinstance(source, str):
        raise TypeError("Original video_jobs source required")
    anchors = [
        ("import hashlib,json,os,re,signal,subprocess,threading,time,uuid",
         "import hashlib,json,os,re,signal,subprocess,threading,time,uuid"),
        ("    def runtime(self):\n        python=self.home/'venv/bin/python';marker=self.home/'ENGINE_COMMIT'",
         """    def renderer_python(self):
        if os.name == 'nt':
            return self.home/'venv'/'Scripts'/'python.exe'
        return self.home/'venv'/'bin'/'python'

    def runtime(self):
        python=self.renderer_python();marker=self.home/'ENGINE_COMMIT'"""),
        ("process=subprocess.Popen([str(self.home/'venv/bin/python'),str(self.home/'local_video.py'),str(job['work']/'render.json')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)",
         "process=subprocess.Popen([str(self.renderer_python()),str(self.home/'local_video.py'),str(job['work']/'render.json')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)"),
        ("    rows=subprocess.check_output(['ps','-Ao','pid=,ppid='],text=True).splitlines()",
         """    if os.name == 'nt':
        # Windows has no `ps` or POSIX process groups. taskkill /T /F
        # terminates FFmpeg descendants as well as the renderer.
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       check=False,timeout=12)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:pass
        return
    rows=subprocess.check_output(['ps','-Ao','pid=,ppid='],text=True).splitlines()"""),
    ]
    revised=source
    for old,new in anchors[1:]:
        if revised.count(old)!=1:
            raise ValueError("Chema video_jobs compatibility anchor changed")
        revised=revised.replace(old,new)
    if ("venv/bin/python" in revised or
            "def renderer_python" not in revised):
        raise ValueError("Unpatched native renderer interpreter")
    compile(revised,"video_jobs.py","exec")
    return revised
