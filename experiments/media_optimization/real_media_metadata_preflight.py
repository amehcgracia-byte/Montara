#!/usr/bin/env python3
"""Inspect bounded packet timestamps and 360 metadata; ffprobe only.

Never decodes frames, writes derived media, or modifies inputs. The user
must run this when the shared VM is no longer under heavy rendering load.
"""
import argparse
import collections
import json
import statistics
import subprocess
from pathlib import Path

def probe(path, entries, interval=None):
    cmd=["ffprobe","-v","error"]
    if interval: cmd+=["-read_intervals",interval]
    cmd+=["-select_streams","v:0","-show_entries",entries,"-of","json",str(path)]
    res=subprocess.run(cmd,capture_output=True,text=True,timeout=90,check=True)
    return json.loads(res.stdout)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--iphone",type=Path,required=True)
    p.add_argument("--spherical",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error("Report exists; refusing to overwrite")
    meta={}
    for kind,path in (("iphone",a.iphone),("spherical",a.spherical)):
        if not path.is_file():p.error(f"{kind} missing: {path}")
        info=probe(path,"format=duration:stream=codec_name,width,height,avg_frame_rate,r_frame_rate,field_order,color_transfer,color_primaries,color_space:stream_tags:stream_side_data")
        meta[kind]={"file":path.name,"streams":info.get("streams",[]),"duration":info.get("format",{}).get("duration")}
    # Two short windows: avoid full 16-minute packet scan.
    windows={}
    for at in (5,60):
        info=probe(a.iphone,"packet=pts_time,dts_time,duration_time,flags",f"{at}%+3")
        packets=info.get("packets",[])
        pts=sorted(float(z["pts_time"]) for z in packets if z.get("pts_time") not in (None,"N/A"))
        intervals=[b-x for x,b in zip(pts,pts[1:]) if b>x]
        rounded=[round(x*1000,3) for x in intervals]
        counts=collections.Counter(rounded)
        windows[str(at)]={"packets":len(packets),"positive_pts_deltas":len(intervals),
            "median_pts_ms":round(statistics.median(rounded),4) if rounded else None,
            "unique_delta_ms":len(counts),"common_delta_ms":counts.most_common(8),
            "min_delta_ms":min(rounded) if rounded else None,
            "max_delta_ms":max(rounded) if rounded else None}
    result={"status":"BOUNDED_METADATA_INSPECTION","metadata":meta,
        "iphone_packet_windows":windows,
        "caveats":["Packet PTS variation is evidence of cadence irregularity, not full-file VFR certification.",
          "Packets may include GOP seek pre-roll; use decoded frame timestamps if packet data is inconclusive.",
          "360 projection cannot be confirmed solely by 2:1 frame shape.",
          "No frame decode or transcode performed."]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    for label,data in meta.items():
        print(f"{label}: duration={data['duration']}, streams={json.dumps(data['streams'],ensure_ascii=False)[:1200]}")
    print("iphone_packet_windows:",json.dumps(windows,ensure_ascii=False))
    print("REPORT:",a.output)
if __name__=="__main__":main()
