"""Montara-owned split/ripple-delete adapter for the single-source Show editor.

The upstream engine has roll/framing APIs but no deletion API. Keep its source
untouched; edit its project documents under the same locks, with a recoverable
transaction, storyboard backup and revision-checked undo.
"""
from __future__ import annotations
import copy, hashlib, json, math, uuid, time
from pathlib import Path
from flask import jsonify, request
from preview_api import engine_client

FILES=('show_plan.json','show_scenes.json','show_proposals.json','show_caption_layout.json','show_plan_undo.json')


def digest(doc):
    return hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest()


def read_state(folder):
    return {name:json.loads((folder/name).read_text()) if (folder/name).is_file() else None for name in FILES}


def write_state(folder, state, previous=None):
    from core.project import atomic_write_json
    for name in FILES:
        if previous is not None and state[name]==previous[name]:continue
        if state[name] is None:(folder/name).unlink(missing_ok=True)
        else:atomic_write_json(folder/name,state[name])


def ripple_item(item, a, b, *, overlay=False):
    """Remove intersecting material, retaining media offsets of both surviving sides."""
    start=float(item.get('at',0));duration=float(item.get('duration',0));end=start+duration
    params=item if overlay else item.get('params',{})
    kind=item.get('kind','overlay')
    insert=(kind=='character' or kind=='clip' and params.get('clip_audio') is not False and params.get('matte','none')=='none'
            or overlay and item.get('action')=='talk' and item.get('voice_mode')!='mine')
    shift=lambda t:round(t if t<=a else a if t<b else t-(b-a),6)
    if insert or duration<=0:
        return [] if a<=start<b else [{**copy.deepcopy(item),'at':shift(start)}]
    spans=[(start,min(end,a)),(max(start,b),end)]
    out=[]
    for lo,hi in spans:
        if hi-lo<1e-6:continue
        piece=copy.deepcopy(item);offset=lo-start;piece.update(at=shift(lo),duration=round(hi-lo,6))
        p=piece if overlay else piece.setdefault('params',{})
        if out:
            piece['id']=str(item['id'])+'-cut-'+uuid.uuid4().hex[:8]
            p['group']=params.get('group') or item['id']
        if offset:
            keys={'jingle':('start',),'cutaway':('source_start',),'clip':('clip_start',)}.get(kind,())
            for key in keys:p[key]=round(float(p.get(key,0))+offset*float(p.get('speed',1) if kind=='clip' else 1),6)
        out.append(piece)
    return out


def delete_shot(state, index):
    from core.show import edited_words,edited_captions
    plan=state['show_plan.json'];shots=plan['shots'];fps=int(plan.get('fps') or 30)
    if not 0<=index<len(shots):raise ValueError('Select a shot in this video.')
    if len(shots)==1:raise ValueError('Keep at least one shot in your video.')
    a=sum(s['end_frame']-s['start_frame'] for s in shots[:index])/fps
    b=a+(shots[index]['end_frame']-shots[index]['start_frame'])/fps
    old_cues=edited_captions(plan,plan.get('style') or 'choe')
    shots.pop(index)
    if index<len(shots):
        shots[index]['cut_before']='manual-delete'
        for key in ('move','glide_from','glide_frames','glide_skip'):shots[index].pop(key,None)
    plan['edited_duration']=round(sum(s['end_frame']-s['start_frame'] for s in shots)/fps,6)
    plan['cuts']=len(shots)-1
    shift=lambda t:round(t if t<=a else a if t<b else t-(b-a),6)
    stored=state['show_proposals.json'];mapping={};items=[]
    for item in stored.get('proposals',[]):
        pieces=ripple_item(item,a,b);mapping[item['id']]=[p['id'] for p in pieces];items.extend(pieces)
    stored['proposals']=items
    words=edited_words(plan);scenes=[]
    for scene in state['show_scenes.json']['scenes']:
        old_start,old_end=scene['start'],scene['end'];scene['start'],scene['end']=shift(old_start),shift(old_end)
        if scene['end']-scene['start']<1/fps-1e-6:continue
        scene['text']=' '.join(w for w,x,y in words if scene['start']<=x<scene['end'])
        scene['effects']=[new for old in scene.get('effects',[]) for new in mapping.get(old,[])]
        scene['overlays']=[piece for item in scene.get('overlays',[]) for piece in ripple_item(item,a,b,overlay=True)]
        scenes.append(scene)
    if not scenes:raise ValueError('Keep at least one part of your video.')
    state['show_scenes.json']['scenes']=scenes
    # Remap caption overrides for surviving phrases, including corrected text.
    # Newly regrouped cues inherit a surviving cue's styling by temporal overlap.
    layout=state['show_caption_layout.json']
    if layout:
        key=lambda c:hashlib.sha256(json.dumps([c['lines'],c['start'],c['end']],ensure_ascii=False).encode()).hexdigest()[:20]
        kept=[]
        for cue in old_cues:
            values=layout.get('cues',{}).get(key(cue))
            if not values:continue
            lo,hi=shift(cue['start']),shift(cue['end'])
            if hi>lo:kept.append((lo,hi,values,cue['lines']))
        changes={}
        for cue in edited_captions(plan,plan.get('style') or 'choe'):
            matches=[entry for entry in kept if entry[0]<cue['end'] and entry[1]>cue['start']]
            if not matches:continue
            lo,hi,values,lines=max(matches,key=lambda e:min(e[1],cue['end'])-max(e[0],cue['start']))
            values=copy.deepcopy(values)
            if lines!=cue['lines']:values.pop('text',None) # never reintroduce deleted words
            changes[key(cue)]=values
        layout['cues']=changes;layout['revision']=int(layout.get('revision',0))+1
    # A framing-only undo from before deletion must never resurrect old timing.
    state['show_plan_undo.json']=None
    return a,b


