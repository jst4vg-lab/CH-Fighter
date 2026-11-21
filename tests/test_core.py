import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from crea_core import eligible_files, parse, render_asset, scan, db, visible_assets


class CoreTests(unittest.TestCase):
    def test_existing_creator_table_gets_enabled_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.sqlite'
            con=sqlite3.connect(path)
            con.execute('create table creators(name text primary key,color text)')
            con.execute("insert into creators values('taco','#725436')")
            con.commit();con.close()
            with patch('crea_core.DB',path):
                con=db()
                self.assertEqual(con.execute("select enabled from creators where name='taco'").fetchone()[0],1)
                con.close()

    def test_creator_visibility_migrates_and_filters_ready_and_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'app.sqlite'
            with patch('crea_core.DB',path):
                con=db()
                for name in ('taco','oneg'):
                    con.execute('insert into creators(name,color) values(?,?)',(name,'#123456'))
                for aid,creator,used in [('a','taco',0),('b','oneg',0),('c','oneg',1)]:
                    con.execute('''insert into assets(id,relpath,sha256,branch,type,creator,status,used)
                        values(?,?,?,?,?,?,?,?)''',(aid,aid+'.png',aid,'af','fgt',creator,'ready',used))
                con.commit()
                self.assertEqual([a['id'] for a in visible_assets()],['b','a'])
                con.execute("update creators set enabled=0 where name='oneg'")
                con.commit();con.close()
                self.assertEqual([a['id'] for a in visible_assets()],['a'])
                self.assertEqual(visible_assets('used'),[])
                con=db()
                con.execute("update creators set enabled=1 where name='oneg'")
                con.commit();con.close()
                self.assertEqual([a['id'] for a in visible_assets('used')],['c'])

    def test_filename_and_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            good=root/'oneg'/'Space'/'space combat'/'hf_sct_oneg-7.png'
            good.parent.mkdir(parents=True)
            good.write_bytes(b'x')
            repost=root/'oneg'/'repost-misc'/'af-fgt-oneg-1.png'
            repost.parent.mkdir(parents=True)
            repost.write_bytes(b'x')
            self.assertEqual(list(eligible_files(root)),[good])
            fields,issue=parse(good,root)
            self.assertIsNone(issue)
            self.assertEqual((fields['branch'],fields['type'],fields['creator']),('hf','sct','oneg'))
            bad=good.with_name('blank.png')
            self.assertIsNotNone(parse(bad,root)[1])

    def test_render_preserves_source_and_output_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; output=root/'formatted'; thumbs=root/'thumbnails'
            src=source/'taco'/'Missiles'/'mi-mis-taco-5bp-1.png'
            src.parent.mkdir(parents=True)
            Image.new('RGBA',(120,400),(220,20,20,180)).save(src)
            before=hashlib.sha256(src.read_bytes()).hexdigest()
            row={'id':'sample','relpath':str(src.relative_to(source)),'sha256':before,'mode':'fit','focal_x':.5,'focal_y':.5,'type':'mis','bp':5,'render_key':None}
            key=render_asset(row,'#385A72',source,output,thumbs)
            self.assertTrue(key)
            with Image.open(output/'sample.jpg') as image:
                self.assertEqual(image.size,(1920,1920))
                self.assertEqual(image.format,'JPEG')
            self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),before)
            row['mode']='crop'; row['focal_y']=1
            self.assertNotEqual(render_asset(row,'#385A72',source,output,thumbs),key)

    def test_scan_persists_and_flags_exact_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'
            first=source/'taco'/'Missiles'/'mi-mis-taco-1.png'
            second=source/'taco'/'Missiles'/'mi-mis-taco-2.png'
            first.parent.mkdir(parents=True)
            Image.new('RGB',(40,40),'red').save(first)
            second.write_bytes(first.read_bytes())
            with patch('crea_core.DB',root/'app.sqlite'):
                self.assertEqual(scan(source)['scanned'],2)
                con=db(); status=[tuple(r) for r in con.execute('select status,issue from assets order by relpath')]
                self.assertEqual(status[0][0],'pending')
                self.assertEqual(status[1][0],'review')
                self.assertIn('Exact duplicate',status[1][1])
                con.close()

    def test_fit_keeps_full_art_and_uses_blurred_source_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; src=source/'taco'/'Missiles'/'mi-mis-taco-1.png'
            src.parent.mkdir(parents=True)
            art=Image.new('RGB',(100,300),'red')
            ImageDraw.Draw(art).rectangle((0,150,99,299),fill='blue')
            art.save(src)
            row={'id':'fit','relpath':str(src.relative_to(source)),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'mode':'fit','focal_x':.5,'focal_y':.5,'type':'mis','bp':None,'render_key':None}
            render_asset(row,'#725436',source,root/'out',root/'thumbs')
            with Image.open(root/'out/fit.jpg') as image:
                self.assertEqual(image.size,(1920,1920))
                self.assertGreater(image.getpixel((960,100))[0],180)
                self.assertGreater(image.getpixel((960,1550))[2],150)
                self.assertNotEqual(image.getpixel((100,100)),image.getpixel((100,1550)))
                self.assertEqual(image.getpixel((100,1800))[0] > 50,True)


if __name__=='__main__': unittest.main()
