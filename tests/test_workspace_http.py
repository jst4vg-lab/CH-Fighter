import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class WorkspaceHandlerTests(unittest.TestCase):
    def test_workspace_initializes_and_routes_local_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch('crea_core.DB', Path(directory) / 'app.sqlite'), patch.object(server, 'DESKTOP_SECRET', ''), patch.object(server, 'REMOTE_HOST', ''):
            handler = server.Handler.__new__(server.Handler)
            handler.headers = {'Host': '127.0.0.1'}
            handler.send_json = lambda data, status=200: (data, status)
            handler.path = '/api/workspace/draft'
            first, status = handler.do_GET()
            self.assertEqual(status, 200)
            self.assertEqual(first['status'], 'draft')
            handler.body = lambda: {'text': 'Local fixture', 'asset_ids': []}
            saved, status = handler.do_POST()
            self.assertEqual(status, 200)
            self.assertEqual(saved['id'], first['id'])
            current, status = handler.do_GET()
            self.assertEqual(status, 200)
            self.assertEqual(current['text'], 'Local fixture')
            handler.path = '/api/workspace/drafts'
            history, status = handler.do_GET()
            self.assertEqual(status, 200)
            self.assertEqual(history[0]['id'], first['id'])


if __name__ == '__main__':
    unittest.main()
