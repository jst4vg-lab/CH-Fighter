import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crea_core import db
import workspace
import test_submissions
from communications.outgoing import DisabledWriteProvider,DiscordBotWriteProvider,select_provider


class FakeWriteProvider:
    def __init__(self,result=None):
        self.calls=[]
        self.result=result or {'ok':True,'message_id':'444','sender_id':'555','channel_id':'333'}
    def status(self):return {'state':'connected','reason':'','channel_id':'333','capabilities':{'send':True,'reply':True,'attach':True}}
    def send(self,draft_id,text,paths,reply_to_id=''):
        self.calls.append((draft_id,text,[p.name for p in paths],reply_to_id))
        return self.result


class TestSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.db_patch=patch('crea_core.DB',self.root/'app.sqlite');self.format_patch=patch('test_submissions.FORMATTED',self.root/'formatted')
        self.db_patch.start();self.format_patch.start()
        (self.root/'formatted').mkdir()
        con=db();con.execute("insert into creators(name,color) values('creator','#123456')")
        con.execute("insert into assets(id,relpath,sha256,branch,type,creator,status,used) values('a','a.png','h','af','fgt','creator','ready',0)")
        con.commit();con.close()
        (self.root/'formatted'/'a.jpg').write_bytes(b'fixture')

    def tearDown(self):
        self.format_patch.stop();self.db_patch.stop();self.temp.cleanup()

    def test_acknowledged_send_is_idempotent_and_does_not_use_crea(self):
        draft=workspace.save('Test', ['a'], reply_to_id='123')
        provider=FakeWriteProvider()
        first=test_submissions.send_current(draft['id'],provider)
        second=test_submissions.send_current(draft['id'],provider)
        self.assertEqual(first['status'],'confirmed')
        self.assertEqual(second['message_id'],'444')
        self.assertEqual(provider.calls,[(draft['id'],'Test',['a.jpg'],'123')])
        next_draft=workspace.save('Changed',['a'])
        self.assertNotEqual(next_draft['id'],draft['id'])
        self.assertEqual(next_draft['text'],'Changed')
        con=db();self.assertEqual(con.execute("select used from assets where id='a'").fetchone()[0],0);con.close()

    def test_missing_attachment_and_unavailable_provider_preserve_draft(self):
        draft=workspace.save('Test',['a'])
        self.assertEqual(test_submissions.send_current(draft['id'],DisabledWriteProvider())['code'],'provider_unavailable')
        (self.root/'formatted'/'a.jpg').unlink()
        with self.assertRaisesRegex(ValueError,'unavailable'):
            test_submissions.send_current(draft['id'],FakeWriteProvider())
        self.assertIsNone(test_submissions.current_result())

    def test_unknown_outcome_cannot_be_retried_automatically(self):
        draft=workspace.save('Test',[])
        provider=FakeWriteProvider({'ok':False,'code':'unverified','error':'timeout'})
        first=test_submissions.send_current(draft['id'],provider)
        second=test_submissions.send_current(draft['id'],provider)
        self.assertEqual((first['status'],second['status']),('unverified','unverified'))
        self.assertEqual(len(provider.calls),1)

    def test_provider_selection_requires_explicit_bot_configuration(self):
        self.assertIsInstance(select_provider({'DISCORD_WRITE_PROVIDER':'disabled'}),DisabledWriteProvider)
        provider=select_provider({'DISCORD_WRITE_PROVIDER':'discord_bot','DISCORD_GUILD_ID':'1','DISCORD_WRITE_TEST_CHANNEL_ID':'2'})
        self.assertIsInstance(provider,DiscordBotWriteProvider)
        self.assertFalse(provider.status()['capabilities']['send'])
        self.assertNotIn('token',provider.status())


if __name__=='__main__':unittest.main()
