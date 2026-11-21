import sqlite3
import tempfile
import unittest
from pathlib import Path

from desktop_data import migrate


class DesktopMigrationTests(unittest.TestCase):
    def test_copies_database_and_images_without_changing_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            legacy = base / 'old'
            legacy.mkdir()
            with sqlite3.connect(legacy / 'app.sqlite') as con:
                con.execute('create table state(value text)')
                con.execute('insert into state values (?)', ('staged',))
            (legacy / 'formatted').mkdir()
            (legacy / 'formatted' / 'sample.jpg').write_bytes(b'fixture')
            target = base / 'xdg' / 'clan-hub-crea-manager'
            migrate(legacy, target)
            with sqlite3.connect(target / 'app.sqlite') as con:
                self.assertEqual(con.execute('select value from state').fetchone()[0], 'staged')
            self.assertEqual((target / 'formatted' / 'sample.jpg').read_bytes(), b'fixture')
            self.assertEqual((legacy / 'formatted' / 'sample.jpg').read_bytes(), b'fixture')
            migrate(legacy, target)


if __name__ == '__main__':
    unittest.main()
