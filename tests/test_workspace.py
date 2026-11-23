import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workspace
from crea_core import db


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patcher = patch('crea_core.DB', Path(self.temp.name) / 'workspace.sqlite')
        self.patcher.start()
        con = db()
        con.execute("insert into creators(name,color) values('taco','#725436')")
        con.execute("insert into assets(id,relpath,sha256,branch,type,creator,status) values('a','a.png','hash','af','fgt','taco','ready')")
        con.commit()
        con.close()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_initializes_and_persists_draft_and_selected_assets(self):
        first = workspace.current()
        self.assertEqual(first['status'], 'draft')
        self.assertEqual(first['asset_ids'], [])
        saved = workspace.save('Submission', ['a'], 'https://discord.com/channels/1/2')
        self.assertEqual(saved['id'], first['id'])
        self.assertEqual(workspace.current()['asset_ids'], ['a'])
        con = db()
        con.execute("update assets set used=1 where id='a'")
        con.commit()
        con.close()
        self.assertEqual(workspace.current()['asset_ids'], ['a'])
        db().close()
        self.assertEqual(workspace.current()['text'], 'Submission')
        with self.assertRaisesRegex(ValueError, 'no longer exist'):
            workspace.save('Submission', ['missing'])
        with self.assertRaisesRegex(ValueError, 'channel URL'):
            workspace.save('Submission', ['a'], 'https://discord.com.evil.test/channels/1/2')
        self.assertEqual(workspace.current()['asset_ids'], ['a'])

    def test_handoff_transitions_failure_recovery_and_history(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            workspace.transition('prepared')
        workspace.save('Message', ['a'])
        workspace.transition('prepared')
        self.assertEqual(workspace.save('Edited message', ['a'])['status'], 'draft')
        workspace.transition('prepared')
        workspace.transition('handoff_pending')
        with self.assertRaisesRegex(ValueError, 'Explicit user'):
            workspace.transition('sent_confirmed')
        workspace.transition('failed_unverified')
        workspace.transition('handoff_pending')
        workspace.transition('sent_confirmed', manual_confirmation=True)
        self.assertEqual(workspace.current()['status'], 'sent_confirmed')
        new = workspace.new_draft()
        self.assertNotEqual(new['id'], workspace.history()[1]['id'])
        self.assertEqual(new['status'], 'draft')
        self.assertEqual({item['status'] for item in workspace.history()}, {'draft', 'sent_confirmed'})


if __name__ == '__main__':
    unittest.main()
