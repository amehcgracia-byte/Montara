"""Reasoning contracts shared by music sessions and Show.

The model selects from bounded evidence. It cannot invent file paths, execute
code, change hand edits or introduce arbitrary timeline coordinates.
"""
from montara_ai import Task


def bounded_text(value, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Invalid explanation')
    return value.strip()


def validate_boundaries(value, evidence):
    if not isinstance(value, dict) or set(value) != {'cuts', 'summary'} or not isinstance(value['cuts'], list):
        raise ValueError('Invalid boundary review')
    expected = {cut['id'] for cut in evidence['cuts']}
    seen, cuts = set(), []
    for cut in value['cuts']:
        if not isinstance(cut, dict) or set(cut) != {'id', 'decision', 'reason'}:
            raise ValueError('Invalid cut')
        identity = cut['id']
        if isinstance(identity, bool) or not isinstance(identity, int) or identity not in expected or identity in seen:
            raise ValueError('Unknown boundary')
        if cut['decision'] not in {'plausible', 'review'}:
            raise ValueError('Invalid boundary decision')
        seen.add(identity)
        cuts.append(dict(id=identity, decision=cut['decision'], reason=bounded_text(cut['reason'], 250)))
    if seen != expected:
        raise ValueError('Incomplete boundary review')
    return dict(cuts=cuts, summary=bounded_text(value['summary']))


SESSION_BOUNDARIES = Task('session.boundaries.review', '1',
    'Review proposed music-song boundaries using ONLY the supplied acoustic evidence. '
    'You have not heard the recording. A pause can be inside a song. Mark uncertain cuts review. '
    'Do not invent titles, lyrics, instruments or new timestamps. '
    'Return {"cuts":[{"id":integer,"decision":"plausible" or "review","reason":string}],"summary":string}. '
    'Include every supplied cut exactly once. Keep explanations short.', validate_boundaries)


def validate_emphases(value, evidence):
    if not isinstance(value, dict) or set(value) != {'emphases'} or not isinstance(value['emphases'], list):
        raise ValueError('Invalid text emphasis plan')
    expected = {phrase['id'] for phrase in evidence['phrases']}
    if len(value['emphases']) > evidence['maximum']:
        raise ValueError('Too many emphases')
    result, seen = [], set()
    for item in value['emphases']:
        if not isinstance(item, dict) or set(item) != {'id', 'reason'}:
            raise ValueError('Invalid emphasis')
        identity = item['id']
        if isinstance(identity, bool) or not isinstance(identity, int) or identity not in expected or identity in seen:
            raise ValueError('Unknown phrase')
        seen.add(identity)
        result.append(dict(id=identity, reason=bounded_text(item['reason'], 250)))
    return dict(emphases=result)


GAMER_EMPHASES = Task('show.gamer.emphases', '1',
    'Choose sparse punch-ins for significant revelations, punchlines or important points in this transcript. '
    'Avoid filler, repeated mechanical zooms and ordinary sentences. An empty list is valid. '
    'Select only supplied phrase IDs, at most maximum. Do not invent visual subjects. '
    'Return {"emphases":[{"id":integer,"reason":string}]}.', validate_emphases)
