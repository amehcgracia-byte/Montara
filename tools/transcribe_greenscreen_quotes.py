import json,subprocess
from pathlib import Path
from faster_whisper import WhisperModel
root=Path('/tmp/montara-green-raw');sources=json.loads((root/'sources.json').read_text());target=root/'transcripts.json';done=json.loads(target.read_text()) if target.exists() else {}
model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=2,local_files_only=True)
keywords={'quotes-just-do-it':['do it'],'quotes-are-you-sure':['sure'],'quotes-time-to-stop':['time to stop'],'quotes-nice':['nice','noice'],'quotes-emotional-damage':['damage'],'quotes-hell-no':['hell'],'quotes-wait-minute':['wait'],'quotes-be-back':['back'],'quotes-oprah':['money'],'quotes-sofia':['spanish']}
for key,s in sources.items():
 if s['category']!='quotes' or key in done:continue
 try:
  wav=root/(key+'.wav');subprocess.run(['/usr/local/bin/ffmpeg','-v','error','-y','-i',s['raw'],'-vn','-ar','16000','-ac','1',str(wav)],check=True)
  segments,info=model.transcribe(str(wav),language='en',vad_filter=False,word_timestamps=True)
  rows=[{'start':r.start,'end':r.end,'text':r.text,'words':[{'start':w.start,'end':w.end,'word':w.word} for w in r.words]} for r in segments]
  wanted=next((r for r in rows if any(k in r['text'].lower() for k in keywords[key])),None)
  duration=s['source_duration'];window=[max(0,wanted['start']-.12),min(duration,wanted['end']+.15)] if wanted else [0,min(duration,6)]
  if window[1]-window[0]>8:window[1]=window[0]+8
  done[key]={'segments':rows,'window':window};target.write_text(json.dumps(done,indent=2));print(key,json.dumps(done[key]),flush=True)
 except Exception as e:print('FAILED',key,str(e),flush=True)
