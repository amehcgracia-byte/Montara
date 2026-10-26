"""Portable Show examples and companion guides; no engine internals."""
import io,json,zipfile
from pathlib import Path
from preview_api import engine_client
from flask import jsonify,send_file,send_from_directory,request


def show_examples(root):
    path=Path(root)/'show/manifest.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def show_inputs(fixtures, key):
    """Expose the separate rehearsal inputs, before any processing starts."""
    root=Path(fixtures)/'show'/key
    if key=='podcast':
        setup=json.loads((root/'setup.json').read_text())
        for person in setup['people']:person['mic']=str(root/person['mic'])
        for camera in setup['cameras']:
            camera['name']=Path(camera['path']).name
            camera['path']=str(root/camera['path'])
        return {'podcast':{'people':setup['people'],'cameras':setup['cameras']}}
    if key=='storytelling':
        kit=json.loads((root/'kit.json').read_text())
        def item(name):return {'path':str(root/name),'name':Path(name).name}
        return {'story':{'narration':item(kit['narration']),'clips':[item(c['file']) for c in kit['clips']]}}
    return {}


def register_show_samples(app, fixtures, enabled, data_root=None):
    root=Path(fixtures)/'show'
    @app.get('/montara/show/input')
    def show_input_media():
        path=Path(request.args.get('path','')).resolve()
        roots=[Path(fixtures).resolve()]+([Path(data_root).resolve()] if data_root else [])
        if not path.is_file() or not any(path.is_relative_to(base) for base in roots) or path.suffix.lower() not in {'.mp4','.mov','.mkv','.webm','.m4v','.mp3','.wav','.m4a','.flac','.ogg','.png','.jpg','.jpeg','.webp'}:return '',404
        return send_file(path,conditional=True)
    @app.get('/montara/show/examples')
    def show_example_catalog():
        return jsonify(items=[{**item,'preview_url':f'/montara/show/examples/{key}/files/'+item['video'].split('/',1)[1],'guide_url':f'/montara/show/examples/{key}/guide','kit_url':f'/montara/show/examples/{key}/kit'} for key,item in show_examples(fixtures).items()] if enabled else [])

    def known(key):return enabled and key in show_examples(fixtures)

    @app.get('/montara/show/examples/<key>/files/<path:filename>')
    def show_example_media(key,filename):
        if not known(key):return '',404
        return send_from_directory(root/key,filename,conditional=True)

    @app.get('/montara/show/examples/<key>/guide')
    def show_example_guide(key):
        if not known(key):return '',404
        return send_from_directory(root/key,'GUIA.md',mimetype='text/plain; charset=utf-8')

    @app.get('/montara/show/examples/<key>/kit')
    def show_example_kit(key):
        if not known(key):return '',404
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w',zipfile.ZIP_STORED) as archive:
            for file in sorted((root/key).rglob('*')):
                if file.is_file():archive.write(file,file.relative_to(root/key))
        content.seek(0)
        return send_file(content,mimetype='application/zip',as_attachment=True,download_name=f'Montara-{key}-prueba.zip')

    @app.post('/montara/show/examples/<key>/prepare')
    def show_example_prepare(key):
        if not known(key) or key not in ('podcast','storytelling'):return jsonify(error={'message':'Choose a Podcast or Story example'}),400
        body=request.get_json(silent=True) or {}
        with engine_client(app) as engine:
            status=engine.get('/api/v1/wizard/status').get_json()
            if body.get('project_id')!=status.get('project_path'):return jsonify(error={'message':'Reopen this video before loading its example kit'}),409
            if key=='podcast':
                setup=json.loads((root/key/'setup.json').read_text())
                for person in setup['people']:person['mic']=str(root/key/person['mic'])
                for camera in setup['cameras']:camera['path']=str(root/key/camera['path'])
                setup.update(render_width=640,render_height=360)
                response=engine.put('/api/v1/show/podcast',json=setup)
            else:
                kit=json.loads((root/key/'kit.json').read_text());plan=json.loads((root/key/'review-plan.json').read_text())
                for item in plan['catalogue']:item['path']=str(root/key/item['path'])
                for moment in plan['moments']:
                    for picture in moment['pictures']:picture['path']=str(root/key/picture['path'])
                response=engine.put('/api/v1/show/story',json={'narration':str(root/key/kit['narration']),'clips':[str(root/key/c['file']) for c in kit['clips']],'manual_plan':plan})
            return response.get_json(),response.status_code
