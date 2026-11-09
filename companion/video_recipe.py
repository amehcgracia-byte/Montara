"""Strict data-only plan accepted by the local original-quality renderer."""
import math,re


def bounded(value,low,high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Invalid video timing or adjustment')
    return float(value)


def geometry(value,depth=0):
    if depth>5:raise ValueError('Video geometry is too deeply nested')
    if isinstance(value,bool) or value is None:return value
    if isinstance(value,(int,float)):return bounded(value,-1000000,1000000)
    if isinstance(value,str):
        if len(value)>150 or any(c in value for c in ('/','\\',';',':','[',']','\n','\x00')):raise ValueError('Invalid camera geometry text')
        return value
    if isinstance(value,list):
        if len(value)>2000:raise ValueError('Camera movement is too long')
        return [geometry(v,depth+1) for v in value]
    if isinstance(value,dict):
        if len(value)>100 or any(not isinstance(k,str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]{0,60}',k) or any(word in k.lower() for word in ('path','file','filter','command','script','url')) for k in value):raise ValueError('Invalid camera geometry fields')
        return {k:geometry(v,depth+1) for k,v in value.items()}
    raise ValueError('Invalid camera geometry')


def controls(name,value):
    value=geometry(value)
    if value is None:return None
    if name in ('motion','flat_framing','spherical_shot','video_light','reel_framing') and value is not None and not isinstance(value,dict):
        raise ValueError('Invalid camera controls')
    if name=='flat_framing' and value:
        if set(value)-{'zoom','x','y'}:raise ValueError('Unknown crop control')
        for k,lo,hi,default in [('zoom',1,6,1),('x',0,1,.5),('y',0,1,.5)]:bounded(value.get(k,default),lo,hi)
    if name=='video_light' and value is not None:
        if set(value)-{'auto','light','shadows'} or not isinstance(value.get('auto',True),bool):raise ValueError('Invalid light controls')
        for k in ('light','shadows'):bounded(value.get(k,0),-1,1)
    # The engine renders into fixed dimensions; keep authored angles and zooms
    # finite and within physical limits before passing any geometry to it.
    def check(v):
        if isinstance(v,dict):
            for k,item in v.items():
                if isinstance(item,(int,float)) and not isinstance(item,bool):
                    if k in ('fov','insv_fov'):bounded(item,1,360)
                    elif k in ('zoom','zoom_start','zoom_end'):bounded(item,1,6 if name=='flat_framing' else 3)
                    elif k in ('yaw','pitch','roll'):bounded(item,-360,360)
                    elif k in ('width','height','w','h'):raise ValueError('Output dimensions are fixed')
                check(item)
        elif isinstance(v,list):
            for item in v:check(item)
    check(value)
    if name=='insv_fov':bounded(value,1,360)
    return value


def validate(recipe):
    if not isinstance(recipe,dict) or recipe.get('version')!=1 or recipe.get('platform')!='youtube':raise ValueError('Choose a Stage edit')
    if not isinstance(recipe.get('engine'),str) or not re.fullmatch('[a-f0-9]{40}',recipe['engine']):raise ValueError('Unknown editor version')
    sources=recipe.get('sources');segments=recipe.get('segments')
    if not isinstance(sources,list) or not 0<=len(sources)<=200 or not isinstance(segments,list) or not 1<=len(segments)<=2000:raise ValueError('Invalid video plan size')
    keys=[]
    for source in sources:
        key=source.get('key') if isinstance(source,dict) else None
        if isinstance(key,bool) or not isinstance(key,int) or key<0 or key in keys:raise ValueError('Invalid source identity')
        keys.append(key)
    result=[];total=0
    for s in segments:
        if not isinstance(s,dict):raise ValueError('Invalid video segment')
        placeholder=s.get('placeholder')
        if placeholder is not None:
            if placeholder!='black' or set(s)-{'placeholder','master_start_sec','duration_sec','clip_start_sec','playback_speed'} or s.get('clip_start_sec',0)!=0 or s.get('playback_speed',1)!=1:
                raise ValueError('Invalid neutral interval')
            result.append({'placeholder':'black','master_start_sec':bounded(s.get('master_start_sec'),0,86400),
                           'duration_sec':bounded(s.get('duration_sec'),1/60,21600),'clip_start_sec':0,'playback_speed':1})
            total+=result[-1]['duration_sec']
            continue
        if isinstance(s.get('source'),bool) or s.get('source') not in keys:raise ValueError('Unknown video source')
        item={'source':s['source'],'clip_start_sec':bounded(s.get('clip_start_sec',0),0,86400),'duration_sec':bounded(s.get('duration_sec'),1/60,21600),'master_start_sec':bounded(s.get('master_start_sec'),0,86400),'playback_speed':bounded(s.get('playback_speed',1.0),0.5,2.0)}
        for k in ('spherical_shot','motion','motion_enabled','flat_framing','video_light','projection','manual_view','insv_fov','reel_framing'):
            if k in s:
                if k=='motion_enabled' and not isinstance(s[k],bool):raise ValueError('Movement must be enabled or disabled')
                item[k]=controls(k,s[k])
        result.append(item);total+=item['duration_sec']
    if total>21600:raise ValueError('The edit is longer than six hours')
    diagnostics=recipe.get('diagnostics',[])
    if not isinstance(diagnostics,list) or len(diagnostics)>2000:raise ValueError('Invalid export diagnostics')
    clean=[]
    for row in diagnostics:
        if not isinstance(row,dict) or row.get('status')!='omitted':raise ValueError('Unresolved source diagnostic')
        if any(isinstance(row.get(k),bool) or not isinstance(row.get(k),int) for k in ('shot','source')):raise ValueError('Invalid omission identity')
        if not 1<=row['shot']<=len(result):raise ValueError('Invalid omission shot')
        segment=result[row['shot']-1]
        if row.get('placeholder')=='black':
            if 'replacement' not in row or row['replacement'] is not None or segment.get('placeholder')!='black':raise ValueError('Omission does not match the neutral interval')
        elif isinstance(row.get('replacement'),bool) or not isinstance(row.get('replacement'),int) or segment.get('source')!=row['replacement']:
            raise ValueError('Omission does not match the rendered shot')
        entry={k:row[k] for k in ('shot','source','replacement','status')}
        if row.get('placeholder')=='black':entry['placeholder']='black'
        if 'name' in row:
            if not isinstance(row['name'],str) or len(row['name'])>200:raise ValueError('Invalid diagnostic clip name')
            entry['name']=row['name']
        clean.append(entry)
    return {'version':1,'engine':recipe['engine'],'platform':'youtube','sources':[{'key':k} for k in keys],'segments':result,'diagnostics':clean}
