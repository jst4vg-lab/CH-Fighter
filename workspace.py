"""Local Command Suite draft and manual handoff state."""
import json
import uuid
import re
from urllib.parse import urlparse

from crea_core import db

TRANSITIONS = {
    'draft': {'prepared'},
    'prepared': {'draft', 'handoff_pending'},
    'handoff_pending': {'sent_confirmed', 'failed_unverified'},
    'failed_unverified': {'draft', 'handoff_pending'},
    'sent_confirmed': set(),
}


def _active(con):
    row = con.execute('select * from workspace_drafts where active=1').fetchone()
    if row is None:
        ident = str(uuid.uuid4())
        con.execute('insert into workspace_drafts(id) values(?)', (ident,))
        row = con.execute('select * from workspace_drafts where id=?', (ident,)).fetchone()
    result = dict(row)
    result['asset_ids'] = json.loads(result.pop('asset_ids_json'))
    return result


def current():
    con = db()
    try:
        with con:
            return _active(con)
    finally:
        con.close()


def history():
    con = db()
    try:
        rows = []
        for row in con.execute('select * from workspace_drafts order by created_at desc, rowid desc limit 50'):
            item = dict(row)
            item['asset_ids'] = json.loads(item.pop('asset_ids_json'))
            rows.append(item)
        return rows
    finally:
        con.close()


def save(text, asset_ids, channel_url='', reply_to_id=''):
    if not isinstance(text, str) or len(text) > 20000:
        raise ValueError('Invalid draft text')
    if not isinstance(asset_ids, list) or len(asset_ids) > 10 or any(not isinstance(x, str) for x in asset_ids) or len(set(asset_ids)) != len(asset_ids):
        raise ValueError('Invalid selected crea')
    parsed = urlparse(channel_url) if isinstance(channel_url, str) else None
    if not isinstance(channel_url, str) or (channel_url and (parsed.scheme != 'https' or parsed.netloc != 'discord.com' or not re.fullmatch(r'/channels/(?:@me|\d+)(?:/\d+)?/?', parsed.path) or parsed.query or parsed.fragment)):
        raise ValueError('Invalid Discord channel URL')
    if not isinstance(reply_to_id,str) or (reply_to_id and not re.fullmatch(r'\d{1,24}',reply_to_id)):
        raise ValueError('Invalid reply message ID')
    con = db()
    try:
        with con:
            draft = _active(con)
            sent=con.execute("select status from workspace_test_sends where draft_id=?",(draft['id'],)).fetchone()
            if sent and sent['status']=='confirmed':
                con.execute('update workspace_drafts set active=0 where id=?',(draft['id'],))
                draft=_active(con)
            elif sent and sent['status'] in ('pending','unverified'):
                raise ValueError('Check the test send outcome before starting another draft')
            if draft['status'] in ('handoff_pending', 'sent_confirmed'):
                raise ValueError('Start a new draft or return this handoff to editing')
            found = {r['id'] for r in con.execute('select id from assets where id in (%s)' % ','.join('?' * len(asset_ids)), asset_ids)} if asset_ids else set()
            if found != set(asset_ids):
                raise ValueError('Selected crea no longer exist')
            status = 'draft' if draft['status'] in ('prepared', 'failed_unverified') else draft['status']
            con.execute("update workspace_drafts set text=?,asset_ids_json=?,channel_url=?,reply_to_id=?,status=?,updated_at=current_timestamp where id=?",
                        (text, json.dumps(asset_ids), channel_url, reply_to_id, status, draft['id']))
            return _active(con)
    finally:
        con.close()


def transition(target, manual_confirmation=False):
    con = db()
    try:
        with con:
            draft = _active(con)
            if target not in TRANSITIONS[draft['status']]:
                raise ValueError('Invalid handoff transition')
            if target == 'prepared' and not (draft['text'].strip() or draft['asset_ids']):
                raise ValueError('Draft is empty')
            if target == 'sent_confirmed' and manual_confirmation is not True:
                raise ValueError('Explicit user confirmation is required')
            con.execute('update workspace_drafts set status=?,updated_at=current_timestamp where id=?', (target, draft['id']))
            return _active(con)
    finally:
        con.close()


def new_draft():
    con = db()
    try:
        with con:
            con.execute('update workspace_drafts set active=0 where active=1')
            return _active(con)
    finally:
        con.close()
