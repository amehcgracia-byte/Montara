import json,time
from pathlib import Path
from yt_dlp import YoutubeDL
out=Path('/tmp/montara-green-search.json')
queries={
'quotes':[
('just-do-it','Shia LaBeouf · Just do it','Shia LaBeouf just do it green screen'),('are-you-sure','John Cena · Are you sure?','John Cena are you sure about that green screen'),('time-to-stop','Filthy Frank · Time to stop','Filthy Frank its time to stop green screen'),('nice','Michael Rosen · Nice','Michael Rosen nice green screen'),('emotional-damage','Steven He · Emotional damage','Steven He emotional damage green screen'),('hell-no','Steve Harvey · Oh hell no','Steve Harvey oh hell no green screen'),('wait-minute','Kevin Hart · Wait a minute','Kevin Hart wait a minute green screen'),('be-back','Arnold · I’ll be back','Arnold Schwarzenegger ill be back green screen'),('oprah','Oprah · You get a car','Oprah you get a car green screen'),('sofia','Sofía Vergara · Ay','Sofia Vergara ay green screen meme')],
'scenes':[(a,b,b+' green screen effect footage') for a,b in [('snow','Snow falling'),('rain','Rain overlay'),('fire','Fire flames'),('smoke','Smoke'),('fog','Fog mist'),('lightning','Lightning strike'),('sparks','Sparks'),('wind','Wind dust storm'),('tornado','Tornado'),('light','Light rays')]],
'paint':[(a,b,b+' green screen animation') for a,b in [('circle','Hand drawn circle'),('line','Brush stroke line'),('arrow','Hand drawn arrow'),('underline','Marker underline'),('cross','Hand drawn cross'),('tick','Hand drawn check mark'),('triangle','Triangle drawing'),('square','Square drawing'),('splatter','Paint splatter'),('spiral','Hand drawn spiral')]],
'text':[(a,b,b+' green screen effect') for a,b in [('math','Math formulas'),('latin','Latin words text'),('matrix','Matrix code'),('question','Question marks'),('exclamation','Exclamation marks'),('speech','Speech bubble'),('wow','Comic wow text'),('loading','Loading text'),('countdown','Countdown numbers'),('glitch','Glitch text')]]}
items=json.loads(out.read_text()) if out.exists() else []
for category,entries in queries.items():
 for key,name,query in entries:
  if any(i['id']==category+'-'+key for i in items):continue
  try:
   with YoutubeDL({'quiet':True,'no_warnings':True,'extract_flat':True,'skip_download':True,'socket_timeout':12,'retries':0}) as y:
    result=y.extract_info('ytsearch3:'+query,download=False)
   candidates=[{'id':e.get('id'),'title':e.get('title'),'url':e.get('url'),'duration':e.get('duration'),'channel':e.get('channel')} for e in result.get('entries',[])]
   item={'id':category+'-'+key,'category':category,'name':name,'query':query,'candidates':candidates};items.append(item);out.write_text(json.dumps(items,ensure_ascii=False,indent=2));print(json.dumps(item,ensure_ascii=False),flush=True)
  except Exception as e:print('FAILED',category,key,str(e)[:150],flush=True)
  time.sleep(.3)
