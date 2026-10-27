"""Text-led framing with optional shared LLM review and an offline fallback.

Uses edited word timings and the engine's public framing API. Source cuts, sound,
effects and hand-aimed framing are retained. A durable audit prevents reapplying
on every visit (including after the user undoes the automatic direction).
"""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from flask import jsonify, request
from preview_api import engine_client

POLICY = 'text-emphasis-v1'


def normal(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


# Deliberately sparse: these are explicit linguistic cues, not semantic AI.
CUES = [
    (r'\b(me di cuenta|lo que no sabia|no me lo esperaba|hasta que|la verdad es|el problema es|lo mas importante|lo que cambio|lo que nadie)\b', 'Revelation or turning point'),
    (r'\b(i realized|i realised|what i didn.t know|i never expected|until suddenly|the problem is|the most important|what changed|the truth is)\b', 'Revelation or turning point'),
    (r'\b(mir wurde klar|plotzlich|das problem ist|das wichtigste|die wahrheit ist|was niemand)\b', 'Revelation or turning point'),
]
QUESTION = re.compile(r'\b(como|por que|cuando|que paso|how|why|what happened|warum|wie)\b')
FILLER = re.compile(r'\b(sabes|entiendes|you know|right|verdad|no se)\b')


def phrases(document):
    words = sorted({(str(w[0]), float(w[1]), float(w[2]))
                    for s in document.get('scenes', []) for w in s.get('words', [])
                    if len(w) >= 3 and float(w[2]) > float(w[1])}, key=lambda w: (w[1], w[2], w[0]))
    groups, group = [], []
    for word in words:
        if group and (word[1]-group[-1][2] > .8 or word[2]-group[0][1] > 9):
            groups.append(group); group = []
        group.append(word)
        if re.search(r'[.!?…]["»”]*$', word[0].strip()):
            groups.append(group); group = []
    if group: groups.append(group)
    return groups


def direction(document, narrator, semantic=None):
    """Return complete, boundary-aligned automatic ranges and explain each emphasis."""
    shots = narrator.get('shots', [])
    candidates = []
    for phrase_id, group in enumerate(phrases(document)):
        quote = ' '.join(w[0].strip() for w in group)
        text = normal(quote)
        if len(group) < 4: continue
        reason = semantic.get(phrase_id) if semantic is not None else next((reason for pattern, reason in CUES if re.search(pattern, text)), None)
        if semantic is None and not reason and '?' in quote and QUESTION.search(text) and not FILLER.search(text):
            reason = 'Specific question'
        if not reason: continue
        # Keep an emphasis as one framing across fast cuts; never crop an unseen object.
        selected = [i for i, s in enumerate(shots) if s['at'] < group[-1][2] and s['at']+s['duration'] > group[0][1]]
        if not selected or any(shots[i].get('aimed') for i in selected): continue
        a = shots[selected[0]]['at']; b = shots[selected[-1]]['at']+shots[selected[-1]]['duration']
        if a < 3 or b-a < 1 or b-a > 10: continue
        if candidates and a-candidates[-1]['end'] < 10: continue
        if len(candidates) >= max(1, int(narrator.get('duration', 0)//25)): break
        candidates.append(dict(start=a, end=round(b, 6), zoom=1.22, quote=quote, reason=reason))
    # Wide rests between selected phrases. Group only equal automatic framing;
    # hand-aimed shots remain byte-for-byte unchanged by this adapter.
    ranges = []
    for s in shots:
        if s.get('aimed'): continue
        emphasis = next((c for c in candidates if c['start'] <= s['at'] < c['end']-.001), None)
        zoom = emphasis['zoom'] if emphasis else 1.0
        start, end = s['at'], round(s['at']+s['duration'], 6)
        if ranges and abs(ranges[-1]['end']-start) < .002 and ranges[-1]['zoom'] == zoom:
            ranges[-1]['end'] = end
        else: ranges.append(dict(start=start, end=end, zoom=zoom))
    return dict(method='llm-reviewed-text' if semantic is not None else 'local-text-rules', policy=POLICY, emphases=candidates, ranges=ranges,
                preserved_manual_shots=sum(bool(s.get('aimed')) for s in shots))


def register_show_direction(app, data_root):
    root = Path(data_root)/'ShowDirection'

    @app.after_request
    def forget_new_generation(response):
        if request.path == '/api/v1/wizard/start' and request.method == 'POST' and response.status_code < 300:
            body = request.get_json(silent=True) or {}
            if body.get('platform') == 'show' and body.get('project_id'):
                for marker in root.glob('*.json'):
                    if json.loads(marker.read_text()).get('project_id') == body['project_id']:
                        marker.unlink(missing_ok=True)
        return response

    @app.post('/montara/show/direction')
    def apply_direction():
        from montara_ai import AIService
        from ai_tasks import GAMER_EMPHASES
        service = app.extensions.get('montara_ai') or AIService(data_root)
        review, semantic, proof = {'status': 'not_configured'}, None, None
        # A network deadline must not hold the edit locks and freeze manual work.
        if service.configured and not app.config.get('MONTARA_EDIT_BUSY', lambda: False)():
            with engine_client(app) as engine:
                probe = engine.get('/api/v1/show/scenes').get_json() or {}
                narrator_probe = engine.get('/api/v1/show/narrator').get_json() or {}
            if probe.get('plan', {}).get('style') in {'fast', 'choe'}:
                proof = phrases(probe)
                evidence = dict(phrases=[dict(id=i, text=' '.join(w[0] for w in group)[:800])
                                        for i, group in enumerate(proof[:300]) if len(group) >= 4],
                                maximum=min(12, max(1, int(narrator_probe.get('duration', 0)//25))))
                review = service.review(GAMER_EMPHASES, evidence)
                if review['status'] == 'reviewed':
                    semantic = {item['id']: item['reason'] for item in review['value']['emphases']}
        from core.show_proposals import LOCK
        from server.edit_timeline import LOCK as CUT_LOCK
        # Block concurrent framing and roll edits while the public API applies
        # the short batch. Source timing is never changed by this adapter.
        with CUT_LOCK, LOCK, engine_client(app) as engine:
            if app.config.get('MONTARA_EDIT_BUSY', lambda: False)():
                return jsonify(applied=False, reason='Analysis is still running.')
            response = engine.get('/api/v1/show/scenes')
            if response.status_code != 200: return response.get_json(), response.status_code
            document = response.get_json()
            if document.get('plan', {}).get('style') not in {'fast', 'choe'}:
                return jsonify(applied=False, reason='This direction is for Gamer only.')
            narrator = engine.get('/api/v1/show/narrator').get_json()
            if semantic is not None and (phrases(document) != proof or probe.get('project_id') != document.get('project_id')):
                semantic, review = None, {'status': 'stale_evidence'}
            project = document['project_id']
            # Source path + transcript differentiate new analyses without treating
            # manual cut/zoom edits as a reason to overwrite the user again.
            identity = [project, document.get('source'), [(s.get('id'), s.get('text')) for s in document.get('scenes', [])]]
            if service.configured:
                identity.append(service.model)
            key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            marker = root/(key+'.json')
            if marker.is_file(): return jsonify(applied=False, **json.loads(marker.read_text()))
            timeline = engine.get('/api/v1/edit/timeline?kind=show').get_json()
            audit = direction(document, narrator, semantic)
            audit['ai_review'] = review
            audit.update(project_id=project, source=document.get('source'), before_revision=timeline['revision'])
            operations = []
            # Skip already correct ranges to avoid needless preview invalidation.
            for span in audit['ranges']:
                chosen = [s for s in narrator['shots'] if span['start'] <= s['at'] < span['end']-.001]
                if any(abs(s['zoom']-span['zoom'])>.0001 or s.get('zoom_end') is not None or s.get('move')=='glide' for s in chosen):
                    operations.append(span)
            revision = timeline['revision']
            done = 0
            for span in operations:
                result = engine.post('/api/v1/show/narrator/framing', json=dict(
                    project_id=project, revision=revision, op='frame', **span, zoom_end=None, move='cut', backup=done==0))
                if result.status_code != 200:
                    # Undo only our own successful operations while still holding
                    # the lock. Retain the original error and permit a retry.
                    for _ in range(done): engine.post('/api/v1/show/narrator/framing', json=dict(project_id=project, op='undo'))
                    return result.get_json(), result.status_code
                done += 1
                revision = engine.get('/api/v1/edit/timeline?kind=show').get_json()['revision']
            audit.update(after_revision=revision, operations=done)
            root.mkdir(parents=True, exist_ok=True)
            temporary = marker.with_suffix('.tmp'); temporary.write_text(json.dumps(audit, ensure_ascii=False, indent=2)); temporary.replace(marker)
            return jsonify(applied=bool(done), **audit)
