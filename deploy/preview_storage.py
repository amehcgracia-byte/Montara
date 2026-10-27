"""Initialize private preview data on the sandbox's large working filesystem.

Old 1 GiB Drives remain intact as migration sources. The complete working
filesystem is persisted by the named sandbox's automatic snapshot on stop.
"""
from pathlib import Path
import shutil


def prepare_storage(root: Path, *, initialize: bool, import_root: Path | None = None) -> None:
    root = Path(root)
    marker = root.parent / '.montara-root-storage-v1'
    if marker.exists():
        return
    if not initialize:
        # Existing snapshot-based previews already keep their data here.
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text('existing snapshot data\n')
        return
    staging = root.parent / '.montara-data-staging'
    if import_root is not None:
        source = Path(import_root)
        if not source.is_dir():
            raise RuntimeError('The saved preview data could not be mounted; migration stopped.')
        shutil.copytree(source, staging, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns('lost+found'))
    else:
        staging.mkdir(parents=True, exist_ok=True)
    # Keep the template's example workspace outside the new visitor's namespace.
    # Never replace the old Drive or discard a visitor's saved files.
    if root.exists():
        backup = root.parent / '.montara-template-data'
        if backup.exists():
            raise RuntimeError('An unfinished storage migration needs review; existing data was kept.')
        root.rename(backup)
    staging.rename(root)
    marker.write_text('private snapshot data\n')
