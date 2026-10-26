"""Build portable, short Show test kits without changing the originals."""
import argparse,json,subprocess
from pathlib import Path

def build(source, output, talk):
    output.mkdir(parents=True,exist_ok=True)
    def convert(src,relative,length,video=True,width=640):
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
        args=['ffmpeg','-v','error','-y','-nostdin','-i',str(src),'-t',str(length)]
        if video:args+=['-map','0:v:0','-map','0:a:0?','-vf',f'scale={width}:-2,fps=25','-c:v','libx264','-preset','fast','-crf','29','-pix_fmt','yuv420p','-threads','2','-c:a','aac','-b:a','64k','-movflags','+faststart']
        else:args+=['-vn','-c:a','libmp3lame','-b:a','64k','-ar','48000']
        if not target.exists():subprocess.run(args+[str(target)],check=True)
        print(relative,round(target.stat().st_size/1024**2,2),'MB',flush=True)
        return str(relative)
    convert(source/'gamer/como-logre-salir-de-cuba.mp4','fast/video.mp4',60)
    convert(talk,'normal/video.mp4',60)
    convert(source/'relato/masacre-de-flores.mp4','storytelling/video.mp4',60)
    convert(source/'storytelling-reference/masacre-de-flores-narration.mp3','storytelling/narration.mp3',60,False)
    kit=json.loads((source/'storytelling-reference/kit.json').read_text());clips=[]
    for clip in kit['clips']:
        if clip['from']>=60:continue
        duration=min(60,clip['to'])-clip['from']
        convert(source/'storytelling-reference/clips'/clip['file'],'storytelling/clips/'+clip['file'],duration)
        clips.append({**clip,'file':'clips/'+clip['file'],'to':min(60,clip['to'])})
    (output/'storytelling/kit.json').write_text(json.dumps({'source':'video.mp4','narration':'narration.mp3','duration':60,'clips':clips},indent=2))
    convert(source/'podcast-360/roundtable-360.mp4','podcast/roundtable-360.mp4',90,width=960)
    setup=json.loads((source/'podcast-reference/setup.json').read_text())
    for i in range(1,4):convert(source/f'podcast-reference/camera-{i}.mp4',f'podcast/camera-{i}.mp4',90)
    for i in range(1,6):convert(source/f'podcast-reference/mic-{i}.mp3',f'podcast/mic-{i}.mp3',90,False)
    for person in setup['people']:person['mic']=Path(person['mic']).name
    for camera in setup['cameras']:camera['path']=Path(camera['path']).name
    setup.pop('speaking_share',None)
    setup.update(source='roundtable-360.mp4',duration=90,start=0)
    (output/'podcast/setup.json').write_text(json.dumps(setup,indent=2))
    guides={
      'fast':('Gamer','video.mp4',60,'Vídeo con voz para comprobar cortes rápidos, zooms y efectos. Selecciona Gamer y pulsa Make my edit. Compara los cortes con Influencer utilizando este mismo ejemplo.'),
      'normal':('Influencer','video.mp4',60,'Vídeo con voz para comprobar cortes más largos y naturales. Selecciona Influencer y pulsa Make my edit. También puedes compararlo con Gamer.'),
      'storytelling':('Story','video.mp4',60,'Incluye el primer minuto del relato, narration.mp3 y sus clips asociados en kit.json. En Montara puedes probar ahora el vídeo y sus efectos. La construcción automática del relato a partir de narración y recursos de la 2.6.20 sigue pendiente de adaptar. El vídeo de referencia ya contiene edición; úsalo para contrastar, no como toma virgen.'),
      'podcast':('Podcast','camera-1.mp4',90,'Incluye una cámara 360, tres cámaras normales y cinco pistas de micrófono. Todos abarcan 0–90 s de la misma fuente: no desplaces una pista por separado. setup.json conserva nombres, asientos y asociaciones de cámaras con rutas relativas. Los micrófonos de referencia proceden del material de prueba existente; no sustituyen una prueba futura con cinco grabaciones físicas independientes. En Montara puedes probar ahora camera-1.mp4 como vídeo único. La sincronización multicámara y el cambio automático de hablante de la 2.6.20 siguen pendientes de adaptar.')
    }
    manifest={}
    for key,(title,video,duration,guide) in guides.items():
        folder=output/key
        text=f'# {title}\n\nDuración: {duration} segundos. Vídeos ligeros para pruebas.\n\n{guide}\n\nLos originales no se han modificado. Kit local de evaluación; los ejemplos comerciales se prepararán por separado.\n'
        (folder/'GUIA.md').write_text(text)
        manifest[key]={'id':key,'title':title,'video':key+'/'+video,'duration':duration,'bytes':sum(f.stat().st_size for f in folder.rglob('*') if f.is_file()),'guide':guide}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('DONE total media MB',round(sum(i['bytes'] for i in manifest.values())/1024**2,1),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--talk',type=Path,required=True);a=p.parse_args();build(a.source,a.output,a.talk)
