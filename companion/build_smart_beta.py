"""Reproducible pinned Windows Companion + native Stage renderer ZIP.

Bundled sources are pinned Chema 14cce126 and Engine b867b3c; Python
dependencies are installed separately and only on the Windows test PC.
Original Windows installations, personal projects and secrets stay outside.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

from windows_video_jobs_compat import patched_windows_video_jobs

EDITOR_SHA = "14cce126137a0ef30a987351ff35b750f54473bd"
ENGINE_SHA = "b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b"
MIXER_SHA = "f15ff91c1b80fc5f157099dcd9451d958d553ae6"
SOURCE_FILES = (
    "companion/companion.py",
    "companion/video_jobs.py",
    "companion/video_recipe.py",
    "companion/local_video.py",
    "companion/local_mix.py",
    "companion/windows_support.py",
    "companion/spherical_proxy.py",
)
SMART_FILES = (
    "smart_beta_launcher.py",
    "windows_tray_smart.ps1",
    "INSTALAR-RENDER-SMART.ps1",
)
START = """@echo off
cd /d "%~dp0"
echo Montara SMART Beta - icono en la bandeja de Windows
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0windows_tray_smart.ps1"
"""
INSTALL = """@echo off
cd /d "%~dp0"
echo Montara SMART Beta - Preparar motor local de video
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR-RENDER-SMART.ps1"
if errorlevel 1 (
    echo No se ha terminado la instalacion. Revisar error anterior.
    pause
    exit /b 1
)
echo.
pause
"""
README = """MONTARA SMART BETA · Windows / Stage local
============================================
Este paquete utiliza el Companion de Chema (0.6.10) y el Engine b867b3c.

No modifica:
  C:\\Users\\lakme\\AppData\\Local\\Montara-Companion
  C:\\Users\\lakme\\AppData\\Local\\Montara-Companion-Lab
  C:\\Users\\lakme\\AppData\\Local\\Montara-W3L-Build

Datos exclusivos de esta beta:
  %LOCALAPPDATA%\\MontaraSMARTBeta
El directorio del proyecto y los originales se eligen en Montara.

ANTES DE EMPEZAR:
  - Cierra Companion antiguo y deja finalizar renders, si los hubiera.
  - Python 3.11 instalado y reconocido por 'py -3.11'.
  - FFmpeg y ffprobe en PATH.
  - Acceso a Internet para instalar dependencias Python.

PASOS:
  1. Extrae todo el ZIP en una carpeta nueva; NO mezcles con instalaciones antiguas.
  2. Ejecuta una vez INSTALAR-RENDER-SMART.cmd.
     Instala las librerias Python y verifica el Engine completo.
  3. Ejecuta INICIAR-SMART-BETA.cmd.
     Debe aparecer el icono en la bandeja de Windows; no hace falta consola.
  4. Abre el menu del icono y pulsa Abrir Montara SMART Beta.
     Comprueba los proyectos y el render local; originales sin subir.

Al salir, el icono bloquea el cierre si hay un trabajo activo.
La preparacion del Engine se niega si hay un Companion abierto.
No instala autoarranque, no toca registro, ni migra archivos antiguos.
Se puede borrar la carpeta extraida cuando la beta no este en uso.

