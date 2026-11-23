"""Send the desktop composer package through the configured Discord profile."""
from contextlib import closing
import json
import re
from uuid import UUID

from crea_core import db, FORMATTED
import staging
from test_submissions import test_mode
from communications.core.mentions import prepare


def _active(con):
    return con.execute("select * from composer_sends where status in ('pending','unverified')").fetchone()


def status():
    with closing(db()) as con:
        row = _active(con)
        return dict(row) if row else None


def recover():
    with closing(db()) as con, con:
        con.execute("""update composer_sends set status='unverified',
                    error='The app closed before Discord delivery was confirmed' where status='pending'""")


def _apply_package(con, package_id, asset_ids, mode):
    if package_id is None:
        return
    if mode:
        staging.validate_hot(con, package_id, asset_ids)
        con.execute('delete from packages where id=?', (package_id,))
    else:
        staging.deploy_hot(con, package_id, asset_ids)


def resolve(send_id, posted):
    if type(posted) is not bool:
        raise ValueError('Confirm whether the message appeared in Discord')
    with closing(db()) as con, con:
        con.execute('begin immediate')
        row = _active(con)
        if not row or row['id'] != send_id or row['status'] != 'unverified':
            raise ValueError('No unverified send matches this request')
        if posted:
            _apply_package(con, row['package_id'], json.loads(row['asset_ids']), row['test_mode'])
        con.execute('update composer_sends set status=?, error=null where id=?',
                    ('manually_confirmed' if posted else 'failed', send_id))
    return {'ok': True}


def send(body, provider):
    send_id = body.get('id')
    try:
        if str(UUID(send_id)) != send_id:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ValueError('Invalid Discord send ID') from None
    text, ids, package_id = (body.get(key) for key in ('text', 'asset_ids', 'package_id'))
    if not isinstance(text, str) or len(text) > 2000:
        raise ValueError('Discord messages can contain up to 2000 characters')
    if (not isinstance(ids, list) or len(ids) > 10 or any(not isinstance(asset, str) for asset in ids)
            or bool(ids) != isinstance(package_id, str) or (not ids and package_id is not None)
            or not (text.strip() or ids)):
        raise ValueError('Select crea or enter a message')
    reply = body.get('reply')
    if reply is not None and (not isinstance(reply, dict) or
                             any(not isinstance(reply.get(key), str) or
                                 not re.fullmatch(r'[0-9]{1,24}', reply[key])
                                 for key in ('id', 'guild_id', 'channel_id'))):
        raise ValueError('Invalid Discord reply target')
    state = provider.status()
    destination = {key: state.get(key) for key in ('provider', 'sender_id', 'guild_id', 'channel_id')}
    chosen = body.get('mentions', [])
    wire_text, allow_mentions = prepare(text, chosen, destination)
    if len(wire_text)>2000:
        raise ValueError('Discord messages can contain up to 2000 characters after mentions are expanded')
    with closing(db()) as con:
        with con:
            con.execute('begin immediate')
            previous = con.execute('select * from composer_sends where id=?', (send_id,)).fetchone()
            if previous:
                return {**dict(previous), 'ok': previous['status'] == 'confirmed'}
            if _active(con):
                raise ValueError('Resolve the previous Discord send first')
            caps = state['capabilities']
            if not caps.get('send'):
                raise ValueError(state.get('reason') or 'The active Discord profile cannot send')
            if body.get('destination') != destination:
                raise ValueError('Discord destination or sender changed. Review it before sending.')
            mode = test_mode(con)
            if body.get('test_mode') is not mode:
                raise ValueError('Test mode changed. Review it before sending.')
            if reply:
                if not caps.get('reply'):
                    raise ValueError('The active Discord profile cannot send replies')
                if any(reply[key] != destination[key] for key in ('guild_id', 'channel_id')):
                    raise ValueError('The reply target is outside the configured send channel')
            paths = []
            if ids:
                if not caps.get('attach'):
                    raise ValueError('The active Discord profile cannot attach files in this channel')
                staging.validate_hot(con, package_id, ids)
                for asset in ids:
                    path = FORMATTED / f'{asset}.jpg'
                    if not path.is_file() or not con.execute(
                            "select 1 from assets where id=? and used=0 and status='ready'", (asset,)).fetchone():
                        raise ValueError('A selected crea is unavailable')
                    paths.append(path)
                con.execute('update packages set submission=?,mentions_json=? where id=?', (text, json.dumps(chosen), package_id))
            elif con.execute("select 1 from package_items i join packages p on i.package_id=p.id where p.location='hot'").fetchone():
                raise ValueError('The composer attachments changed. Review them before sending.')
            con.execute('''insert into composer_sends
                (id,package_id,asset_ids,test_mode,guild_id,channel_id,sender_id,status)
                values (?,?,?,?,?,?,?,'pending')''',
                (send_id, package_id, json.dumps(ids), mode, destination['guild_id'],
                 destination['channel_id'], destination['sender_id']))

        try:
            options = {'reply_to_id': reply['id']} if reply else {}
            if chosen:
                options['mentions'] = allow_mentions
            result = provider.send(send_id, wire_text, paths, **options)
        except Exception:
            result = {'error': 'Discord did not confirm delivery'}
        confirmed = (result.get('ok') and result.get('message_id')
                     and result.get('channel_id') == destination['channel_id']
                     and result.get('sender_id') == destination['sender_id'])
        outcome = 'confirmed' if confirmed else 'failed' if result.get('code') in ('failed', 'provider_unavailable') else 'unverified'
        error = None if confirmed else result.get('error') or 'Check Discord before sending again'
        with con:
            con.execute('begin immediate')
            if confirmed:
                try:
                    _apply_package(con, package_id, ids, mode)
                except ValueError:
                    error = 'Discord confirmed the message, but the local package changed'
            con.execute('update composer_sends set status=?, message_id=?, error=? where id=?',
                        (outcome, result.get('message_id') if confirmed else None, error, send_id))
        return {'ok': bool(confirmed), 'status': outcome, 'error': error,
                'url': result.get('url') if confirmed else None}
