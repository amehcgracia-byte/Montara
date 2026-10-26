"""Local proxy prototype. Originals and absolute paths never enter public metadata.

Run: python -m local_media.proxies VIDEO --cache FOLDER [--sphere]
Not yet wired into the public web upload or its final renderer.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess


def probe(path):
    return json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],check=True,capture_output=True,text=True).stdout)


def stamp(path):
    s=path.stat();return {'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}


def prepare(source,cache,sphere=False):
    source=Path(source).resolve();cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    if source.suffix.lower() in {'.insv','.msv','.360','.insp','.lrv'}:
        raise ValueError('Export a stitched equirectangular MP4 from your camera app first.')
    original=probe(source);video=next(s for s in original['streams'] if s['codec_type']=='video')
    fingerprint=stamp(source)
    key=hashlib.sha256(json.dumps([str(source),fingerprint,sphere,'proxy019']).encode()).hexdigest()[:24]
    private=cache/(key+'.local.json');proxy=cache/(key+'.mp4')
    if private.exists() and proxy.exists():return json.loads(private.read_text())
    pending=cache/(key+'.pending.mp4')
    scale='scale=2048:1024' if sphere else "scale=w='min(960,iw)':h=-2"
    try:
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-copyts','-start_at_zero','-i',str(source),'-map','0:v:0','-map','0:a:0?','-vf',scale,'-fps_mode','passthrough','-c:v','libx264','-preset','veryfast','-crf','28','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart',str(pending)],check=True,capture_output=True)
        proxy_info=probe(pending);pv=next(s for s in proxy_info['streams'] if s['codec_type']=='video')
        duration=float(video.get('duration') or original['format']['duration'])
        pd=float(pv.get('duration') or proxy_info['format']['duration'])
        fps=video.get('avg_frame_rate','30/1');a,b=map(float,fps.split('/'));tolerance=max(.12,2/(a/b if a and b else 30))
        if abs(duration-pd)>tolerance:raise ValueError('Proxy timing differs from the original; this source needs a dedicated adapter.')
        pending.replace(proxy)
        public={'source_id':key,'duration':duration,'proxy_duration':pd,'projection':'equirectangular' if sphere else 'flat','width':pv['width'],'height':pv['height'],'frame_rate':fps,'proxy_bytes':proxy.stat().st_size}
        record={'source_id':key,'original':str(source),'original_stamp':fingerprint,'proxy':str(proxy),'public':public}
        private.write_text(json.dumps(record,indent=2));(cache/(key+'.public.json')).write_text(json.dumps(public,indent=2))
        return record
    finally:pending.unlink(missing_ok=True)


def resolve_recipe(recipe,cache):
    """Resolve cloud decisions to unchanged local originals, never to the proxies."""
    result=[]
    for clip in recipe['clips']:
        key=clip['source_id']
        if len(key)!=24 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Unknown source ID')
        record=json.loads((Path(cache)/(key+'.local.json')).read_text());original=Path(record['original'])
        if stamp(original)!=record['original_stamp']:raise ValueError('The original changed; prepare it again before export.')
        start,end=float(clip['start']),float(clip['end'])
        if not 0<=start<end<=record['public']['duration']+.001:raise ValueError('Cut outside the original timeline')
        result.append({'original':str(original),'start':start,'end':end,'source_id':key})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('--cache',required=True);parser.add_argument('--sphere',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.cache,args.sphere)['public'],indent=2))
