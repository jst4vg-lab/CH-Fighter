"""Shared branch and type ordering preferences."""
from contextlib import closing
import json

from crea_core import BRANCHES, TYPES, db


def _merge(order, known):
    return list(dict.fromkeys([key for key in order if key in known] + list(known)))


def read(con):
    row = con.execute("select value from app_settings where key='gallery_order'").fetchone()
    order = json.loads(row['value']) if row else {}
    types = {branch: [] for branch in BRANCHES}
    for item in con.execute('select distinct branch,type from assets where type is not null order by type'):
        if item['branch'] in types and item['type'] in TYPES:
            types[item['branch']].append(item['type'])
    saved_types = order.get('types', {})
    return {'branches': _merge(order.get('branches', []), BRANCHES),
            'types': {branch: _merge(saved_types.get(branch, []),
                                     sorted(set(found) | set(saved_types.get(branch, []))))
                      for branch, found in types.items()}}


def save(body):
    branches, types = body.get('branches', []), body.get('types', {})
    def valid(values, known):
        return (isinstance(values, list) and all(isinstance(key, str) and key in known for key in values)
                and len(set(values)) == len(values))
    if (not valid(branches, BRANCHES) or not isinstance(types, dict) or
            any(branch not in BRANCHES or not valid(values, TYPES) for branch, values in types.items())):
        raise ValueError('Invalid gallery order')
    with closing(db()) as con, con:
        con.execute("insert or replace into app_settings(key,value) values('gallery_order',?)",
                    (json.dumps({'branches': branches, 'types': types}),))
        return read(con)
