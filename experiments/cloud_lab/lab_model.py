"""Montara hybrid lab: pure, deterministic end-to-end timing/cost model."""
from dataclasses import dataclass, asdict
import argparse, json

@dataclass(frozen=True)
class Scenario:
    input_gib: float
    output_gib: float
    upload_mbps: float
    download_mbps: float
    remote_compute_s: float
    local_compute_s: float
    queue_s: float = 0
    startup_s: float = 0
    gpu_usd_per_hour: float = 0
    billed_extra_s: float = 0

def estimate(s: Scenario) -> dict:
    for name, value in asdict(s).items():
        if not isinstance(value,(float,int)) or value != value or value in (float('inf'),float('-inf')) or value < 0:
            raise ValueError(f'{name} must be finite and nonnegative')
    if s.upload_mbps == 0 or s.download_mbps == 0:
        raise ValueError('network throughput must be positive')
    upload_s = s.input_gib * (1024**3) * 8 / (s.upload_mbps * 1_000_000)
    download_s = s.output_gib * (1024**3) * 8 / (s.download_mbps * 1_000_000)
    total_s = upload_s + download_s + s.queue_s + s.startup_s + s.remote_compute_s
    gpu_billed_s = s.startup_s + s.remote_compute_s + s.billed_extra_s
    return {'upload_s':round(upload_s,2),'download_s':round(download_s,2),'remote_total_s':round(total_s,2),
            'local_total_s':s.local_compute_s,'remote_advantage_s':round(s.local_compute_s-total_s,2),
            'gpu_compute_bill_usd':round(gpu_billed_s*s.gpu_usd_per_hour/3600,4),
            'note':'Modeled, not benchmarked. Excludes storage, network charges, provisioning variability, failures, taxes.'}
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-gib',type=float,required=True);p.add_argument('--output-gib',type=float,required=True)
    p.add_argument('--upload-mbps',type=float,required=True);p.add_argument('--download-mbps',type=float,required=True)
    p.add_argument('--remote-compute-s',type=float,required=True);p.add_argument('--local-compute-s',type=float,required=True)
    p.add_argument('--queue-s',type=float,default=0);p.add_argument('--startup-s',type=float,default=0)
    p.add_argument('--gpu-usd-per-hour',type=float,default=0);p.add_argument('--billed-extra-s',type=float,default=0)
    print(json.dumps(estimate(Scenario(**vars(p.parse_args()))),indent=2))
