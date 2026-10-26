"""Exercise real trimming and disk persistence in disposable storage."""
import tempfile,json,subprocess
from pathlib import Path
import server
with tempfile.TemporaryDirectory() as tmp:
 server.DATA=Path(tmp);server.DB=Path(tmp)/'selection.json';server.state={'candidates':[],'clips':[],'rejected':[]}
 cache=server.DATA/'fuentes';cache.mkdir()
 source=(Path(__file__).resolve().parents[2]/'tests/fixtures/greenscreens/quotes-just-do-it.mp4')
 (cache/'PcdHp_tLUmA.mp4').symlink_to(source)
 for start,end,name,category in [(0,1,'Primer gesto','Memes/Tendencias'),(1,2,'Segundo gesto','Pinturas/Trazos')]:
  clip={'id':name[:6],'video_id':'PcdHp_tLUmA','name':name,'category':category,'start':start,'end':end,'status':'downloading'}
  server.state['clips'].append(clip);job={};server.download(clip,job)
  assert clip['status']=='ready' and (server.DATA/clip['file']).is_file()
  info=json.loads(subprocess.check_output([(__import__('shutil').which('ffprobe') or '/usr/local/bin/ffprobe'),'-v','quiet','-show_format','-of','json',str(server.DATA/clip['file'])]));assert .95<float(info['format']['duration'])<1.2
 assert len(json.loads(server.DB.read_text())['clips'])==2
 assert server.video_id('https://youtu.be/PcdHp_tLUmA')=='PcdHp_tLUmA'
 try:server.video_id('https://example.com/not-youtube');raise AssertionError('bad URL accepted')
 except ValueError:pass
 print('PASS: two independent cuts, named folders, MP4 durations, saved decisions, URL validation')
# Exercise the actual HTTP actions without touching the user's selection file.
import threading,urllib.request
with tempfile.TemporaryDirectory() as tmp:
 server.DATA=Path(tmp);server.DB=Path(tmp)/'selection.json';server.state={'candidates':[{'id':'PcdHp_tLUmA','title':'test','category':'Memes/Tendencias','collection':'green'}],'clips':[],'rejected':[],'rejections':[]}
 folder=server.DATA/'biblioteca/green-screens/memes/tendencias';folder.mkdir(parents=True);media=folder/'test.mp4';media.write_bytes(b'test')
 clip={'id':'testclip','video_id':'PcdHp_tLUmA','url':'https://youtu.be/PcdHp_tLUmA','name':'Test','category':'Memes/Tendencias','collection':'green','start':0.,'end':1.,'status':'ready','file':str(media.relative_to(server.DATA))}
 server.state['clips'].append(clip)
 http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
 def post(path,data):
  req=urllib.request.Request('http://127.0.0.1:'+str(http.server_address[1])+'/api/'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'});return json.load(urllib.request.urlopen(req))
 try:
  result=post('accept',{'url':clip['url'],'name':'Test','category':clip['category'],'collection':'green','start':0,'end':1});assert result['duplicate'] and len(server.state['clips'])==1
  post('reject',{'id':clip['video_id'],'collection':'green'});assert server.state['rejections']==['green:PcdHp_tLUmA']
  post('restore',{'id':clip['video_id'],'collection':'green'});assert not server.state['rejections']
  post('classify',{'id':clip['video_id'],'collection':'regular'});assert '/videos-con-fondo/' in clip['file'] and (server.DATA/clip['file']).exists()
  assert server.state['candidates'][0]['collection']=='regular'
  assert len(json.loads(server.DB.read_text())['clips'])==1
  print('PASS: HTTP yes deduplicated, no reversible, collections and physical folders separated')
 finally:http.shutdown();http.server_close()
