"""SATURNO-25: measured preparation, bytes, controlled loopback transfer, cost scenarios.

No full render. Uses the exact SATURNO-24 packaging algorithm and Stage plan,
but no foreign cloud or network. Loopback HTTP is labelled explicitly as local.
"""
import hashlib,http.server,json,os,shutil,socketserver,subprocess,sys,threading,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.saturno_10.packet_preflight import probe,choose_gops,copy_sparse
OUT=Path("/tmp/saturno25")
def run(args):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=180)
    if p.returncode:raise RuntimeError(p.stderr[-1500:])
    return p.stdout
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return h.hexdigest()
def make_zip(paths,target):
    start=time.perf_counter()
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:z.write(p,p.name)
    return {"bytes":target.stat().st_size,"sha256":sha(target),"seconds":time.perf_counter()-start}
def main():
    OUT.mkdir(exist_ok=True)
    report={"experiment":"SATURNO-25","status":"NOT_RUN","network_type":"LOCAL_LOOPBACK_HTTP_ONLY","remote_network_measured":False,"phases":{}}
    try:
        from experiments.saturno_10.packet_preflight import rewrite
        import copy
        here=ROOT/"experiments/saturno_10"
        data=json.loads((here/"stage_project.json").read_text())
        plan=json.loads((here/"stage_edit_plan.json").read_text())
        extended=OUT/"extended";extended.mkdir(exist_ok=True)
        packaged=OUT/"packaged";packaged.mkdir(exist_ok=True)
        originals=[];packed=[];rows=[];mapping={}
        start=time.perf_counter()
        for item in data["inputs"]["videos"]:
            source=Path(item["path"])
            base=extended/("base-"+source.name)
            run(["ffmpeg","-v","error","-nostdin","-y","-i",source,
                 "-map","0:v:0","-an","-c:v","copy",base])
            manifest=extended/(source.stem+".txt")
            manifest.write_text(("file '"+str(base)+"'\n")*3)
            long_video=extended/source.name
            run(["ffmpeg","-v","error","-nostdin","-y","-f","concat","-safe","0","-i",manifest,
                 "-map","0:v:0","-an","-c:v","copy","-avoid_negative_ts","disabled",long_video])
            p=probe(str(long_video),packets=True)
            first_duration=float(probe(str(base))["format"]["duration"])
            fps=float(item["probe"]["fps"])
            segments=[s for s in plan["segments"] if s.get("source_path")==str(source)]
            windows=[(float(s["clip_start_sec"]),float(s["clip_start_sec"])+float(s["duration_sec"])) for s in segments]
            windows.append((0,first_duration+2/max(fps,1)))
            # Identical colour-sampling input windows to SATURNO-24.
            sys.path.insert(0,str(ROOT/"engine"))
            from core.project import Project
            import core.stages.export as export
            project=Project(OUT/"colour-probe",data)
            samples=export._visible_color_samples(project,segments) if item.get("probe",{}).get("projection")=="equirect" else None
            cmds=export.color_sample_commands(str(long_video),float(p["format"]["duration"]),samples=samples)
            for cmd in cmds:
                a=float(cmd[cmd.index("-ss")+1]);d=float(cmd[cmd.index("-t")+1]);windows.append((a,a+d))
            groups,selected,indices=choose_gops(p["packets"],windows,1/max(fps,1))
            assert len(selected)<len(groups)
            compact=packaged/source.name
            copy_sparse(str(long_video),str(compact),p,groups,selected)
            check=probe(str(compact),packets=True)["packets"]
            expected=[p["packets"][i] for i in indices]
            assert len(check)==len(expected) and all(all(a.get(k)==b.get(k) for k in ("data_hash","pts","dts")) for a,b in zip(expected,check))
            originals.append(long_video);packed.append(compact)
            mapping[str(source)]=str(compact)
            if item.get("normalized",{}).get("path"):mapping[item["normalized"]["path"]]=str(compact)
            rows.append({"camera":source.name,"original_bytes":long_video.stat().st_size,
                         "package_bytes":compact.stat().st_size,
                         "gops_total":len(groups),"gops_retained":len(selected)})
        master=Path(data["inputs"]["master"]["path"])
        shutil.copy2(master,packaged/"master.mp3")
        originals.append(master);packed.append(packaged/"master.mp3")
        mapping[str(master)]=str(packaged/"master.mp3")
        (packaged/"project.json").write_text(json.dumps(rewrite(copy.deepcopy(data),mapping)))
        (packaged/"plan.json").write_text(json.dumps(rewrite(copy.deepcopy(plan),mapping)))
        report["phases"]["prepare"]={"seconds":time.perf_counter()-start,"cameras":rows,
            "same_media_basis_original_bytes":sum(p.stat().st_size for p in originals),
            "same_media_basis_package_bytes":sum(p.stat().st_size for p in packed)}
        report["phases"]["archive"]={}
        original_archive=OUT/"original.zip";package_archive=OUT/"package.zip"
        report["phases"]["archive"]["original"]=make_zip(originals,original_archive)
        report["phases"]["archive"]["package"]=make_zip(sorted(packaged.iterdir()),package_archive)
        # ZIPs have differing membership: B includes plan/project; report explicitly.
        # Local TCP loopback transfers are not external or internet uplinks.
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n=int(self.headers["Content-Length"])
                h=hashlib.sha256();received=0
                while received<n:
                    chunk=self.rfile.read(min(65536,n-received))
                    if not chunk:break
                    h.update(chunk);received+=len(chunk)
                self.server.received=(received,h.hexdigest())
                self.send_response(200);self.end_headers()
                self.wfile.write(b"ok")
            def log_message(self,*args):pass
        class Server(socketserver.ThreadingMixIn,http.server.HTTPServer):
            daemon_threads=True
        server=Server(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            measured={}
            for label,path in (("original",original_archive),("package",package_archive)):
                values=[]
                for _ in range(3):
                    payload=path.read_bytes()
                    request=urllib.request.Request("http://127.0.0.1:"+str(server.server_port)+"/upload",data=payload,method="POST")
                    begin=time.perf_counter()
                    with urllib.request.urlopen(request,timeout=40) as response:
                        assert response.status==200 and response.read()==b"ok"
                    seconds=time.perf_counter()-begin
                    assert server.received==(len(payload),sha(path))
                    values.append(seconds)
                measured[label]={"bytes":path.stat().st_size,"seconds_trials":values,
                    "seconds_median":sorted(values)[1],"sha256_verified":True}
            report["phases"]["transfer_loopback"]=measured
        finally:server.shutdown();server.server_close()
        raw=report["phases"]["prepare"]
        raw["media_bytes_saved"]=raw["same_media_basis_original_bytes"]-raw["same_media_basis_package_bytes"]
        raw["media_fraction_saved"]=raw["media_bytes_saved"]/raw["same_media_basis_original_bytes"]
        zip_a=original_archive.stat().st_size;zip_b=package_archive.stat().st_size
        report["phases"]["economic_scenarios"]={
            "declared_assumption":"linear outbound transfer fee only; not provider quotes, not measured financial costs",
            "eur_per_GB_scenarios":[0.02,0.05,0.10],
            "GB_decimal":1000000000,
            "archive_original_bytes":zip_a,"archive_package_bytes":zip_b,
            "bytes_saved_per_upload":zip_a-zip_b,
            "savings_eur_per_10000_uploads":{
                str(p):round((zip_a-zip_b)*10000/1000000000*p,6) for p in (0.02,0.05,0.10)}}
        report["status"]="CONTROLLED_PREPARE_TRANSFER_ECONOMICS_MEASURED" if zip_b<zip_a and raw["media_bytes_saved"]>0 else "GATE_FAILED"
    except Exception as exc:report.update(status="OPERATIONAL_ERROR",error=repr(exc))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(report,indent=2))
        print("SATURNO25_SUMMARY="+json.dumps(report,separators=(",",":")),flush=True)
    return 0 if report["status"]=="CONTROLLED_PREPARE_TRANSFER_ECONOMICS_MEASURED" else 1
if __name__=="__main__":raise SystemExit(main())
