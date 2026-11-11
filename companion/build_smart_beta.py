"""Reproducible, minimal Windows SMART Beta package from Chema's pinned source.

No source tree rewrite; only the reviewed Windows video_jobs compatibility
patch is applied inside the distribution ZIP. Never package secrets, user
state, source media, binaries from /opt, or an Engine mismatch.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

from windows_video_jobs_compat import patched_windows_video_jobs

EDITOR_SHA = "14cce126137a0ef30a987351ff35b750f54473bd"
ENGINE_SHA = "b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b"
MIXER_SHA = "f15ff91c1b80fc5f157099dcd9451d958d553ae6"
FILES = (
    "companion/companion.py",
    "companion/video_jobs.py",
    "companion/video_recipe.py",
    "companion/local_video.py",
    "companion/local_mix.py",
    "companion/windows_support.py",
    "companion/spherical_proxy.py",
)
START = r"""@echo off
setlocal
cd /d "%~dp0"
echo Montara SMART Beta - Companion privado Windows
echo Los Companion anteriores no se modificaran.
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo No se encuentra Python. Comprueba su instalacion.
  pause
  exit /b 2
)
python smart_beta_launcher.py
echo.
echo Montara SMART Beta se ha detenido. No se ha actualizado ninguna instalacion previa.
pause
"""
README = """MONTARA SMART BETA · Companion Windows
=======================================

Edicion aislada de validacion privada (no sustituye el Companion de Chema).

1. Extrae este ZIP a una carpeta normal, por ejemplo tu Escritorio.
2. No extraigas dentro de un Companion anterior.
3. Haz doble clic en INICIAR-SMART-BETA.cmd.
4. Debes tener Python (3.11 o posterior) y ffmpeg/ffprobe en PATH.
5. Manten la ventana abierta mientras usas Montara. Ctrl+C la detiene.
6. Comprueba http://127.0.0.1:47820/health y el acceso desde nuestra beta.

Esta primera distribucion es de CONEXION/PROXIES, NO es todavia el instalador
del motor de render de originales. El exportador local requiere una instalacion
aparte del Engine b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b y dependencias.
NO declares que el MP4 final esta listo si /health no anuncia local_video.engine
con ese mismo hash. Prepararemos ese paso antes del ensayo integrado.

Los originales de video permanecen en tu equipo. El Companion escucha
exclusivamente en 127.0.0.1:47820 y solo acepta el origen HTTPS privado de
Montara. Los datos del piloto se guardan aparte en
%LOCALAPPDATA%\\MontaraSMARTBeta, nunca en ~/.montara-companion.
No usar mientras otro Companion ocupe el puerto 47820.

Editor: 14cce126137a0ef30a987351ff35b750f54473bd
Engine: b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b
Mixer:  f15ff91c1b80fc5f157099dcd9451d958d553ae6
"""


def git_bytes(repo: Path, ref: str, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True, timeout=30
    )
    if proc.returncode:
        raise RuntimeError(f"Missing pinned JM source: {path}")
    return proc.stdout


def build(repo: Path, out: Path, source_sha: str) -> dict:
    if source_sha != EDITOR_SHA:
        raise ValueError("Only the reviewed Chema editor revision is authorized")
    # Fetch Chema's original files from the Git repository, but use the
    # checked-out build script's own versioned SMART launcher.
    launcher = Path(__file__).resolve().parent / "smart_beta_launcher.py"
    if not launcher.is_file():
        raise ValueError("SMART launcher missing beside build script")
    output = {}
    for path in FILES:
        output[path.removeprefix("companion/")] = git_bytes(repo, source_sha, path)
    output["video_jobs.py"] = patched_windows_video_jobs(
        output["video_jobs.py"].decode("utf-8")
    ).encode("utf-8")
    output["smart_beta_launcher.py"] = (
        launcher
    ).read_bytes()

    # Only actual spatialmedia Python sources, not .git files, tests or data.
    tree = subprocess.check_output(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only",
         source_sha, "companion/spatialmedia"],
        timeout=30, text=True
    ).splitlines()
    for path in tree:
        if not path.startswith("companion/spatialmedia/"):
            raise ValueError("Unexpected original spatialmedia tree")
        if path.endswith(".py"):
            output[path.removeprefix("companion/")] = git_bytes(repo,source_sha,path)

    output["INICIAR-SMART-BETA.cmd"] = START.encode("utf-8")
    output["LEEME-SMART-BETA.txt"] = README.encode("utf-8")
    manifest = {
        "schema": 1, "editor": EDITOR_SHA, "engine": ENGINE_SHA,
        "mixer": MIXER_SHA, "render_engine_bundled": False,
        "files": {
            path: hashlib.sha256(data).hexdigest()
            for path,data in sorted(output.items())
        }
    }
    output["smart-beta-manifest.json"] = (
        json.dumps(manifest,sort_keys=True,indent=2)+"\n"
    ).encode()
    for path,data in output.items():
        if path.endswith(".py"):
            compile(data.decode("utf-8"),path,"exec")
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path,data in sorted(output.items()):
            archive.writestr("Montara-SMART-Beta/"+path,data)
    with zipfile.ZipFile(out) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Corrupt Beta package")
    return {"path":str(out),"files":len(output),"bytes":out.stat().st_size,
            "source":EDITOR_SHA,"renderer_included":False}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,default=Path.cwd())
    parser.add_argument("--source-sha",default=EDITOR_SHA)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.repo,args.out,args.source_sha),sort_keys=True))


if __name__=="__main__":
    main()
