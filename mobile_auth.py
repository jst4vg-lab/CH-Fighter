"""Small, persistent pairing gate for the private mobile companion."""
import hashlib
import hmac
import secrets
import time
from http.cookies import SimpleCookie

from crea_core import db

PAIR_LIFETIME = 300
SESSION_LIFETIME = 60 * 60 * 24 * 90
_code = None
_expires = 0

def setup():
    con = db()
    con.execute('create table if not exists mobile_sessions (token_hash text primary key, expires integer not null)')
    con.commit()
    con.close()

def new_code():
    global _code, _expires
    _code = f'{secrets.randbelow(1000000):06d}'
    _expires = int(time.time()) + PAIR_LIFETIME
    return {'code': _code, 'expires': _expires}

def pair(code):
    global _code, _expires
    if not isinstance(code, str) or not _code or time.time() >= _expires or not hmac.compare_digest(code, _code):
        return None
    _code = None
    _expires = 0
    token = secrets.token_urlsafe(32)
    con = db()
    con.execute('insert into mobile_sessions values (?,?)', (hashlib.sha256(token.encode()).hexdigest(), int(time.time()) + SESSION_LIFETIME))
    con.commit()
    con.close()
    return token

def valid(cookie_header):
    try:
        cookie = SimpleCookie(); cookie.load(cookie_header or '')
        token = cookie['ch_mobile'].value
    except (KeyError, ValueError):
        return False
    con = db()
    row = con.execute('select expires from mobile_sessions where token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    con.close()
    return bool(row and row['expires'] > time.time())

def revoke():
    con = db()
    con.execute('delete from mobile_sessions')
    con.commit()
    con.close()
