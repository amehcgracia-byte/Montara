"""Regression for black Matrix backgrounds and soft weather plates."""
import json
from pathlib import Path
import numpy as np
import pytest

def test_catalogue_uses_correct_background_modes():
    data=json.loads((Path(__file__).parents[1]/'tests/fixtures/greenscreens/catalog.json').read_text())
    items={x['id']:x for x in data['items']}
    assert items['text-matrix']['matte']=='black'
    assert items['text-countdown']['matte']=='black'
    assert all(items[k]['matte']=='green-light' for k in ('scenes-rain','scenes-snow'))

def test_matrix_render_keeps_letters_and_removes_dark_background():
    import sys
    sys.path.append(str(Path(__file__).parents[1]/"engine"))
    from core.show_video_assets import VideoLayer
    path=Path(__file__).parents[1]/'tests/fixtures/greenscreens/text-matrix.mp4'
    layer=VideoLayer({'video_layer':str(path),'at':0,'duration':3,'matte':'black'},320,180,24)
    try:
        background=np.full((180,320,3),[70,50,90],dtype=np.uint8)
        raw=layer.video.at(1).astype(np.uint8)
        actual=background.copy();layer.apply(actual,1)
        dark=raw.max(axis=2)<8
        green=(raw[:,:,1]>110)&(raw[:,:,1]>raw[:,:,0]*1.5)
        assert dark.sum()>100 and green.sum()>100
        assert np.abs(actual[dark].astype(float)-background[dark]).mean()<4
        assert actual[:,:,1][green].mean()>background[:,:,1][green].mean()+50
    finally:layer.close()