def register_show_cut_edit(app,data_root):
    from core.project import atomic_write_json
    # Recover a transaction interrupted by a worker restart. No media are touched.
    for journal in Path(data_root).glob('Projects/*/artifacts/montara_cut_pending.json'):
        saved=json.loads(journal.read_text());write_state(journal.parent,saved['before']);journal.unlink()

    backed_up=set()

    @app.post('/montara/show/cuts')
    def edit_cuts():
        from core.show_proposals import LOCK
        from server.edit_timeline import LOCK as CUT_LOCK, revision
        from core.project import load_project
        from core.show import keep_storyboard
        from core.show_narrator import _split
        from core.show_review_history import record
        started=time.perf_counter()
        body=request.get_json(silent=True) or {}
        with CUT_LOCK, LOCK:
            if app.config.get('MONTARA_EDIT_BUSY',lambda:False)():return jsonify(error={'message':'Wait for the analysis to finish.'}),409
            project=app.config['MONTARA_EDITOR_PROJECT']()
            if body.get('project_id')!=str(project.folder):return jsonify(error={'message':'Reopen the current project.'}),409
            folder=project.artifacts_dir;before=read_state(folder)
            if before['show_plan.json'].get('style') not in {'fast','choe','normal','calm'}:return jsonify(error={'message':'These source cuts are available in Gamer and Influencer.'}),400
            if body.get('revision')!=revision(before['show_plan.json']):return jsonify(error={'message':'The edit changed. Select the shot again.'}),409
            try:
                op=body.get('op');after=copy.deepcopy(before);operation_id=uuid.uuid4().hex
                undo_folder=folder/'montara_cut_undo';undo_folder.mkdir(exist_ok=True)
                if op=='undo':
                    key=str(body.get('operation_id',''))
                    if not re_id(key):raise ValueError('Choose a saved cut edit to undo.')
                    saved=json.loads((undo_folder/(key+'.json')).read_text())
                    if digest(before)!=saved['after_digest']:return jsonify(error={'message':'Undo your newer edits first.'}),409
                    after=saved['before'];operation_id=None
                elif op=='split':
                    fps=int(after['show_plan.json'].get('fps') or 30);at=float(body['at'])
                    if not math.isfinite(at):raise ValueError('Choose a finite cut time.')
                    frame=round(at*fps);clock=0;found=False
                    for shot in after['show_plan.json']['shots']:
                        end=clock+shot['end_frame']-shot['start_frame']
                        if clock<frame<end:found=True;break
                        clock=end
                    if not found:raise ValueError('Choose a point inside a shot, away from an existing cut.')
                    _split(after['show_plan.json'],frame)
                    after['show_plan.json']['cuts']=len(after['show_plan.json']['shots'])-1
                    after['show_plan_undo.json']=None
                elif op=='delete':
                    raw=body.get('index')
                    if isinstance(raw,bool) or not isinstance(raw,int):raise ValueError('Select a shot to delete.')
                    a,b=delete_shot(after,raw)
                else:raise ValueError('Choose split, delete or undo.')
                if str(project.folder) not in backed_up:
                    keep_storyboard(project,'Before timeline editing')
                    backed_up.add(str(project.folder))
                journal=folder/'montara_cut_pending.json';atomic_write_json(journal,{'before':before})
                try:
                    write_state(folder,after,previous=before)
                    if operation_id:atomic_write_json(undo_folder/(operation_id+'.json'),{'before':before,'after_digest':digest(after)})
                except Exception:
                    write_state(folder,before)
                    journal.unlink(missing_ok=True)
                    raise
                else:journal.unlink(missing_ok=True)
                record(project,'show.cut.'+op,method='editor',evidence={'index':body.get('index'),'at':body.get('at'),'operation_id':operation_id})
                # Bound local undo storage; backups also remain in storyboard history.
                for old in sorted(undo_folder.glob('*.json'),key=lambda p:p.stat().st_mtime)[:-30]:old.unlink()
                app.config['MONTARA_EDITOR_INVALIDATE'](project)
                from show_editor_state import editor_state
                return jsonify(project_id=str(project.folder),revision=revision(after['show_plan.json']),operation_id=operation_id,editor=editor_state(project),
                               processing_ms=round((time.perf_counter()-started)*1000,2),duration=after['show_plan.json']['edited_duration'],removed=(b-a) if op=='delete' else 0)
            except (ValueError,KeyError,TypeError,OSError) as exc:return jsonify(error={'message':str(exc)}),400


def re_id(value):
    return len(value)==32 and all(c in '0123456789abcdef' for c in value)
