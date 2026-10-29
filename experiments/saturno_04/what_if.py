"""SATURNO-04: what-if model, not a measured benchmark. Decimal GB and effective Mbps."""
from dataclasses import dataclass,asdict
import argparse,json,math

@dataclass(frozen=True)
class Case:
    source_gb:float=80
    package_gb:float=10
    upload_mbps:float=100
    download_mbps:float=100
    rendered_gb:float=2
    local_render_s:float=3600
    package_prepare_s:float=300
    remote_render_s:float=900
    queue_and_start_s:float=120
    verify_s:float=30

def run(c):
    values=asdict(c)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values.values()):
        raise ValueError("All inputs must be positive finite values")
    if c.package_gb>c.source_gb:
        raise ValueError("A larger package must be modelled explicitly")
    def net(gb,mbps):return gb*8000/mbps
    full=c.queue_and_start_s+net(c.source_gb,c.upload_mbps)+c.remote_render_s+net(c.rendered_gb,c.download_mbps)+c.verify_s
    part=c.package_prepare_s+c.queue_and_start_s+net(c.package_gb,c.upload_mbps)+c.remote_render_s+net(c.rendered_gb,c.download_mbps)+c.verify_s
    return {"schema":"saturno-04-what-if-v1","inputs":values,
        "local_s":c.local_render_s,"remote_full_s":round(full,2),
        "remote_partial_s":round(part,2),"full_upload_s":round(net(c.source_gb,c.upload_mbps),2),
        "package_upload_s":round(net(c.package_gb,c.upload_mbps),2),
        "partial_faster_than_local":part<c.local_render_s,
        "note":"Purely illustrative; actual link throughput, render times and storage/costs unmeasured."}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k,v in asdict(Case()).items():p.add_argument("--"+k.replace("_","-"),default=v,type=float)
    print(json.dumps(run(Case(**vars(p.parse_args()))),indent=2))
