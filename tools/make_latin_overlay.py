from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,math
root=Path(__file__).resolve().parents[1]/'tests/fixtures/greenscreens';root.mkdir(exist_ok=True)
font='/System/Library/Fonts/Supplemental/Times New Roman.ttf'
phrases=[('CARPE DIEM',30,40,34),('tempus fugit',310,80,28),('Cogito ergo sum',70,145,31),('PER ASPERA AD ASTRA',240,210,28),('Alea iacta est',70,290,30),('memento mori',385,315,24)]
file=root/'text-latin.mp4';cmd=['/usr/local/bin/ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','640x360','-r','24','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(file)]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
for n in range(72):
 im=Image.new('RGB',(640,360),(0,255,0));d=ImageDraw.Draw(im)
 for j,(text,x,y,size) in enumerate(phrases):
  count=max(0,min(len(text),int((n-j*3)/1.3)))
  if count:d.text((x,y+int(math.sin(n/18+j)*4)),text[:count],font=ImageFont.truetype(font,size),fill=(255,246,222),stroke_width=0)
 p.stdin.write(im.tobytes())
p.stdin.close();assert p.wait()==0
subprocess.run(['/usr/local/bin/ffmpeg','-v','error','-y','-ss','1.8','-i',str(file),'-frames:v','1','-vf','scale=240:-2',str(root/'text-latin.jpg')],check=True)
catalog=root/'catalog.json';d=json.loads(catalog.read_text());d['items']=[i for i in d['items'] if i['id']!='text-latin'];d['items'].append(dict(id='text-latin',category='text',name='Latin words · Carpe diem',file=file.name,duration=3,bytes=file.stat().st_size,matte='green',source_url='montara:original/latin-words',source_title='Original animated Latin typography for Montara',creator='Montara',license='Montara original',source_start=0,source_end=3));catalog.write_text(json.dumps(d,ensure_ascii=False,indent=2));print(file.stat().st_size)
