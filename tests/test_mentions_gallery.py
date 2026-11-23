from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from communications.core.mentions import prepare
from crea_core import db
import discord_teams
import gallery_order
import staging


class MentionsAndGalleryTests(TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch('crea_core.DB', root / 'app.sqlite'))

    def asset(self, asset_id, branch, kind):
        with closing(db()) as con, con:
            con.execute("insert or ignore into creators(name,color) values('test','#123456')")
            con.execute("""insert into assets(id,relpath,sha256,branch,type,creator,status)
                         values(?,?,?,?,?,'test','ready')""",
                        (asset_id, f'{asset_id}.png', 'x', branch, kind))

    def test_only_selected_utf16_spans_are_approved(self):
        text = '🔥 @Alice and @Ops <@777> @everyone'
        user = {'kind':'user','id':'42','name':'Alice','guild_id':'1','channel_id':'2','start':3,'end':9}
        role = {'kind':'role','id':'91','name':'Ops','guild_id':'1','channel_id':'2','start':14,'end':18}
        wire, allowed = prepare(text, [user, role], {'guild_id':'1','channel_id':'2'})
        self.assertEqual(wire, '🔥 <@42> and <@&91> <@777> @everyone')
        self.assertEqual(allowed, {'users':['42'], 'roles':['91']})
        with self.assertRaisesRegex(ValueError, 'different channel'):
            prepare(text, [user], {'guild_id':'1','channel_id':'3'})
        with self.assertRaisesRegex(ValueError, 'no longer matches'):
            prepare(text.replace('@Alice','@Alina'), [user], {'guild_id':'1','channel_id':'2'})

    def test_mentions_survive_reserve_and_undo(self):
        self.asset('a','af','fgt')
        pack = staging.add_to_hot(['a'])['hot']
        picked = [{'kind':'user','id':'42','name':'Alice','guild_id':'1',
                   'channel_id':'2','start':0,'end':6}]
        staging.reserve_hot(pack['id'], '@Alice please review', picked)
        self.assertEqual(staging.activate(pack['id'])['hot']['mentions'], picked)
        staging.confirm_hot()
        self.assertEqual(staging.undo_last_deployment()['hot']['mentions'], picked)

    def test_gallery_order_saved_reset_and_newly_indexed_types(self):
        self.asset('a','af','fgt')
        self.asset('b','af','avi')
        self.asset('c','ar','inf')
        order = gallery_order.save({'branches':['nf','af'],'types':{'af':['fgt','avi']}})
        self.assertEqual(order['branches'][:2], ['nf','af'])
        self.assertEqual(order['types']['af'], ['fgt','avi'])
        self.assertEqual(order['types']['ar'], ['inf'])
        self.asset('d','af','afs')
        with closing(db()) as con:
            self.assertEqual(gallery_order.read(con)['types']['af'], ['fgt','avi','afs'])
        self.assertEqual(gallery_order.save({})['types']['af'], ['afs','avi','fgt'])

    def test_team_color_setting_persists(self):
        self.assertFalse(discord_teams.color_view()['enabled'])
        discord_teams.color_view(True)
        self.assertTrue(discord_teams.color_view()['enabled'])
