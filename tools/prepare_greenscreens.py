"""Prepare downloaded clips only: compact encode, auditable source, real thumbnails."""
import json,subprocess,math,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];RAW=Path('/tmp/montara-green-raw');OUT=ROOT/'tests/fixtures/greenscreens';OUT.mkdir(parents=True,exist_ok=True)
FF='/usr/local/bin/ffmpeg';FP='/usr/local/bin/ffprobe'
def probe(path):return json.loads(subprocess.check_output([FP,'-v','error','-show_format','-show_streams','-of','json',str(path)]))
def samples(path):
 c=cv2.VideoCapture(str(path));fps=c.get(cv2.CAP_PROP_FPS) or 24;dur=c.get(cv2.CAP_PROP_FRAME_COUNT)/fps;rows=[]
 for t in np.linspace(.2,max(.2,dur-.3),min(60,max(6,int(dur*2)))):
  c.set(cv2.CAP_PROP_POS_MSEC,float(t*1000));ok,bgr=c.read()
  if not ok:continue
  rgb=cv2.cvtColor(cv2.resize(bgr,(160,90)),cv2.COLOR_BGR2RGB).astype(float);r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2];green=(g>r*1.35)&(g>b*1.25)&(g>70);black=np.max(rgb,axis=2)<28
  border=np.zeros(green.shape,bool);border[:6]=True;border[-6:]=True;border[:,:6]=True;border[:,-6:]=True
  rows.append((float(t),float(green.mean()),float(green[border].mean()),float(black.mean()),float(rgb.std(axis=(0,1)).mean())))
 c.release();return dur,rows
items=json.loads((OUT/'catalog.json').read_text()) if (OUT/'catalog.json').exists() else {'items':[],'pending':[]}
sources=json.loads((RAW/'sources.json').read_text());transcripts=json.loads((RAW/'transcripts.json').read_text()) if (RAW/'transcripts.json').exists() else {}
existing={i['id']:i for i in items['items']}
for key,item in sources.items():
 if key in existing and (OUT/existing[key]['file']).is_file():continue
 try:
  path=Path(item['raw']);duration,rows=samples(path)
  if not rows:raise ValueError('No decoded frames')
  maxgreen=max(x[1] for x in rows);matte='green' if maxgreen>.08 else 'black'
  if item['category']=='quotes':
   # Keep a spoken phrase together; prefer the manually reviewed transcript window.
   window=transcripts.get(key,{}).get('window');start,end=window or (0,min(duration,7));length=end-start
   if maxgreen<.08:raise ValueError('No green-screen cutout in this source')
  else:
   length=min(3,duration);best=max(rows,key=lambda x:(x[1]>.025)*(x[1]<.995)*2+(x[3]>.1)*(x[3]<.98)+x[4]/30)
   start=max(0,min(duration-length,best[0]-length/2))
   windows={"paint-circle":(5.2,3),"paint-line":(4.5,3),"paint-arrow":(39.8,3),"paint-underline":(8,3),"paint-tick":(12,3),"paint-spiral":(4,3)}
   if key in windows:start,length=windows[key]
  target=OUT/(key+'.mp4');pending=OUT/(key+'.part.mp4')
  cmd=[FF,'-v','error','-nostdin','-y','-ss',str(round(start,3)),'-i',str(path),'-t',str(round(length,3)),'-vf','scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=24,format=yuv420p','-c:v','libx264','-preset','fast','-crf','24','-maxrate','1400k','-bufsize','2800k','-threads','2']
  cmd+=['-c:a','aac','-b:a','80k','-ac','1'] if item['category']=='quotes' else ['-an']
  subprocess.run(cmd+['-movflags','+faststart',str(pending)],check=True,capture_output=True,timeout=90);pending.replace(target)
  meta=probe(target);actual=float(meta['format']['duration']);thumbtime=actual*.5
  subprocess.run([FF,'-v','error','-y','-ss',str(thumbtime),'-i',str(target),'-frames:v','1','-vf','scale=240:-2','-q:v','3','-threads','1',str(OUT/(key+'.jpg'))],check=True,capture_output=True,timeout=20)
  entry={k:v for k,v in item.items() if k not in ['raw','source_duration']};entry.update(file=target.name,duration=round(actual,3),bytes=target.stat().st_size,matte=matte,source_start=round(start,3),source_end=round(start+length,3))
  existing[key]=entry;items['items']=list(existing.values());(OUT/'catalog.json').write_text(json.dumps(items,ensure_ascii=False,indent=2));print('PREPARED',key,entry['bytes'],matte,flush=True)
 except Exception as e:print('REVIEW',key,str(e)[-250:],flush=True)
print('TOTAL',len(existing),sum(i['bytes'] for i in existing.values()),flush=True)
