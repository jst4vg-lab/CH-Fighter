from collections import deque
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import api_security
import mobile_auth
import remote_media
import server


class SecurityTests(TestCase):
    def headers(self, **values):
        headers=Message()
        for key,value in values.items():headers[key.replace('_','-')]=value
        return headers

    def test_negative_duplicate_and_oversized_lengths(self):
        for length in ('-1','1, 1','abc','1000001'):
            with self.assertRaises(api_security.RequestError):
                api_security.body_length(self.headers(Content_Length=length))
        headers=self.headers(Content_Length='2')
        headers['Content-Length']='2'
        with self.assertRaises(api_security.RequestError):api_security.body_length(headers)
        headers=self.headers(Content_Length='2',Transfer_Encoding='chunked')
        with self.assertRaises(api_security.RequestError):api_security.body_length(headers)

    def test_json_framing_and_incomplete_body(self):
        handler=SimpleNamespace(headers=self.headers(Content_Length='2',Content_Type='text/plain'),rfile=BytesIO(b'{}'))
        with self.assertRaises(api_security.RequestError):api_security.read_json(handler)
        handler.headers.replace_header('Content-Type','application/json')
        self.assertEqual(api_security.read_json(handler),{})
        handler.rfile=BytesIO(b'{')
        with self.assertRaises(api_security.RequestError):api_security.read_json(handler)

    def test_cross_origin_and_csrf(self):
        handler=server.Handler.__new__(server.Handler)
        handler.server=SimpleNamespace(server_port=8765)
        with patch.object(server,'DESKTOP_SECRET',''),patch.object(server,'REMOTE_HOST',''):
            handler.headers=self.headers(Host='127.0.0.1:8765',Origin='https://evil.example')
            self.assertFalse(handler.allowed('POST','/api/communications/composer'))
            handler.headers.replace_header('Origin','http://127.0.0.1:8765')
            self.assertFalse(handler.allowed('POST','/api/communications/composer'))
            handler.headers['X-CH-CSRF']=api_security.CSRF_TOKEN
            self.assertTrue(handler.allowed('POST','/api/communications/composer'))
            handler.headers['Host']='localhost:8765'
            self.assertFalse(handler.allowed('GET','/api/security'))

    def test_pairing_attempts_expiry_and_concurrent_consumption(self):
        with TemporaryDirectory() as root,patch('crea_core.DB',Path(root)/'db'),patch.object(mobile_auth,'_attempt_times',deque()):
            mobile_auth.setup()
            code=mobile_auth.new_code()['code']
            wrong='000000' if code!='000000' else '111111'
            for _ in range(5):self.assertIsNone(mobile_auth.pair(wrong))
            self.assertIsNone(mobile_auth.pair(code))
            code=mobile_auth.new_code()['code']
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(mobile_auth.pair,[code,code]))
            self.assertEqual(sum(bool(result) for result in results),1)
            for _ in range(2):mobile_auth.pair(wrong)
            with self.assertRaises(mobile_auth.PairingThrottled):mobile_auth.pair(wrong)

    def test_expired_code_and_fresh_code_after_limit(self):
        with patch.object(mobile_auth,'_attempt_times',deque()),patch.object(mobile_auth,'_expires',0),patch.object(mobile_auth,'_code','123456'):
            self.assertIsNone(mobile_auth.pair('123456'))
            self.assertIsNone(mobile_auth._code)
            value=mobile_auth.new_code()
            self.assertEqual(len(value['code']),6)

    def test_remote_dns_blocks_local_and_mixed_addresses(self):
        for ip in ('127.0.0.1','10.0.0.1','169.254.169.254','::1','100.64.0.1'):
            records=[(2,1,6,'',(ip,443))]
            with patch('remote_media.socket.getaddrinfo',return_value=records):
                with self.assertRaises(remote_media.MediaError):
                    remote_media.validated_url('https://untrusted.example/test.png')
        with self.assertRaises(remote_media.MediaError):
            remote_media.validated_url('http://example.com/image.png')

    def test_loopback_csrf_bootstrap_and_bounded_worker_overload(self):
        import http.client
        import threading
        with TemporaryDirectory() as root,patch('crea_core.DB',Path(root)/'db'),patch.object(server,'DESKTOP_SECRET',''),patch.object(server,'REMOTE_HOST',''):
            instance=api_security.LocalHTTPServer(('127.0.0.1',0),server.Handler)
            thread=threading.Thread(target=instance.serve_forever,daemon=True)
            thread.start()
            try:
                def request(method,path,body=None,headers=None):
                    conn=http.client.HTTPConnection('127.0.0.1',instance.server_port,timeout=3)
                    conn.request(method,path,body=body,headers=headers or {})
                    response=conn.getresponse()
                    data=response.read()
                    conn.close()
                    return response.status,data
                self.assertEqual(request('POST','/api/communications/test-mode','{"enabled":false}',
                    {'Content-Type':'text/plain','Origin':'https://evil.example'})[0],403)
                status,data=request('GET','/api/security')
                import json
                token=json.loads(data)['csrf_token']
                self.assertEqual(status,200)
                self.assertEqual(request('POST','/api/communications/test-mode','{"enabled":false}',
                    {'Content-Type':'application/json','X-CH-CSRF':token})[0],200)
                for _ in range(32):instance.slots.acquire()
                self.assertEqual(request('GET','/api/health')[0],503)
                for _ in range(32):instance.slots.release()
            finally:
                instance.shutdown();instance.server_close();thread.join()

    def test_request_timeout_and_private_storage_modes(self):
        import socket
        import threading
        import private_data
        instance=api_security.LocalHTTPServer(('127.0.0.1',0),server.Handler)
        instance.request_timeout=.1
        thread=threading.Thread(target=instance.serve_forever,daemon=True);thread.start()
        try:
            with socket.create_connection(instance.server_address,timeout=2) as sock:
                sock.sendall(b'POST / HTTP/1.1\r\n')
                self.assertEqual(sock.recv(1024),b'')
        finally:
            instance.shutdown();instance.server_close();thread.join()
        with TemporaryDirectory() as root:
            folder=Path(root)/'private'
            folder.mkdir(mode=0o755)
            database=folder/'app.sqlite'
            database.write_text('fixture')
            database.chmod(0o644)
            private_data.secure_data(folder)
            self.assertEqual(folder.stat().st_mode&0o777,0o700)
            self.assertEqual(database.stat().st_mode&0o777,0o600)

    def test_media_redirects_are_revalidated(self):
        from unittest.mock import MagicMock
        response=MagicMock(status=302)
        response.getheader.return_value='https://127.0.0.1/private'
        conn=MagicMock()
        conn.getresponse.return_value=response
        with patch('remote_media.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(remote_media.MediaError):
                remote_media.fetch_image('https://public.example/image')
        public=(__import__('urllib.parse',fromlist=['urlsplit']).urlsplit('https://example.com/x'),[(2,1,6,'',('8.8.8.8',443))])
        with patch('remote_media.validated_url',side_effect=[public,remote_media.MediaError('blocked')]) as validate,patch('remote_media.PinnedHTTPS',return_value=conn):
            with self.assertRaisesRegex(remote_media.MediaError,'blocked'):
                remote_media.fetch_image('https://example.com/x',allow_external=True)
            self.assertEqual(validate.call_count,2)
