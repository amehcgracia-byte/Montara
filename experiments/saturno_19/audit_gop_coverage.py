"""SATURNO-19: audit saved GOP selection evidence without media or FFmpeg.
Read-only stdlib audit; no hypothetical bytes presented as measurements.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"experiments/saturno_10/packet_results_40886014059.json"

def audit():
    root=json.loads(SOURCE.read_text())["report"]
    assert root["status"]=="PASS_INPUT_PREFLIGHT"
    rows=[]
    for row in root["sources"]:
        ranges=row["group_packet_ranges"]
        selection=row["groups_selected"]
        assert all(0<=i<len(ranges) for i in selection)
        assert ranges[0][0]==0 and ranges[-1][1]==row["source_packets"]
        assert all(ranges[i][1]==ranges[i+1][0] for i in range(len(ranges)-1))
        count=sum(b-a for i,(a,b) in enumerate(ranges) if i in selection)
        assert count==row["retained_packets"]==row["source_packets"]
        assert row["original_video_packet_bytes"]==row["retained_video_packet_bytes"]
        rows.append({"source":Path(row["source"]).name,"gops_total":len(ranges),
                     "gops_selected":len(selection),"packet_count":row["source_packets"],
                     "packets_retained":row["retained_packets"],
                     "payload_bytes":row["original_video_packet_bytes"],
                     "retained_payload_bytes":row["retained_video_packet_bytes"],
                     "selection_fraction":len(selection)/len(ranges),
                     "window_count":len(row["needed_windows"])})
    total=sum(x["payload_bytes"] for x in rows)
    kept=sum(x["retained_payload_bytes"] for x in rows)
    result={"experiment":"SATURNO-19","status":"NO_SELECTIVE_GOP_SAVINGS_IN_CURRENT_FIXTURE",
            "source_provenance":str(SOURCE.relative_to(ROOT)),
            "rows":rows,"video_payload_bytes":total,"retained_video_payload_bytes":kept,
            "video_payload_saved_bytes":total-kept,
            "limits":"Packet selection audit of saved evidence only, not a new source or render test. Video container and transfer cost not measured."}
    print(json.dumps(result,indent=2))
    return result
if __name__=="__main__":
    audit()
