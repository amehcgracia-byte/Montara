#!/usr/bin/env python3
"""F4: benchmark aislado de interpolación v360. No modifica ZuckerVideos.

Ejemplo:
 python3 experiments/media_optimization/f4_v360_benchmark.py \
   --source tests/fixtures/real/cam-360.mp4 --seconds 2 --repeats 2 \
   --width 640 --height 360 --output /tmp/montara-f4-smoke

Los resultados son comparaciones de salidas codificadas, NO calidad de verdad-terreno.
"""
import argparse
import csv
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def command_output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def probe(path):
    return json.loads(command_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames,duration:"
                         "format=duration", "-of", "json", str(path)
    ]))


def run(args):
    started = time.perf_counter()
    result = subprocess.run(args, text=True, capture_output=True)
    duration = time.perf_counter() - started
    if result.returncode:
        raise RuntimeError(
            f"Comando fallido ({result.returncode}): {' '.join(map(str, args))}\n"
            + result.stderr[-3000:]
        )
    return duration, result.stderr


def encode(source, output, mode, seconds, width, height, threads):
    vf = (
        f"v360=input=equirect:output=flat:yaw=35:pitch=12:"
        f"h_fov=100:v_fov=62:w={width}:h={height}:interp={mode},"
        "format=yuv420p"
    )
    return run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-threads", str(threads), "-i", str(source), "-t", str(seconds),
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "23", "-threads", str(threads), str(output)
    ])[0]


def ssim(reference, candidate):
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-v", "info",
        "-i", str(reference), "-i", str(candidate),
        "-lavfi", "ssim", "-f", "null", "-"
    ], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    lines = [line for line in result.stderr.splitlines() if "SSIM Y:" in line]
    if not lines:
        raise RuntimeError("SSIM no apareció en la salida de FFmpeg")
    marker = "All:"
    return float(lines[-1].split(marker, 1)[1].split()[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=2)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error("La fuente no existe")
    if not (0 < args.seconds <= 120 and 1 <= args.repeats <= 12):
        parser.error("Requeridos: 0 < seconds <= 120; 1 <= repeats <= 12")
    if min(args.width, args.height, args.threads) < 1:
        parser.error("Dimensiones y threads deben ser positivos")
    if args.width % 2 or args.height % 2:
        parser.error("Para yuv420p, width y height deben ser pares")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("Se requieren ffmpeg y ffprobe")
    source = args.source.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if source.parent == output_dir and source.name.startswith("f4_"):
        parser.error("La fuente no puede ser una salida anterior de este benchmark")
    metadata = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "source_size_bytes": source.stat().st_size,
        "source_probe": probe(source),
        "ffmpeg": command_output(["ffmpeg", "-version"]).splitlines()[0],
        "ffprobe": command_output(["ffprobe", "-version"]).splitlines()[0],
        "config": {
            "seconds": args.seconds, "repeats": args.repeats,
            "width": args.width, "height": args.height,
            "threads": args.threads,
            "yaw": 35, "pitch": 12, "h_fov": 100, "v_fov": 62,
            "encoder": "libx264", "preset": "veryfast", "crf": 23
        },
        "notes": [
            "Una única fuente y parámetros constantes excepto interp.",
            "Alternancia AB/BA por repetición para reducir sesgo de orden.",
            "Elapsed incluye decodificación, reproyección, codificación y escritura.",
            "SSIM entre H.264 resultantes, NO frente a verdad-terreno.",
            "No certifica calidad de 360 real ni rendimiento total de Montara."
        ]
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    rows = []
    for repetition in range(1, args.repeats + 1):
        order = ("lanczos", "linear") if repetition % 2 else ("linear", "lanczos")
        outputs = {}
        elapsed = {}
        for mode in order:
            destination = output_dir / f"f4_run{repetition:02d}_{mode}.mp4"
            print(f"Repetición {repetition}/{args.repeats}: {mode}", flush=True)
            elapsed[mode] = encode(source, destination, mode, args.seconds,
                                   args.width, args.height, args.threads)
            outputs[mode] = destination
        similarity = ssim(outputs["lanczos"], outputs["linear"])
        row = {
            "repeat": repetition, "order": "->".join(order),
            "lanczos_s": round(elapsed["lanczos"], 4),
            "linear_s": round(elapsed["linear"], 4),
            "saving_pct": round(100 * (1 - elapsed["linear"] / elapsed["lanczos"]), 3),
            "ssim_all": round(similarity, 6),
            "lanczos_bytes": outputs["lanczos"].stat().st_size,
            "linear_bytes": outputs["linear"].stat().st_size
        }
        rows.append(row)
        print(row, flush=True)

    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Guardado: {output_dir / 'results.csv'}")
    print(f"Guardado: {output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
