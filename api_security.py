"""HTTP framing, browser origin checks, and per-launch request protection."""
import hmac
import json
import secrets
import socket
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

CSRF_TOKEN = secrets.token_urlsafe(32)
MAX_BODY = 1_000_000
CSP = "; ".join((
    "default-src 'none'", "script-src 'self'", "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: https://cdn.discordapp.com https://media.discordapp.net https://images-ext-1.discordapp.net https://images-ext-2.discordapp.net",
    "connect-src 'self'", "font-src 'self'", "manifest-src 'self'", "worker-src 'self'",
    "frame-src 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'self'",
    "frame-ancestors 'none'",
))


class RequestError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def authority(value):
    if not isinstance(value, str) or not value or value != value.strip() or any(c in value for c in '/\\?#@,\r\n'):
        return None
    try:
        parsed = urlsplit('http://' + value)
        if parsed.username or parsed.password or not parsed.hostname or parsed.port == 0:
            return None
        host = parsed.hostname.lower()
        if host not in ('localhost', '127.0.0.1') and not all(c.isalnum() or c in '.-' for c in host):
            return None
        return host, parsed.port
    except ValueError:
        return None


def same_origin(value, expected):
    try:
        actual = urlsplit(value)
        wanted = urlsplit(expected)
        return (actual.scheme in ('http', 'https') and not actual.username and not actual.password
                and actual.path in ('', '/') and not actual.query and not actual.fragment
                and (actual.scheme, actual.hostname, actual.port or (443 if actual.scheme == 'https' else 80))
                == (wanted.scheme, wanted.hostname, wanted.port or (443 if wanted.scheme == 'https' else 80)))
    except (TypeError, ValueError):
        return False


def headers_all(headers, key):
    return headers.get_all(key, []) if hasattr(headers, 'get_all') else ([headers[key]] if key in headers else [])


def body_length(headers, required=True):
    if headers_all(headers, 'Transfer-Encoding'):
        raise RequestError(400, 'Transfer encoding is unsupported')
    lengths = headers_all(headers, 'Content-Length')
    if not lengths and not required:
        return 0
    if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
        raise RequestError(400, 'Invalid Content-Length')
    length = int(lengths[0])
    if length > MAX_BODY:
        raise RequestError(413, 'Request too large')
    return length


def read_json(handler):
    length = body_length(handler.headers)
    if handler.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise RequestError(415, 'Use application/json')
    try:
        content = handler.rfile.read(length)
    except (TimeoutError, socket.timeout):
        raise RequestError(408, 'Request body timed out') from None
    if len(content) != length:
        raise RequestError(400, 'Incomplete request body')
    try:
        body = json.loads(content or b'{}')
    except (ValueError, UnicodeError):
        raise RequestError(400, 'Invalid JSON') from None
    if not isinstance(body, dict):
        raise RequestError(400, 'Expected a JSON object')
    return body


def token_matches(headers):
    return hmac.compare_digest(headers.get('X-CH-CSRF', ''), CSRF_TOKEN)


class LocalHTTPServer(ThreadingHTTPServer):
    """Cap worker allocation before creating a request thread."""
    daemon_threads = True
    request_timeout = 15

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, address

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nRetry-After: 1\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()
