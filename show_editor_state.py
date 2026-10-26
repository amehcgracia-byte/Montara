"""Fast, render-free Show editing state and the existing engine callbacks.

Bind callbacks during API registration rather than calling the expensive review
view (which fingerprints previews and probes artwork) for every small edit.
"""
import copy,json
from urllib.parse import quote
from flask import jsonify,send_file


def bind_editor_callbacks():
    from server import edit_timeline
    if getattr(edit_timeline.register_edit_timeline,'montara_bound',False):return
    original=edit_timeline.register_edit_timeline
    def register(app,project,invalidate):
        app.config['MONTARA_EDITOR_PROJECT']=project
        app.config['MONTARA_EDITOR_INVALIDATE']=invalidate
        return original(app,project,invalidate)
    register.montara_bound=True
    edit_timeline.register_edit_timeline=register


def editor_state(project):
    from core.show import edited_words,scene_segments,edited_captions
    from core import show_caption_layout,show_narrator
    from server.edit_timeline import snapshot
    folder=project.artifacts_dir
    plan=json.loads((folder/'show_plan.json').read_text())
    doc=json.loads((folder/'show_scenes.json').read_text())
    stored=json.loads((folder/'show_proposals.json').read_text())
    words=edited_words(plan);layout=show_caption_layout.load(project)
    cues=show_caption_layout.apply(edited_captions(plan,plan.get('style') or 'choe'),layout) if layout.get('enabled') else []
    for scene in doc['scenes']:
        scene['preview']={'status':'none'}
        scene['segments']=scene_segments(plan,scene['start'],scene['end'])
        scene['words']=[[t,a,b] for t,a,b in words if scene['start']<=a<scene['end']]
        scene['captions']=[cue for cue in cues if cue['start']<scene['end'] and cue['end']>scene['start']]
        scene['references']=[]
    return {**doc,'project_id':str(project.folder),'proposals':stored.get('proposals',[]),'resources':stored.get('resources',[]),
            'source':plan.get('source'),'source_url':'/api/v1/show/source?path='+quote(str(plan.get('source') or '')),
            'plan':{k:plan.get(k) for k in ('style','fps','edited_duration')},'timeline':snapshot(project,'show',plan),
            'narrator':show_narrator.track(plan),'caption_revision':layout.get('revision',0),'captions_enabled':bool(layout.get('enabled')),'caption_defaults':layout.get('defaults',{})}


def register_editor_state(app):
    @app.get('/montara/show/editor')
    def get_editor_state():
        from core.show_proposals import LOCK
        with LOCK:
            project=app.config['MONTARA_EDITOR_PROJECT']()
            try:return jsonify(editor_state(project))
            except (OSError,ValueError,KeyError) as exc:return jsonify(error={'message':str(exc)}),404

    @app.get('/montara/show/editor/audio/<proposal_id>')
    def editor_audio(proposal_id):
        from pathlib import Path
        project=app.config['MONTARA_EDITOR_PROJECT']()
        stored=json.loads((project.artifacts_dir/'show_proposals.json').read_text())
        item=next((p for p in stored['proposals'] if p['id']==proposal_id and p['kind']=='jingle' and p.get('status')!='discarded'),None)
        if not item:return '',404
        path=Path(item['params'].get('path','')).resolve()
        if not path.is_file() or not path.is_relative_to(project.folder.resolve()):return '',404
        return send_file(path,conditional=True)
