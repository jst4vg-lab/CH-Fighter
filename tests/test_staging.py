import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import staging
from crea_core import db

class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch('crea_core.DB',Path(self.tmp.name)/'test.sqlite')
        self.patch.start()
        con=db()
        con.execute("insert into creators(name,color) values('taco','#725436')")
        for aid,typ,bp in [('a','mbt',5),('b','mbt',5),('c','mbt',None),('d','fgt',None)]:
            con.execute('''insert into assets(id,relpath,sha256,branch,type,creator,bp,seq,width,height,source_format,status)
              values(?,?,?,?,?,?,?,?,?,?,?,?)''',(aid,f'{aid}.png',aid,'ar' if typ=='mbt' else 'af',typ,'taco',bp,1,100,100,'PNG','ready'))
        con.commit();con.close()

    def tearDown(self):self.patch.stop();self.tmp.cleanup()

    def test_hot_reserve_swap_submission_and_replenishment(self):
        staging.add_to_hot(['a'])
        staging.reserve_hot()
        reserve_id=staging.snapshot()['reserve'][0]['id']
        staging.save_submission(reserve_id,'War submission')
        staging.add_to_hot(['a'])
        staging.confirm_hot()
        reserve=staging.snapshot()['reserve'][0]
        self.assertEqual(reserve['submission'],'War submission')
        self.assertEqual(reserve['items'][0]['id'],'b')
        self.assertEqual(reserve['needs_review'],1)
        self.assertEqual(staging.snapshot()['used_count'],1)
        staging.acknowledge(reserve_id)
        self.assertEqual(staging.snapshot()['reserve'][0]['needs_review'],0)
        staging.add_to_hot(['c'])
        staging.activate(reserve_id)
        self.assertEqual(staging.snapshot()['hot']['id'],reserve_id)
        self.assertEqual(len(staging.snapshot()['reserve']),1)
        staging.restore(['a'])
        self.assertEqual(staging.snapshot()['used_count'],0)

    def test_missing_replacement_and_no_duplicate_in_package(self):
        staging.add_to_hot(['a','b','c'])
        staging.reserve_hot()
        staging.add_to_hot(['a'])
        staging.confirm_hot()
        reserve=staging.snapshot()['reserve'][0]
        self.assertEqual(reserve['missing_count'],1)
        self.assertEqual(reserve['needs_review'],1)
        staging.activate(reserve['id'])
        with self.assertRaisesRegex(ValueError,'Resolve missing'):
            staging.confirm_hot()
        staging.remove_from_hot('a')
        self.assertEqual(staging.snapshot()['hot']['missing_count'],0)
        staging.confirm_hot()
        self.assertEqual(staging.snapshot()['used_count'],3)

    def test_hot_limit_is_atomic(self):
        con=db()
        for n in range(11):
            aid=f'extra-{n}'
            con.execute('''insert into assets(id,relpath,sha256,branch,type,creator,seq,width,height,source_format,status)
              values(?,?,?,?,?,?,?,?,?,?,?)''',(aid,f'{aid}.png',aid,'ar','mbt','taco',n,100,100,'PNG','ready'))
        con.commit();con.close()
        staging.add_to_hot([f'extra-{n}' for n in range(10)])
        staging.add_to_hot(['extra-0'])
        with self.assertRaisesRegex(ValueError,'full'):
            staging.add_to_hot(['extra-10'])
        self.assertEqual(len(staging.snapshot()['hot']['items']),10)

    def test_stale_hot_package_cannot_move_a_new_package(self):
        staging.add_to_hot(['a'])
        old_id=staging.snapshot()['hot']['id']
        staging.reserve_hot(old_id)
        staging.add_to_hot(['b'])
        with self.assertRaisesRegex(ValueError,'Hot package changed'):
            staging.reserve_hot(old_id)
        self.assertEqual(staging.snapshot()['hot']['items'][0]['id'],'b')

    def test_mobile_confirmation_requires_the_copied_package_contents(self):
        staging.add_to_hot(['a'])
        package_id=staging.snapshot()['hot']['id']
        staging.add_to_hot(['b'])
        with self.assertRaisesRegex(ValueError,'contents changed'):
            staging.confirm_hot(package_id,['a'])
        with self.assertRaisesRegex(ValueError,'Hot package changed'):
            staging.confirm_hot('stale-package',['a','b'])
        self.assertEqual(staging.snapshot()['used_count'],0)
        self.assertEqual(len(staging.snapshot()['hot']['items']),2)
        staging.confirm_hot(package_id,['a','b'])
        self.assertIsNone(staging.snapshot()['hot'])
        self.assertEqual(staging.snapshot()['used_count'],2)

    def test_hidden_creator_is_not_selectable_or_counted_as_used(self):
        staging.add_to_hot(['a'])
        staging.confirm_hot()
        self.assertEqual(staging.snapshot()['used_count'],1)
        con=db()
        con.execute("update creators set enabled=0 where name='taco'")
        con.commit();con.close()
        self.assertEqual(staging.snapshot()['used_count'],0)
        with self.assertRaisesRegex(ValueError,'unavailable'):
            staging.add_to_hot(['b'])
        con=db()
        con.execute("update creators set enabled=1 where name='taco'")
        con.commit();con.close()
        self.assertEqual(staging.snapshot()['used_count'],1)

    def test_deployment_undo_restores_hot_used_and_replenished_reserve(self):
        staging.add_to_hot(['a'])
        staging.reserve_hot()
        original=staging.snapshot()['reserve'][0]
        staging.add_to_hot(['a'])
        hot_id=staging.snapshot()['hot']['id']
        staging.confirm_hot()
        self.assertEqual(staging.snapshot()['reserve'][0]['items'][0]['id'],'b')
        self.assertTrue(staging.snapshot()['can_undo'])
        db().close()  # Recovery data survives reopening the database.
        staging.undo_last_deployment()
        restored=staging.snapshot()
        self.assertEqual(restored['hot']['id'],hot_id)
        self.assertEqual(restored['reserve'][0]['items'][0]['id'],original['items'][0]['id'])
        self.assertEqual(restored['reserve'][0]['needs_review'],original['needs_review'])
        self.assertEqual(restored['used_count'],0)
        self.assertFalse(restored['can_undo'])

    def test_deployment_undo_rejects_later_staging_changes(self):
        staging.add_to_hot(['a'])
        staging.confirm_hot()
        staging.add_to_hot(['b'])
        with self.assertRaisesRegex(ValueError,'changed since deployment'):
            staging.undo_last_deployment()
        self.assertEqual(staging.snapshot()['used_count'],1)

if __name__=='__main__':unittest.main()
