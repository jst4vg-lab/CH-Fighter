"""One-time, non-destructive move of legacy application data."""
import os
import shutil
import sqlite3
import uuid
from pathlib import Path


def migrate(legacy: Path, target: Path) -> None:
    if target.exists() or not (legacy / 'app.sqlite').is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / ('.clan-hub-migration-' + uuid.uuid4().hex)
    try:
        temporary.mkdir()
        for name in ('formatted', 'thumbnails'):
            source = legacy / name
            if source.is_dir():
                shutil.copytree(source, temporary / name)
                if len(list(source.glob('*.jpg'))) != len(list((temporary / name).glob('*.jpg'))):
                    raise RuntimeError(f'Incomplete {name} migration')
        with sqlite3.connect(f'file:{legacy / "app.sqlite"}?mode=ro', uri=True) as source:
            with sqlite3.connect(temporary / 'app.sqlite') as destination:
                source.backup(destination)
                if destination.execute('pragma integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Migrated database failed integrity check')
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
