from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

import composer
import staging
from crea_core import db
from test_submissions import set_test_mode


class ComposerTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        root = Path(directory)
        self.enterContext(patch('crea_core.DB', root / 'test.sqlite'))
        self.enterContext(patch('composer.FORMATTED', root))
        (root / 'asset.jpg').write_bytes(b'fixture')
        con = db()
        with con:
            con.execute("insert into creators(name,color) values('a','#123456')")
            con.execute("""insert into assets(id,relpath,sha256,branch,type,creator,status)
                           values('asset','asset.png','hash','af','fgt','a','ready')""")
        con.close()
        self.destination = {'provider': 'discord_bot', 'guild_id': '1', 'channel_id': '2', 'sender_id': '3'}
        self.calls = 0
        self.result = {'ok': True, 'message_id': '4', 'channel_id': '2', 'sender_id': '3'}

    def status(self):
        return {**self.destination, 'capabilities': {'send': True, 'attach': True, 'reply': True}}

    def send(self, send_id, text, paths, reply_to_id=''):
        self.last_reply = reply_to_id
        self.calls += 1
        if paths:
            with self.assertRaisesRegex(ValueError, 'Resolve the Discord send'):
                staging.reserve_hot()
            with self.assertRaisesRegex(ValueError, 'Resolve the Discord send'):
                staging.confirm_hot()
        return self.result

    def payload(self, *, mode=True, attach=True, text=''):
        hot = staging.add_to_hot(['asset'])['hot'] if attach else None
        return {'id': str(uuid4()), 'text': text, 'package_id': hot['id'] if hot else None,
                'asset_ids': ['asset'] if hot else [], 'test_mode': mode, 'destination': self.destination}

    def test_test_send_clears_composer_without_marking_used_and_deduplicates(self):
        body = self.payload()
        self.assertTrue(composer.send(body, self)['ok'])
        self.assertIsNone(staging.snapshot()['hot'])
        self.assertEqual(staging.snapshot()['used_count'], 0)
        self.assertTrue(composer.send(body, self)['ok'])
        self.assertEqual(self.calls, 1)

    def test_deployment_send_marks_used_and_can_be_undone(self):
        set_test_mode(False)
        self.assertTrue(composer.send(self.payload(mode=False, text='Report'), self)['ok'])
        self.assertEqual(staging.snapshot()['used_count'], 1)
        staging.undo_last_deployment()
        self.assertEqual(staging.snapshot()['hot']['submission'], 'Report')

    def test_unknown_delivery_requires_resolution_and_preserves_text(self):
        self.result = {'ok': False, 'code': 'unverified'}
        body = self.payload(text='Report')
        self.assertEqual(composer.send(body, self)['status'], 'unverified')
        self.assertEqual(staging.snapshot()['hot']['submission'], 'Report')
        with self.assertRaisesRegex(ValueError, 'previous Discord send'):
            composer.send({**body, 'id': str(uuid4())}, self)
        composer.resolve(body['id'], False)
        self.assertIsNone(composer.status())
        self.assertIsNotNone(staging.snapshot()['hot'])

    def test_text_only_send_does_not_update_staging(self):
        before = staging.snapshot()
        self.assertTrue(composer.send(self.payload(attach=False, text='Report'), self)['ok'])
        self.assertEqual(staging.snapshot(), before)

    def test_reserve_move_saves_latest_text(self):
        hot = staging.add_to_hot(['asset'])['hot']
        moved = staging.reserve_hot(hot['id'], 'Latest text')
        self.assertEqual(moved['reserve'][0]['submission'], 'Latest text')
        self.assertEqual(staging.activate(hot['id'])['hot']['submission'], 'Latest text')

    def test_valid_reply_and_cross_channel_rejection(self):
        body = self.payload(text='Response')
        body['reply'] = {'id': '10', 'guild_id': '1', 'channel_id': '99'}
        with self.assertRaisesRegex(ValueError, 'outside the configured'):
            composer.send(body, self)
        self.assertEqual(self.calls, 0)
        body['reply']['channel_id'] = '2'
        self.assertTrue(composer.send(body, self)['ok'])
        self.assertEqual(self.last_reply, '10')

    def test_user_profile_can_deploy_to_the_current_channel(self):
        self.destination['provider'] = 'discord_user'
        set_test_mode(False)
        body = self.payload(mode=False, text='Response')
        self.assertTrue(composer.send(body, self)['ok'])
        self.assertEqual(self.calls, 1)
        self.assertIsNone(staging.snapshot()['hot'])
        self.assertEqual(staging.snapshot()['used_count'], 1)

    def test_unavailable_reply_keeps_package(self):
        self.result = {'ok': False, 'code': 'failed', 'error': 'Original message unavailable'}
        body = self.payload(text='Response')
        body['reply'] = {'id': '10', 'guild_id': '1', 'channel_id': '2'}
        result = composer.send(body, self)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(staging.snapshot()['hot']['submission'], 'Response')
