"""SATURNO-01: inventory source intervals from Zucker edit_plan.json (read-only).

This is NOT a media package, transfer size estimate or exact export execution plan.
ExportStage.run may normalize frames / landmarks and expand spherical segments.
"""
import argparse,json,math
from pathlib import Path

def finite(value,field,index):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(f"segment {index}: {field} must be finite numeric")
    return float(value)

def merge(intervals):
    result=[]
    for start,end in sorted(intervals):
        if result and start<=result[-1][1]+1e-9:
            result[-1][1]=max(result[-1][1],end)
        else:
            result.append([start,end])
    return result

def inventory(plan):
    segments=plan.get("segments") if isinstance(plan,dict) else plan
    if not isinstance(segments,list) or not segments:
        raise ValueError("expected nonempty edit_plan segments list")
    sources={}
    for index,segment in enumerate(segments,1):
        if not isinstance(segment,dict): raise ValueError(f"segment {index}: must be object")
        source=segment.get("source_path") or segment.get("clip_path")
        if not isinstance(source,str) or not source.strip():
            raise ValueError(f"segment {index}: missing source_path/clip_path")
        start=finite(segment.get("clip_start_sec"),"clip_start_sec",index)
        duration=finite(segment.get("duration_sec"),"duration_sec",index)
        if start<0 or duration<=0:
            raise ValueError(f"segment {index}: invalid start/duration")
        value=sources.setdefault(source,{"intervals":[],"segment_count":0})
        value["intervals"].append((start,start+duration));value["segment_count"]+=1
    items=[]
    for source,value in sorted(sources.items()):
        windows=merge(value["intervals"])
        items.append({"source":source,"segment_count":value["segment_count"],
            "unique_used_duration_sec":round(sum(b-a for a,b in windows),6),
            "intervals_sec":[[round(a,6),round(b,6)] for a,b in windows]})
    return {"schema":"saturno-01-v1","segment_count":len(segments),"source_count":len(items),
        "sources":items,"warnings":[
        "Logical edit intervals ONLY; not a transfer estimate or decodable byte package.",
        "Zucker ExportStage.run transforms edit_plan via spherical landmarks and frame normalization before rendering.",
        "No GOP dependencies, VFR/PTS, audio, transitions, overlays, logos or preroll accounted for.",
        "No render equivalence or byte saving proven."]}

def main():
    p=argparse.ArgumentParser();p.add_argument("edit_plan",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    output=json.dumps(inventory(json.loads(a.edit_plan.read_text(encoding="utf-8"))),indent=2,ensure_ascii=False)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(output,encoding="utf-8")
    else: print(output,end="")
if __name__=="__main__": main()
