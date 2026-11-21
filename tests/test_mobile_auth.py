import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mobile_auth
import server


class MobileAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / 'auth.sqlite'
        def connect():
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
            return con
        self.db_patch = patch.object(mobile_auth, 'db', connect)
        self.db_patch.start()
        mobile_auth.setup()
        self.host_patch = patch.object(server, 'REMOTE_HOST', 'framework.tail.ts.net')
        self.host_patch.start()
        self.secret_patch = patch.object(server, 'DESKTOP_SECRET', 'desktop-only-secret')
        self.secret_patch.start()

    def tearDown(self):
        self.host_patch.stop()
        self.secret_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_pair_session_and_revoke(self):
        code = mobile_auth.new_code()['code']
        self.assertIsNone(mobile_auth.pair('000000' if code != '000000' else '111111'))
        token = mobile_auth.pair(code)
        self.assertTrue(token)
        self.assertIsNone(mobile_auth.pair(code))
        self.assertTrue(mobile_auth.valid(f'ch_mobile={token}'))
        mobile_auth.revoke()
        self.assertFalse(mobile_auth.valid(f'ch_mobile={token}'))

    def test_remote_permissions(self):
        handler = server.Handler.__new__(server.Handler)
        handler.headers = {'Host': 'framework.tail.ts.net', 'Origin': 'https://framework.tail.ts.net'}
        self.assertTrue(handler.allowed('GET', '/mobile'))
        self.assertTrue(handler.allowed('POST', '/api/mobile/pair'))
        self.assertFalse(handler.allowed('GET', '/api/staging'))
        self.assertFalse(handler.allowed('POST', '/api/import'))
        token = mobile_auth.pair(mobile_auth.new_code()['code'])
        handler.headers['Cookie'] = f'ch_mobile={token}'
        self.assertTrue(handler.allowed('GET', '/api/staging'))
        handler.path = '/api/assets?status=used'
        self.assertFalse(handler.allowed('GET', '/api/assets'))
        handler.path = '/api/assets'
        self.assertTrue(handler.allowed('GET', '/api/assets'))
        self.assertTrue(handler.allowed('POST', '/api/staging/hot/items'))
        self.assertTrue(handler.allowed('POST', '/api/mobile/clipboard'))
        self.assertTrue(handler.allowed('GET', '/api/mobile/clipboard/00000000-0000-0000-0000-000000000000'))
        self.assertFalse(handler.allowed('GET', '/api/desktop/clipboard-request'))
        self.assertTrue(handler.allowed('POST', '/api/staging/hot/confirm'))
        handler.headers['Origin'] = 'https://another.example'
        self.assertFalse(handler.allowed('POST', '/api/staging/hot/items'))
        self.assertFalse(handler.allowed('POST', '/api/staging/hot/confirm'))
        handler.headers = {'Host': 'localhost'}
        self.assertFalse(handler.allowed('GET', '/api/mobile/pair-code'))
        handler.headers['X-CH-Desktop'] = 'desktop-only-secret'
        self.assertTrue(handler.allowed('GET', '/api/mobile/pair-code'))

    def test_mobile_confirmation_requires_package_identity(self):
        token = mobile_auth.pair(mobile_auth.new_code()['code'])
        handler = server.Handler.__new__(server.Handler)
        handler.path = '/api/staging/hot/confirm'
        handler.headers = {'Host': 'framework.tail.ts.net',
                           'Origin': 'https://framework.tail.ts.net',
                           'Cookie': f'ch_mobile={token}'}
        handler.send_json = lambda data, status=200: (data, status)
        handler.body = lambda: {}
        with patch.object(server.staging, 'confirm_hot') as confirm:
            self.assertEqual(handler.do_POST()[1], 400)
            confirm.assert_not_called()
            handler.body = lambda: {'package_id': 'package-1', 'asset_ids': ['crea-1']}
            confirm.return_value = {'hot': None}
            self.assertEqual(handler.do_POST(), ({'hot': None}, 200))
            confirm.assert_called_once_with('package-1', ['crea-1'])


if __name__ == '__main__':
    unittest.main()
