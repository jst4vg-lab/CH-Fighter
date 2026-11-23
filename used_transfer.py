"""Portable Used Crea lists containing only library-relative identity."""
from contextlib import closing
from pathlib import PurePosixPath
import re

from crea_core import db
from staging import mark_used, require_composer_idle


def export_used():
    with closing(db()) as con:
        assets = [dict(row) for row in con.execute(
            'select relpath, sha256 from assets where used=1 order by relpath')]
    return {'version': 1, 'assets': assets}


def import_used(document):
    if (not isinstance(document, dict) or type(document.get('version')) is not int
            or document['version'] != 1 or not isinstance(document.get('assets'), list)):
        raise ValueError('Expected a version 1 Used Crea list')
    entries = set()
    for asset in document['assets']:
        if not isinstance(asset, dict):
            raise ValueError('Invalid Used Crea entry')
        path, digest = asset.get('relpath'), asset.get('sha256')
        if (not isinstance(path, str) or not path or '\0' in path
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Invalid Used Crea path or SHA-256')
        entries.add((path, digest))

    with closing(db()) as con, con:
        con.execute('begin immediate')
        require_composer_idle(con)
        matched = {}
        missing, ambiguous = [], []
        for path, digest in sorted(entries):
            candidates = con.execute(
                'select id as asset_id, branch, type, bp, used, relpath from assets where sha256=?',
                (digest,)).fetchall()
            exact = next((row for row in candidates if row['relpath'] == path), None)
            if exact is not None or len(candidates) == 1:
                row = exact if exact is not None else candidates[0]
                matched[row['asset_id']] = row
            else:
                (ambiguous if candidates else missing).append(path)
        newly_used = [row for row in matched.values() if not row['used']]
        mark_used(con, newly_used)
        con.executemany('''delete from package_items where asset_id=? and package_id in
                          (select id from packages where location='hot')''',
                        [(row['asset_id'],) for row in newly_used])
        return {'marked': len(newly_used), 'unchanged': len(matched)-len(newly_used),
                'missing': missing, 'ambiguous': ambiguous}
