"""Single active, host-side Crea source preference."""
from pathlib import Path
from crea_core import db, source_path, scan

def status():
    path=source_path()
    con=db()
    try: count=con.execute('select count(*) from assets').fetchone()[0]
    finally: con.close()
    return {'path':str(path),'available':path.is_dir() and not path.is_symlink(), 'indexed_count':count}

def validate(value):
    if not isinstance(value,str) or not value or '\0' in value:
        raise ValueError('Enter an absolute library directory')
    path=Path(value)
    if not path.is_absolute(): raise ValueError('Enter an absolute library directory')
    try:path=path.resolve(strict=True)
    except OSError as exc:raise ValueError(f'Library directory is not accessible: {exc}') from exc
    if not path.is_dir(): raise ValueError('Library path is not a directory')
    try: next(path.iterdir(),None)
    except OSError as exc: raise ValueError(f'Library directory is not readable: {exc}') from exc
    return path

def apply(value):
    path=validate(value)
    con=db()
    try:
        with con:
            con.execute("update app_settings set value=? where key='library_source'",(str(path),))
    finally: con.close()
    return status()

def rescan():
    result=scan()
    return {**result,**status()}