Editor 14cce126137a0ef30a987351ff35b750f54473bd
Engine b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b
Mixer  f15ff91c1b80fc5f157099dcd9451d958d553ae6
"""
def git_bytes(repo: Path, sha: str, path: str) -> bytes:
    response = subprocess.run(
        ["git","-C",str(repo),"show",f"{sha}:{path}"],
        capture_output=True,timeout=30
    )
    if response.returncode:
        raise RuntimeError(f"Missing pinned Chema source {path}")
    return response.stdout


def engine_files(engine_repo: Path) -> dict[str, bytes]:
    revision = subprocess.check_output(
        ["git","-C",str(engine_repo),"rev-parse","HEAD"],
        timeout=15,text=True
    ).strip()
    if revision != ENGINE_SHA:
        raise ValueError("Engine checkout does not match pinned Chema gitlink")
    archived = subprocess.run(
        ["git","-C",str(engine_repo),"archive",ENGINE_SHA,"core"],
        capture_output=True,timeout=60,check=True
    ).stdout
    result={}
    with tarfile.open(fileobj=io.BytesIO(archived)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            path=member.name
            if (not path.startswith("core/") or "/../" in path
                    or path.startswith("/") or "\\" in path
                    or member.size>10_000_000):
                raise ValueError("Unexpected Engine archive path")
            content=tar.extractfile(member).read()
            result["renderer/engine/"+path]=content
    if "renderer/engine/core/stages/export.py" not in result:
        raise ValueError("Pinned native export Stage is missing")
    return result


def build(repo: Path, engine_repo: Path, out: Path, source_sha: str) -> dict:
    if source_sha != EDITOR_SHA:
        raise ValueError("Only the reviewed Chema editor commit is supported")
    path_root=Path(__file__).resolve().parent
    output={}
    for path in SOURCE_FILES:
        output[path.removeprefix("companion/")]=git_bytes(repo,source_sha,path)
    original=output["video_jobs.py"].decode("utf-8")
    output["video_jobs.py"]=patched_windows_video_jobs(original).encode("utf-8")
    for path in SMART_FILES:
        output[path]=(path_root/path).read_bytes()

    spatialmedia=subprocess.check_output(
        ["git","-C",str(repo),"ls-tree","-r","--name-only",
         source_sha,"companion/spatialmedia"],text=True,timeout=30
    ).splitlines()
    for path in spatialmedia:
        if path.endswith(".py"):
            output[path.removeprefix("companion/")]=git_bytes(repo,source_sha,path)

    output["renderer/local_video.py"]=git_bytes(
        repo,source_sha,"companion/local_video.py")
    output["renderer/video_recipe.py"]=git_bytes(
        repo,source_sha,"companion/video_recipe.py")
    for name in ("montara-logo.png","montara-watermark.png"):
        output["renderer/brand/"+name]=git_bytes(
            repo,source_sha,"web/brand/"+name)
    output["renderer/ENGINE_COMMIT"]=(ENGINE_SHA+"\n").encode("ascii")
    output.update(engine_files(engine_repo))

    output["INICIAR-SMART-BETA.cmd"]=START.encode("utf-8")
    output["INSTALAR-RENDER-SMART.cmd"]=INSTALL.encode("utf-8")
    output["LEEME-SMART-BETA.txt"]=README.encode("utf-8")
    manifest={
        "schema":2,"editor":EDITOR_SHA,"engine":ENGINE_SHA,
        "mixer":MIXER_SHA,
        "renderer_sources_bundled":True,
        "dependencies_preinstalled":False,
        "files":{name:hashlib.sha256(data).hexdigest()
                 for name,data in sorted(output.items())},
    }
    output["smart-beta-manifest.json"]=(
        json.dumps(manifest,sort_keys=True,indent=2)+"\n"
    ).encode("utf-8")
    for path,data in output.items():
        if path.endswith(".py"):
            compile(data.decode("utf-8"),path,"exec")
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,data in sorted(output.items()):
            z.writestr("Montara-SMART-Beta/"+path,data)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
    return {
        "path":str(out),"files":len(output),
        "bytes":out.stat().st_size,
        "sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
        "editor":EDITOR_SHA,"engine":ENGINE_SHA,
        "renderer_sources_bundled":True,
    }


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--repo",type=Path,default=Path.cwd())
    cli.add_argument("--engine-repo",type=Path,required=True)
    cli.add_argument("--source-sha",default=EDITOR_SHA)
    cli.add_argument("--out",type=Path,required=True)
    args=cli.parse_args()
    print(json.dumps(build(args.repo,args.engine_repo,args.out,args.source_sha),
                     sort_keys=True))


if __name__=="__main__":
    main()
