from pathlib import Path
import pytest
from deploy.preview_storage import prepare_storage


def test_migration_preserves_source_and_original_project_paths(tmp_path):
    saved=tmp_path/'saved'; project=saved/'Projects'/'Test.zuckervid'
    project.mkdir(parents=True); (project/'project.json').write_text('{"keep":"all edits"}')
    (saved/'original.mp4').write_bytes(b'original video')
    (saved/'lost+found').mkdir(); (saved/'lost+found'/'metadata').write_text('filesystem')
    root=tmp_path/'worker'/'data'; root.mkdir(parents=True)
    (root/'template-project').write_text('not this visitor')
    prepare_storage(root,initialize=True,import_root=saved)
    assert (root/'Projects'/'Test.zuckervid'/'project.json').read_bytes()==(project/'project.json').read_bytes()
    assert (root/'original.mp4').read_bytes()==(saved/'original.mp4').read_bytes()
    assert not (root/'template-project').exists()
    assert (root.parent/'.montara-template-data'/'template-project').is_file()
    assert not (root/'lost+found').exists()
    (root/'new-edit').write_text('later work')
    prepare_storage(root,initialize=True,import_root=saved)
    assert (root/'new-edit').read_text()=='later work'


def test_new_visitor_and_existing_snapshot_are_separate(tmp_path):
    fresh=tmp_path/'fresh'/'data';fresh.mkdir(parents=True);(fresh/'old-template').write_text('old')
    prepare_storage(fresh,initialize=True)
    assert list(fresh.iterdir())==[]
    existing=tmp_path/'existing'/'data';existing.mkdir(parents=True);(existing/'project').write_text('mine')
    prepare_storage(existing,initialize=False)
    assert (existing/'project').read_text()=='mine'


def test_failed_copy_does_not_move_existing_data(tmp_path,monkeypatch):
    root=tmp_path/'data';root.mkdir();(root/'keep').write_text('keep')
    with pytest.raises(RuntimeError):prepare_storage(root,initialize=True,import_root=tmp_path/'missing')
    def failed(*a,**kw):raise OSError('copy failed')
    monkeypatch.setattr('deploy.preview_storage.shutil.copytree',failed)
    with pytest.raises(OSError):prepare_storage(root,initialize=True,import_root=tmp_path)
    assert (root/'keep').read_text()=='keep'
    assert not (tmp_path/'.montara-root-storage-v1').exists()
