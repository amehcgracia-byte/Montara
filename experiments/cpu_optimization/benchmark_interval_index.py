#!/usr/bin/env python3
"""JÚPITER-OPT-01: microbenchmark CPU sin vídeo y sin modificar el motor.

Compara el patrón O(S*W) del texto de escenas en show_cut_edit.py con
bisect sobre los tiempos de las palabras, y el patrón de solapes de cues
con una ventana temporal indexada. Comprueba igualdad EXACTA de resultados
antes de reportar rendimiento. Casos con datos ordenados y escenarios
adversos. No extrapolar estos resultados al tiempo total de exportación.

Ejemplo:
  python3 experiments/cpu_optimization/benchmark_interval_index.py \\
    --repeats 5 --output /tmp/montara-opt01
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import platform
import random
import statistics
import time
from pathlib import Path


def original_scenes(scenes, words):
    return [" ".join(w for w, x, y in words if start <= x < end)
            for start, end in scenes]


def indexed_scenes(scenes, words):
    # El código original comprueba start <= x < end; índice válido solo si
    # los x están ordenados (se valida y no se ordena para no cambiar semántica).
    times = [x for _, x, _ in words]
    if any(a > b for a, b in zip(times, times[1:])):
        return original_scenes(scenes, words), False
    result = []
    for start, end in scenes:
        left = bisect.bisect_left(times, start)
        right = bisect.bisect_left(times, end)
        result.append(" ".join(w for w, _, _ in words[left:right]))
    return result, True


def original_cues(cues, kept):
    result = []
    for start, end in cues:
        matches = [e for e in kept if e[0] < end and e[1] > start]
        result.append(max(matches, key=lambda e: min(e[1], end) - max(e[0], start))
                      if matches else None)
    return result


def indexed_cues(cues, kept):
    # Índice por inicio; filtra hasta start < cue.end. Preserva el orden
    # ORIGINAL de kept para respetar el primer empate en max().
    starts = sorted((e[0], idx) for idx, e in enumerate(kept))
    sorted_times = [x for x, _ in starts]
    output = []
    for begin, end in cues:
        count = bisect.bisect_left(sorted_times, end)
        candidate_indices = sorted(idx for _, idx in starts[:count]
                                   if kept[idx][1] > begin)
        matches = [kept[idx] for idx in candidate_indices]
        output.append(max(matches, key=lambda e: min(e[1], end) - max(e[0], begin))
                      if matches else None)
    return output


def timed(fn, *args):
    t = time.perf_counter()
    result = fn(*args)
    return time.perf_counter() - t, result


def run_case(kind, size, repeats, seed):
    rng = random.Random(seed + size)
    # Normal: palabras de medio segundo, escenas de ~20 s.
    # El caso de cues simula correcciones dispersas (kept ~size/2).
    if kind == "scenes":
        words = [(f"w{i}", i * 0.25, i * 0.25 + 0.10) for i in range(size)]
        scenes = [(i * 5.0, i * 5.0 + 7.0) for i in range(max(1, size // 25))]
        base = lambda: original_scenes(scenes, words)
        candidate = lambda: indexed_scenes(scenes, words)[0]
        optimized = True
    else:
        kept = [(i * 1.5, i * 1.5 + 0.9, f"cue{i}") for i in range(size)]
        cues = [(rng.randrange(size) * 1.5, 0) for _ in range(size)]
        cues = [(a, a + 0.75) for a, _ in cues]
        base = lambda: original_cues(cues, kept)
        candidate = lambda: indexed_cues(cues, kept)
        optimized = True
    if base() != candidate():
        raise AssertionError(f"Different outputs: {kind} size={size}")
    runs = []
    for i in range(repeats):
        # AB/BA alternancia para atenuar sesgo de orden.
        a, b = (("original", base), ("indexed", candidate))
        sequence = [a, b] if i % 2 == 0 else [b, a]
        d = {}
        for name, call in sequence:
            elapsed, result = timed(call)
            d[name] = elapsed
        runs.append(d)
    old = statistics.median(x["original"] for x in runs)
    new = statistics.median(x["indexed"] for x in runs)
    return {"case": kind, "size": size, "repeats": repeats,
            "original_median_ms": round(old * 1000, 3),
            "indexed_median_ms": round(new * 1000, 3),
            "speedup_x": round(old / new, 3) if new > 0 else None,
            "outputs_equal": True, "notes": "Synthetic CPU microbenchmark; excludes I/O/render."}


def edge_tests():
    words = [("a", 1.0, 1.1), ("b", 1.0, 1.2), ("c", 2.0, 2.1)]
    scenes = [(1.0, 2.0), (2.0, 2.0), (-1.0, 10.0)]
    assert original_scenes(scenes, words) == indexed_scenes(scenes, words)[0]
    unsorted = [words[2], words[0], words[1]]
    value, indexed = indexed_scenes(scenes, unsorted)
    assert not indexed and value == original_scenes(scenes, unsorted)
    kept = [(1, 4, "a"), (1, 4, "b"), (0, 5, "c"), (7, 8, "d")]
    cues = [(2, 3), (4, 5), (6, 6), (9, 10)]
    assert original_cues(cues, kept) == indexed_cues(cues, kept)
    assert original_cues([(2, 3)], kept)[0][2] == "a"  # empate estable


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sizes", default="200,1000,3000")
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]
    if not 1 <= args.repeats <= 15 or not sizes or any(not 1 <= n <= 10000 for n in sizes):
        p.error("1 <= repeats <= 15, 1 <= each size <= 10000")
    edge_tests()
    print("Comprobación de bordes y empates: OK", flush=True)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind in ("scenes", "cues"):
        for size in sizes:
            r = run_case(kind, size, args.repeats, 20261030)
            rows.append(r)
            print(r, flush=True)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    report = {"python": platform.python_version(), "platform": platform.platform(),
              "sizes": sizes, "repeats": args.repeats, "edge_tests_pass": True,
              "results": rows,
              "limitations": [
                  "La variante indexada de cues usa ordenación y filtrado de candidatos; podría ser más lenta.",
                  "Escenas indexadas requieren timestamps ordenados; fallback sin índice si no lo están.",
                  "Los datos son sintéticos y el benchmark no incluye FFmpeg ni ruta E2E.",
                  "No modificar código productivo sin tests reales y perfil de coste."
              ]}
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Resultados: {out / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
