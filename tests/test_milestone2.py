import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import communications
from communications.outgoing import select_provider
import library_settings
from crea_core import db,scan,source_path

class LibraryAndCommunicationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.patch_db=patch('crea_core.DB',self.root/'app.sqlite')
        self.patch_source=patch('crea_core.SOURCE',self.root/'Original')
        self.patch_db.start();self.patch_source.start()
        (self.root/'Original').mkdir()
        db().close()

    def tearDown(self):
        self.patch_source.stop();self.patch_db.stop();self.temp.cleanup()

    def test_path_persistence_and_unavailable_source(self):
        new=self.root/'New Library ü'
        new.mkdir()
        library_settings.apply(str(new))
        self.assertEqual(source_path(),new)
        with self.assertRaises(ValueError):library_settings.apply(str(self.root/'missing'))
        self.assertEqual(source_path(),new)
        new.rmdir()
        self.assertFalse(library_settings.status()['available'])
        with self.assertRaisesRegex(ValueError,'Library Unavailable'):scan()

    def test_unique_hash_relink_preserves_id_and_used(self):
        old=self.root/'Original'/'taco'/'Air Corps'
        old.mkdir(parents=True)
        image=old/'af-fgt-taco-1.png'
        Image.new('RGB',(8,8),'red').save(image)
        scan()
        con=db();row=con.execute('select id from assets').fetchone();aid=row['id'];con.execute('update assets set used=1 where id=?',(aid,));con.commit();con.close()
        new=self.root/'New Library'/'taco'/'Air Corps'
        new.mkdir(parents=True)
        image.rename(new/'af-fgt-taco-2.png')
        library_settings.apply(str(self.root/'New Library'))
        scan()
        con=db();row=con.execute('select id,used,relpath from assets').fetchone();con.close()
        self.assertEqual((row['id'],row['used'],row['relpath']),(aid,1,'taco/Air Corps/af-fgt-taco-2.png'))

    def test_disabled_provider_and_event_deduplication(self):
        hub=communications.DiscordBotIncoming({'DISCORD_READ_PROVIDER':'disabled'})
        hub.start()
        self.assertEqual(select_provider({'DISCORD_WRITE_PROVIDER':'disabled'}).send('draft','',[])['code'],'provider_unavailable')
        data={'id':'1','content':'hello'}
        hub.publish('upsert','10','1',data)
        hub.publish('upsert','10','1',{**data,'content':'edited'})
        self.assertEqual(len(hub.messages),1)
        self.assertEqual(hub.snapshot(after=1)['events'][0]['message']['content'],'edited')
        hub.publish('delete','10','1')
        self.assertEqual(len(hub.messages),0)

if __name__=='__main__':unittest.main()
