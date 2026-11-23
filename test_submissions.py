"""Persist acknowledged test sends without touching Crea deployment state."""
import re
import threading
from crea_core import db, FORMATTED
import workspace

_lock=threading.Lock()

def _record(con,draft_id):
    row=con.execute('select * from workspace_test_sends where draft_id=?',(draft_id,)).fetchone()
    return dict(row) if row else None

def current_result():
    draft=workspace.current()
    con=db()
    try:return _record(con,draft['id'])
    finally:con.close()

def send_current(draft_id,provider):
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
        con=db()
        try:
            with con:
                draft=workspace.current()
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
                    return {'ok':False,'code':'provider_unavailable','error':'Write bot cannot attach files'}
                channel_id=state['channel_id']
                con.execute('''insert into workspace_test_sends(draft_id,channel_id,guild_id,status) values(?,?,?,'pending')
                  on conflict(draft_id) do update set channel_id=excluded.channel_id,guild_id=excluded.guild_id,status='pending',error=null,updated_at=current_timestamp''',(draft_id,channel_id,state.get('guild_id')))
            result=provider.send(draft_id,draft['text'],paths,draft.get('reply_to_id',''))
            status='confirmed' if result.get('ok') and result.get('message_id') and result.get('sender_id') and result.get('channel_id')==channel_id else 'failed' if result.get('code')=='failed' else 'unverified'
            with con:
                con.execute('''update workspace_test_sends set status=?,message_id=?,sender_id=?,error=?,updated_at=current_timestamp where draft_id=?''',
                    (status,result.get('message_id') if status=='confirmed' else None,result.get('sender_id') if status=='confirmed' else None,
                     result.get('error') if status!='confirmed' else None,draft_id))
            return {'ok':status=='confirmed',**_record(con,draft_id)}
        finally:con.close()
    finally:_lock.release()
