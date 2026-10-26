"""Bundled, small green-screen clips. Never download an online link on selection."""
import json
from pathlib import Path
from flask import jsonify,request,send_from_directory
from preview_api import engine_client

CATEGORIES=[{'id':'quotes','name':'Quotes'},{'id':'scenes','name':'Escenas'},{'id':'paint','name':'Pinturas'},{'id':'text','name':'Textos'}]

def register_green_library(app,fixtures):
    root=Path(fixtures)/'greenscreens'
    def catalogue():
        try:return json.loads((root/'catalog.json').read_text())
        except (OSError,ValueError):return {'items':[],'pending':[]}
    def media_path(item):
        p=(root/item.get('file','')).resolve()
        return p if p.is_relative_to(root.resolve()) and p.is_file() else None
    def find(key):
        return next((i for i in catalogue()['items'] if i['id']==key),None)
    @app.get('/montara/greenscreens')
    def green_catalog():
        data=catalogue();items=[]
        for item in data['items']:
            if media_path(item):
                items.append({k:v for k,v in item.items() if k!='file'}|{'thumbnail':f"/montara/greenscreens/{item['id']}/thumbnail"})
        return jsonify(categories=CATEGORIES,items=items,pending=data.get('pending',[]),bytes=sum(i.get('bytes',0) for i in items))
    @app.get('/montara/greenscreens/<key>/thumbnail')
    def green_thumbnail(key):
        if not find(key):return '',404
        return send_from_directory(root,key+'.jpg',mimetype='image/jpeg')
    @app.post('/montara/greenscreens/<key>/use')
    def green_use(key):
        item=find(key)
        if not item or not media_path(item):return jsonify(error={'message':'This clip is not available.'}),404
        with engine_client(app) as engine:
            response=engine.post('/api/v1/show/library/media',json={'path':str(media_path(item)),'project_id':(request.get_json(silent=True) or {}).get('project_id')})
            if response.status_code!=201:return response.get_json(),response.status_code
            asset=response.get_json()['asset'];asset.update(name=item['name'],saved_duration=item['duration'],matte=item.get('matte','green'),default_audio=item['category']=='quotes',curated_id=key,curated_category=item['category'],source_url=item['source_url'])
            return jsonify(asset=asset)
