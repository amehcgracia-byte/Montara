"""SATURNO-04: scenario break-even. Not a benchmark. Decimal GB and sustained Mbps."""
from dataclasses import dataclass,asdict
import argparse,json,math
@dataclass(frozen=True)
class Scenario:
    source_gb:float=80
    package_gb:float=10
    upload_mbps:float=100
    download_mbps:float=100
    output_gb:float=2
    local_render_s:float=3600
    prepare_s:float=300
    queue_s:float=120
    cloud_render_s:float=900
    verify_s:float=30
    cloud_usd_hour:float=0.8
    storage_usd_gb_month:float=0.1
    storage_days:float=1
def evaluate(s):
    d=asdict(s)
    if any(not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in d.values()):
        raise ValueError("all values must be positive and finite")
    if s.package_gb>s.source_gb:raise ValueError("package exceeds source; unsupported by restricted model")
    transfer=lambda gb,rate:gb*8000/rate
    down=transfer(s.output_gb,s.download_mbps)
    fixed=s.prepare_s+s.queue_s+s.cloud_render_s+down+s.verify_s
    partial=fixed+transfer(s.package_gb,s.upload_mbps)
    full=s.queue_s+s.cloud_render_s+transfer(s.source_gb,s.upload_mbps)+down+s.verify_s
    threshold=max(0,(s.local_render_s-fixed)*s.upload_mbps/8000)
    rate=None if fixed>=s.local_render_s else 8000*s.package_gb/(s.local_render_s-fixed)
    compute=partial/3600*s.cloud_usd_hour
    storage=s.package_gb*s.storage_usd_gb_month*s.storage_days/30
    return dict(schema="saturno-04-decision-v1",inputs=d,local_seconds=s.local_render_s,
        remote_full_seconds=round(full,2),remote_partial_seconds=round(partial,2),
        remote_fixed_seconds=round(fixed,2),max_package_gb_to_beat_local=round(threshold,4),
        min_upload_mbps_to_beat_local=None if rate is None else round(rate,4),
        partial_faster=partial<s.local_render_s,illustrative_cloud_usd=round(compute+storage,4),
        assumptions=["Hypothetical values, not measured Montara times","Effective Mbps and decimal GB",
        "Assumes pod billing covers full elapsed time; simplified pro-rata storage",
        "Excludes egress taxes failed jobs, storage minimums and local power",
        "No proven Zucker partial media export"])
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k,v in asdict(Scenario()).items():p.add_argument("--"+k.replace("_","-"),type=float,default=v)
    print(json.dumps(evaluate(Scenario(**vars(p.parse_args()))),indent=2))
