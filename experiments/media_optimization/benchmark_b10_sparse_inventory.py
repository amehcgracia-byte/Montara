"""B10: isolate file COUNT from logical video BYTES without allocating huge media.

Sparse placeholders contain no video payload and cannot measure FFmpeg, proxies,
seeks, rendering or real disk/USB/NAS throughput. Use real footage separately.
"""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from pathlib import Path

from experiments.media_optimization.benchmark_b08_folder import inventory


def run(*, counts=(10,100,1000), logical_bytes=(10**9,10**10,10**11), repeats=9):
    if len(counts) != len(logical_bytes) or repeats < 3:
        raise ValueError("Provide matching scenarios and >=3 runs")
    results=[]
    for num, total in zip(counts, logical_bytes):
        if num < 1 or total < num:
            raise ValueError("Invalid sparse scenario")
        with tempfile.TemporaryDirectory(prefix="montara-b10-") as td:
            folder=Path(td)
            for i in range(num):
                with (folder / f"camera-{i:05}.mp4").open("wb") as f:
                    f.truncate(total // num)
            timings=[]
            for _ in range(repeats):
                report=inventory(folder)
                assert report["counts"]["video"]==num
                timings.append(report["elapsed_seconds"]*1000)
            results.append({
                "file_count":num,
                "logical_source_bytes":report["total_source_bytes"],
                "median_inventory_ms":round(statistics.median(timings),3),
                "minimum_ms":round(min(timings),3),
                "maximum_ms":round(max(timings),3),
                "samples":len(timings),
                "bytes_uploaded":0,
                "copies_created":0,
                "fixture":"sparse zero-payload placeholders; not valid media",
            })
    return {"benchmark":"B10-inventory-file-count-v1", "results":results}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=json.dumps(run(),indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(result)
    print(result,end="")
