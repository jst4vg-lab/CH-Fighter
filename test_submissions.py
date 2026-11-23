"""Persist Discord acknowledgments and apply optional bot deployments."""
import re
import threading
from crea_core import db, FORMATTED
import workspace
import staging
from contextlib import closing

_lock=threading.Lock()

def test_mode(con=None):
    if con is None:
        with closing(db()) as connection:
            return test_mode(connection)
    row = con.execute("select value from app_settings where key='discord_test_mode'").fetchone()
    return row is None or row['value'] != 'off'


def set_test_mode(enabled):
    if type(enabled) is not bool:
        raise ValueError('Test mode must be on or off')
    with closing(db()) as con, con:
        con.execute("insert or replace into app_settings(key,value) values('discord_test_mode',?)",
                    ('on' if enabled else 'off',))
    return {'enabled': enabled}


def _record(con,draft_id):
    row=con.execute('select * from workspace_test_sends where draft_id=?',(draft_id,)).fetchone()
    return dict(row) if row else None

def current_result():
    draft=workspace.current()
    con=db()
    try:return _record(con,draft['id'])
    finally:con.close()

def send_current(draft_id,provider,destination=None, expected_test_mode=None):
    if not isinstance(draft_id,str) or not re.fullmatch(r'[0-9a-f-]{36}',draft_id):raise ValueError('Invalid draft ID')
    if not _lock.acquire(blocking=False):return {'ok':False,'code':'in_progress'}
    try:
        existing_con=db()
        try:
            previous=_record(existing_con,draft_id)
            if previous and previous['status'] in ('confirmed','pending','unverified'):
                return {'ok':previous['status']=='confirmed',**previous}
        finally:existing_con.close()
        state=provider.status()
        if not state['capabilities']['send']:
            return {'ok':False,'code':'provider_unavailable','error':state['reason']}
        expected = {key: state.get(key) for key in ('provider', 'sender_id', 'guild_id', 'channel_id')}
        if (destination is not None or state.get('provider') == 'discord_user') and destination != expected:
            return {'ok':False,'code':'destination_changed','error':'Discord sender or destination changed. Review the current destination.'}
        con=db()
        try:
            draft=workspace.current()
            with con:
                con.execute('begin immediate')
                staging.require_composer_idle(con)
                mode = test_mode(con)
                if expected_test_mode is not mode and (expected_test_mode is not None or not mode):
                    raise ValueError('Test mode changed. Review the send controls and try again.')
                if draft['id']!=draft_id:raise ValueError('Draft changed; review it before sending')
                previous=_record(con,draft_id)
                if previous and previous['status'] in ('confirmed','pending','unverified'):
                    return {'ok':previous['status']=='confirmed',**previous}
                if draft['status'] not in ('draft','prepared','failed_unverified'):
                    raise ValueError('Draft is not editable')
                if not draft['text'].strip() and not draft['asset_ids']:
                    raise ValueError('Draft is empty')
                paths=[]
                for aid in draft['asset_ids']:
                    row=con.execute('select id,status from assets where id=?',(aid,)).fetchone()
                    path=FORMATTED/f'{aid}.jpg'
                    if not row or row['status']!='ready' or not path.is_file():
                        raise ValueError('Selected crea attachment is unavailable')
                    paths.append(path)
                if paths and not state['capabilities']['attach']:
                    return {'ok':False,'code':'provider_unavailable','error':'Discord account cannot attach files'}
                package_id = None
                if paths and not mode:
                    package, _ = staging.validate_hot(con, None, draft['asset_ids'])
                    package_id = package['id']
                channel_id=state['channel_id']
                con.execute('''insert into workspace_test_sends(draft_id,channel_id,guild_id,status) values(?,?,?,'pending')
                  on conflict(draft_id) do update set channel_id=excluded.channel_id,guild_id=excluded.guild_id,status='pending',error=null,updated_at=current_timestamp''',(draft_id,channel_id,state.get('guild_id')))
            result=provider.send(draft_id,draft['text'],paths,draft.get('reply_to_id',''))
            status='confirmed' if result.get('ok') and result.get('message_id') and result.get('sender_id') and result.get('channel_id')==channel_id else 'failed' if result.get('code')=='failed' else 'unverified'
            with con:
                con.execute('begin immediate')
                deployment_error = None
                if status == 'confirmed' and package_id:
                    try:
                        staging.deploy_hot(con, package_id, draft['asset_ids'])
                    except ValueError:
                        deployment_error = 'Discord confirmed delivery, but Hot changed during send. Review the sent crea before marking them Used.'
                con.execute('''update workspace_test_sends set status=?,message_id=?,sender_id=?,error=?,updated_at=current_timestamp where draft_id=?''',
                    (status,result.get('message_id') if status=='confirmed' else None,result.get('sender_id') if status=='confirmed' else None,
                     result.get('error') if status!='confirmed' else deployment_error,draft_id))
            return {'ok':status=='confirmed',**_record(con,draft_id)}
        finally:con.close()
    finally:_lock.release()
