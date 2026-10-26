import json,time,subprocess,re,traceback
from pathlib import Path
from yt_dlp import YoutubeDL
ROOT=Path(__file__).resolve().parents[1];raw=Path('/tmp/montara-green-raw');raw.mkdir(exist_ok=True)
choices={
'quotes-just-do-it':'PcdHp_tLUmA','quotes-are-you-sure':'BLikP6BDH5w','quotes-time-to-stop':'lw7nKebW1UQ','quotes-nice':'3GkCn522b0s','quotes-emotional-damage':'RUG1fY7aZ88','quotes-hell-no':'VSghZUJKgJY','quotes-wait-minute':'qbEBwq9nq1k','quotes-be-back':'goYJ-Esa5p4','quotes-oprah':'4cQV97UqyhI','quotes-sofia':'FuLdeSDKaW0',
'scenes-snow':'dUutlcgrdsA','scenes-rain':'H-N2ahaNhK8','scenes-fire':'JPfOGcOnPmM','scenes-smoke':'6LOm2Esb8x0','scenes-fog':'-5_PCEwIuk0','scenes-lightning':'9nRe-SqWQ0o','scenes-sparks':'-OBcBLkBsqs','scenes-wind':'geTs_pLRTNc','scenes-tornado':'Fqk_cItE7AA','scenes-light':'7Evi9Zi3twM',
'paint-circle':'nOgcv68nxRQ','paint-line':'SR3qprApqfo','paint-arrow':'7Sdz2YaHRUA','paint-underline':'6bRduvu0BAc','paint-cross':'n4qhP9B2Lp8','paint-tick':'6sWOo285xYM','paint-triangle':'czVDP_v8cU8','paint-square':'v434uG-Wfq0','paint-splatter':'V1eWnutyRO4','paint-spiral':'MRYRmoKB9PE',
'text-math':'DCNDB-TySyA','text-matrix':'KCVN-SuBBWM','text-question':'s_aLE7YWy1c','text-exclamation':'snfGaQFT8-E','text-speech':'qlTZHSUZfCk','text-wow':'PAZcDFo_zsQ','text-loading':'goywJtH7tuI','text-countdown':'NDxV6AAiu2k','text-glitch':'cKfZyuoXccQ'}
items=json.load(open('/tmp/montara-green-search.json'));logpath=raw/'sources.json';done=json.loads(logpath.read_text()) if logpath.exists() else {}
for item in items:
 key=item['id']
 if key not in choices or key in done and Path(done[key].get('raw','missing')).is_file():continue
 ids=[choices[key]]+[c['id'] for c in item['candidates'] if c['id']!=choices[key] and c.get('duration',999)<180 and 'tutorial' not in c['title'].lower() and 'how to' not in c['title'].lower()]
 for candidate in ids[:2]:
  try:
   folder=raw/key;folder.mkdir(exist_ok=True)
   options={'quiet':True,'no_warnings':True,'noprogress':True,'noplaylist':True,'socket_timeout':15,'retries':1,'fragment_retries':1,'format':'b[height<=720]/bv[height<=720]+ba/b','merge_output_format':'mp4','max_filesize':50*1024*1024,'outtmpl':str(folder/'source.%(ext)s'),'ffmpeg_location':'/usr/local/bin/ffmpeg','concurrent_fragment_downloads':1}
   with YoutubeDL(options) as y:info=y.extract_info('https://www.youtube.com/watch?v='+candidate,download=True)
   files=[p for p in folder.glob('source.*') if p.suffix in ['.mp4','.mkv','.webm']]
   if not files:raise RuntimeError('No media')
   name=item['name']
   if key=='quotes-oprah':name='Show me the money'
   if key=='quotes-hell-no':name='Steve Carell · No, God, please no'
   if key=='quotes-wait-minute':name='Wait a minute!'
   if key=='quotes-sofia':name='Sofía Vergara · Smart in Spanish'
   done[key]={**{k:item[k] for k in ['id','category']},'name':name,'source_url':'https://www.youtube.com/watch?v='+candidate,'source_title':info.get('title'),'creator':info.get('uploader'),'source_duration':info.get('duration'),'license':info.get('license') or 'Rights not verified; source retained','raw':str(files[0])}
   logpath.write_text(json.dumps(done,ensure_ascii=False,indent=2));print('READY',key,info.get('duration'),info.get('title'),flush=True);break
  except Exception as exc:print('FAILED',key,candidate,str(exc)[-220:],flush=True)
 time.sleep(.8)
print('TOTAL',len(done),flush=True)
