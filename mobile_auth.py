"""Small, persistent pairing gate for the private mobile companion."""
import hashlib
import hmac
import secrets
import time
import threading
from collections import deque
from http.cookies import SimpleCookie

from crea_core import db

PAIR_LIFETIME = 300
SESSION_LIFETIME = 60 * 60 * 24 * 90
_code = None
_expires = 0
_attempts = 0
_attempt_times = deque()
_lock = threading.Lock()

def setup():
    con = db()
    con.execute('create table if not exists mobile_sessions (token_hash text primary key, expires integer not null)')
    con.commit()
    con.close()

class PairingThrottled(Exception):
    pass


def new_code():
    global _code, _expires, _attempts
    with _lock:
        _code = f'{secrets.randbelow(1000000):06d}'
        _expires = int(time.time()) + PAIR_LIFETIME
        _attempts = 0
        return {'code': _code, 'expires': _expires}


def pair(code):
    global _code, _expires, _attempts
    with _lock:
        now = time.time()
        while _attempt_times and now - _attempt_times[0] >= 60:
            _attempt_times.popleft()
        if len(_attempt_times) >= 10:
            raise PairingThrottled()
        _attempt_times.append(now)
        if not _code or now >= _expires:
            _code = None
            return None
        if not isinstance(code, str) or not hmac.compare_digest(code, _code):
            _attempts += 1
            if _attempts >= 5:
                _code = None
            return None
        _code = None
        _expires = 0
    token = secrets.token_urlsafe(32)
    con = db()
    try:
        with con:
            con.execute('insert into mobile_sessions values (?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(), int(time.time()) + SESSION_LIFETIME))
    finally:
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
