"""Private loopback curator. Selections live on disk, independently of Montara."""
import json,re,sys,threading,uuid,subprocess,unicodedata,os,shutil
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from yt_dlp import YoutubeDL
ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
FFMPEG=shutil.which('ffmpeg') or '/usr/local/bin/ffmpeg'
if not (DATA/'selection.json').exists() and (ROOT/'examples/selection.json').exists():shutil.copytree(ROOT/'examples',DATA,dirs_exist_ok=True)
DB=DATA/'selection.json';lock=threading.RLock();download_lock=threading.Lock();jobs={}
state=json.loads(DB.read_text()) if DB.exists() else {'candidates':[], 'clips':[], 'rejected':[]}
def save():
 with lock:
  tmp=DB.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2));tmp.replace(DB)
def slug(s):return re.sub(r'[^a-z0-9_-]+','-',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip('-')[:90] or 'sin-titulo'
def video_id(url):
 u=urlparse(url);v=(parse_qs(u.query).get('v') or [''])[0] if u.hostname in ('youtube.com','www.youtube.com','m.youtube.com') else u.path.strip('/').split('/')[0] if u.hostname=='youtu.be' else ''
 if u.hostname in ('youtube.com','www.youtube.com','m.youtube.com') and u.path.startswith('/shorts/'):v=u.path.split('/')[2]
 if not re.fullmatch(r'[A-Za-z0-9_-]{11}',v):raise ValueError('Pega un enlace de vídeo de YouTube válido.')
 return v
def infer_collection(title):
 return 'green' if re.search(r'green[ -]?screen|chroma|black[ -]?screen|overlay|backdrop|matrix.*code|rain.*code',title,re.I) else 'regular'
def add_candidates(entries,category,query,collection=None):
 with lock:
  known={x['id'] for x in state['candidates']}
  for x in entries:
   if not x.get('id') or x['id'] in known:continue
   state['candidates'].append({'id':x['id'],'title':x.get('title') or x['id'],'duration':x.get('duration'),'channel':x.get('channel') or x.get('uploader') or '', 'category':category,'query':query,'collection':collection or infer_collection(x.get('title',''))});known.add(x['id'])
  save()
def task(fn):
 key=uuid.uuid4().hex;jobs[key]={'status':'working','message':'Preparando…'}
 def run():
  try:fn(jobs[key]);jobs[key]['status']='done'
  except Exception as e:jobs[key].update(status='error',message=str(e)[-700:])
 threading.Thread(target=run,daemon=True).start();return key
SERIES_PATTERNS={'South Park':r'south.?park|cartman|butters|kenny|kyle|randy|pc principal','Simpsons':r'simpson|homer|marge|bart|lisa','Futurama':r'futurama|bender|leela|fry','Thundercats':r'thunder.?cats|lion.?o|mum.?ra','Sailor Moon':r'sailor|usagi|chibiusa|tuxedo','Dragon Ball':r'dragon.?ball|dbz|goku|vegeta|gohan|frieza','Tortugas Ninja':r'turtle|donatello|michaelangelo|michelangelo|raphael|leonardo','Looney Tunes':r'looney|bugs.?bunny|daffy|elmer|tweety|coyote|sylvester'}
def search(body,job):
 q=body['query'].strip();q += ' green screen' if body.get('collection','green')=='green' and not re.search(r'green[ -]?screen|chroma|overlay',q,re.I) else ' -greenscreen -"green screen"' if body.get('collection')=='regular' else '';limit=min(60,max(12,int(body.get('limit',12))))
 with YoutubeDL({'quiet':True,'no_warnings':True,'extract_flat':True,'skip_download':True,'socket_timeout':15,'retries':0}) as y:
  d=y.extract_info('ytsearch'+str(limit)+':'+q,download=False)
 entries=d.get('entries',[])
 collection=body.get('collection','green')
 entries=[e for e in entries if infer_collection(e.get('title',''))==collection]
 pattern=SERIES_PATTERNS.get(body.get('category','').split('/')[-1])
 if pattern:entries=[e for e in entries if re.search(pattern,e.get('title',''),re.I)]
 add_candidates(entries,body.get('category','Memes/Tendencias'),body.get('query',q),collection);job['message']=str(len(entries))+' candidatos encontrados. Ninguno se acepta automáticamente.'
def download(clip,job):
 job["message"]="En cola de descarga…"
 with download_lock:download_inner(clip,job)
def download_inner(clip,job):
 try:
  vid=clip['video_id'];cache=DATA/'fuentes';cache.mkdir(exist_ok=True);existing=list(cache.glob(vid+'.*'));existing=[p for p in existing if p.suffix in ('.mp4','.mkv','.webm')]
  if existing:source=existing[0]
  else:
   job['message']='Descargando la fuente aprobada…'
   with YoutubeDL({'quiet':True,'no_warnings':True,'format':'bestvideo[height<=480]+bestaudio/best[height<=480]/best','outtmpl':str(cache/(vid+'.%(ext)s')),'merge_output_format':'mp4','ffmpeg_location':str(Path(FFMPEG).parent),'socket_timeout':20,'retries':1,'max_filesize':600*1024*1024,'noplaylist':True}) as y:
    y.download(['https://www.youtube.com/watch?v='+vid])
   source=next(p for p in cache.glob(vid+'.*') if p.suffix in ('.mp4','.mkv','.webm'))
  folder=DATA/'biblioteca'/('green-screens' if clip.get('collection','green')=='green' else 'videos-con-fondo')
  for part in clip['category'].split('/'):folder=folder/slug(part)
  folder.mkdir(parents=True,exist_ok=True);dest=folder/(slug(clip['name'])+'-'+clip['id'][:6]+'.mp4');job['message']='Guardando el fragmento…'
  subprocess.run([FFMPEG,'-v','error','-y','-ss',str(clip['start']),'-i',str(source),'-t',str(clip['end']-clip['start']),'-vf','scale=640:480:force_original_aspect_ratio=decrease','-r','24','-c:v','libx264','-preset','fast','-crf','24','-c:a','aac','-b:a','96k','-movflags','+faststart',str(dest)],check=True,capture_output=True)
  with lock:clip.update(status='ready',file=str(dest.relative_to(DATA)),bytes=dest.stat().st_size);save()
  (dest.with_suffix('.json')).write_text(json.dumps(clip,ensure_ascii=False,indent=2));job['message']='Fragmento guardado en su carpeta.'
 except Exception as e:
  with lock:clip.update(status='error',error='No se pudo descargar. Puedes reintentar; tu selección está guardada.');save()
  raise e
def classify(vid,collection):
 if collection not in ('green','regular'):raise ValueError('Tipo de biblioteca no válido')
 with lock:
  for c in state['candidates']:
   if c['id']==vid:c['collection']=collection
  for c in state['clips']:
   if c['video_id']!=vid:continue
   c['collection']=collection
   if c.get('file'):
    old=DATA/c['file'];folder=DATA/'biblioteca'/('green-screens' if collection=='green' else 'videos-con-fondo')
    for part in c['category'].split('/'):folder/=slug(part)
    folder.mkdir(parents=True,exist_ok=True);dest=folder/old.name
    if old.exists() and old!=dest:old.rename(dest)
    c['file']=str(dest.relative_to(DATA));dest.with_suffix('.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
  save()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,data,status=200):
  raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/api/state':return self.reply(state)
  if path.startswith('/api/jobs/'):return self.reply(jobs.get(path.split('/')[-1],{'status':'error','message':'Trabajo no encontrado.'}))
  if path.startswith('/media/'):
   p=(DATA/path[len('/media/'):]).resolve()
   if not p.is_relative_to(DATA.resolve()) or p.suffix!='.mp4' or not p.exists():return self.reply({},404)
   raw=p.read_bytes();self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(len(raw)));self.end_headers();return self.wfile.write(raw)
  if path not in ('/','/app.js','/style.css'):return self.reply({},404)
  p=ROOT/({'/':'index.html'}.get(path,path[1:]));raw=p.read_bytes();self.send_response(200);self.send_header('Content-Type','text/html' if p.suffix=='.html' else 'text/javascript' if p.suffix=='.js' else 'text/css');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  # No cross-site POSTs to this local filesystem tool.
  if self.headers.get('Origin') not in (None,'http://127.0.0.1:8097','http://localhost:8097'):return self.reply({'error':'Origen no permitido'},403)
  try:
   b=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),50000)))
   if self.path=='/api/classify':
    classify(b['id'],b['collection']);return self.reply({'ok':True})
   if self.path=='/api/search':return self.reply({'job':task(lambda j:search(b,j))})
   if self.path=='/api/link':
    vid=video_id(b['url']);add_candidates([{'id':vid,'title':b.get('name') or 'Vídeo añadido · '+vid}],b.get('category','Memes/Tendencias'),'Enlace propio',b.get('collection','green'));return self.reply({'id':vid})
   if self.path=='/api/reject':
    with lock:
     key=b.get('collection','green')+':'+b['id']
     if key not in state.setdefault('rejections',[]):state['rejections'].append(key)
     save()
    return self.reply({'ok':True})
   if self.path=='/api/restore':
    with lock:state['rejections']=[v for v in state.get('rejections',[]) if v!=b.get('collection','green')+':'+b['id']];save()
    return self.reply({'ok':True})
   if self.path=='/api/accept':
    vid=video_id(b['url']);start=float(b['start']);end=float(b['end'])
    if not (0<=start<end and end-start<=120):raise ValueError('El fragmento debe durar entre 0 y 120 segundos.')
    name=str(b['name']).strip();category=str(b['category']).strip()
    if not name or not category:raise ValueError('Escribe un nombre y una carpeta.')
    clip={'id':uuid.uuid4().hex,'video_id':vid,'url':'https://www.youtube.com/watch?v='+vid,'name':name,'category':category,'start':start,'end':end,'status':'downloading','collection':b.get('collection','green')}
    with lock:
     duplicate=next((c for c in state['clips'] if (c['video_id'],c['start'],c['end'],c.get('collection','green'),c['category'],c['name'])==(vid,start,end,clip['collection'],category,name) and c['status']!='error'),None)
     if duplicate:return self.reply({'clip':duplicate,'duplicate':True})
     state['clips'].append(clip);save()
    return self.reply({'job':task(lambda j:download(clip,j)),'clip':clip})
   if self.path=='/api/retry':
    clip=next(c for c in state['clips'] if c['id']==b['id']);clip['status']='downloading';save();return self.reply({'job':task(lambda j:download(clip,j))})
   return self.reply({},404)
  except Exception as e:return self.reply({'error':str(e)},400)
if __name__=='__main__':
 if not state['candidates']:
  old=Path('/tmp/montara-green-search.json')
  if old.exists():
   cats={'quotes':'Memes/Frases','scenes':'Escenas/Atmósfera','paint':'Pinturas/Trazos','text':'Textos/Animaciones'}
   for group in json.loads(old.read_text()):add_candidates(group['candidates'],cats[group['category']],group['query'])
 print('Selector independiente: http://127.0.0.1:8097/',flush=True);ThreadingHTTPServer(('127.0.0.1',8097),Handler).serve_forever()
