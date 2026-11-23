"""Bounded HTTPS image retrieval with redirect and DNS validation."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

TRUSTED_HOSTS = {'cdn.discordapp.com','media.discordapp.net','images-ext-1.discordapp.net','images-ext-2.discordapp.net'}
MAX_IMAGE = 15 * 1024 * 1024
MIME = {'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif'}


class MediaError(ValueError):
    pass


def validated_url(value):
    if not isinstance(value, str) or len(value)>8192 or any(ord(char)<32 for char in value):
        raise MediaError('Invalid image URL')
    try:
        url=urlsplit(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.port not in (None,443):
            raise MediaError('Only public HTTPS images are supported')
        if url.hostname.endswith(('.local','.localhost','.internal')) or url.hostname=='localhost':
            raise MediaError('Local network images are blocked')
        addresses=socket.getaddrinfo(url.hostname,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise MediaError('Local network images are blocked')
        return url,addresses
    except (ValueError, OSError):
        raise MediaError('Image host unavailable or blocked') from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,address):
        super().__init__(host,443,timeout=10,context=ssl.create_default_context())
        self.address=address

    def connect(self):
        family,kind,protocol,_,target=self.address
        raw=socket.socket(family,kind,protocol)
        raw.settimeout(self.timeout)
        try:
            raw.connect(target)
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def fetch_image(value, allow_external=False):
    deadline=time.monotonic()+15
    for _ in range(4):
        if time.monotonic()>deadline:raise MediaError('Image download timed out')
        url,addresses=validated_url(value)
        if not allow_external and url.hostname.lower() not in TRUSTED_HOSTS:
            raise MediaError('External image requires consent')
        connection=PinnedHTTPS(url.hostname,addresses[0])
        try:
            path=(url.path or '/')+('?' + url.query if url.query else '')
            connection.request('GET',path,headers={'Accept':'image/avif,image/webp,image/png,image/jpeg,image/gif',
                                                   'User-Agent':'ClanHub-Media/1'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                destination=response.getheader('Location')
                if not destination:raise MediaError('Image redirect unavailable')
                value=urljoin(value,destination)
                continue
            if response.status!=200:raise MediaError('Image unavailable')
            mime=response.getheader('Content-Type','').split(';',1)[0].lower()
            if mime not in MIME:raise MediaError('Unsupported image format')
            length=response.getheader('Content-Length')
            if length and (not length.isdecimal() or int(length)>MAX_IMAGE):
                raise MediaError('Image exceeds the 15 MB limit')
            chunks=[]
            size=0
            while chunk:=response.read(min(65536,MAX_IMAGE-size+1)):
                if time.monotonic()>deadline:raise MediaError('Image download timed out')
                size+=len(chunk)
                if size>MAX_IMAGE:raise MediaError('Image exceeds the 15 MB limit')
                chunks.append(chunk)
            return mime,b''.join(chunks)
        except (OSError,http.client.HTTPException):
            raise MediaError('Image unavailable') from None
        finally:
            connection.close()
    raise MediaError('Too many image redirects')
