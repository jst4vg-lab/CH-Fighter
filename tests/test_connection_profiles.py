import tempfile
import unittest
from pathlib import Path
from communications.profiles import load_profiles, resolve_credential


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'profiles.toml'

    def test_legacy_preserves_separate_credentials(self):
        values = {'DISCORD_READ_BOT_TOKEN': 'read-secret', 'DISCORD_WRITE_PROVIDER': 'discord_bot', 'DISCORD_WRITE_BOT_TOKEN': 'write-secret'}
        profiles = load_profiles(self.path, values)
        self.assertEqual(resolve_credential(profiles['legacy_read'], values), 'read-secret')
        self.assertEqual(resolve_credential(profiles['legacy_write'], values), 'write-secret')
        self.assertNotIn('secret', str([p.public() for p in profiles.values()]))

    def test_named_profile_and_missing_credentials(self):
        self.path.write_text('[profiles.shared]\nname="Shared"\nprovider="discord_bot"\ntoken_env="BOT_TOKEN"\nguild_id="123"\nwrite_enabled=true\n')
        profile = load_profiles(self.path, {})['shared']
        self.assertTrue(profile.read_enabled and profile.write_enabled)
        with self.assertRaisesRegex(ValueError, 'BOT_TOKEN'):
            resolve_credential(profile, {})

    def test_credentials_and_invalid_flags_rejected(self):
        base = '[profiles.test]\nname="Test"\nprovider="discord_bot"\ntoken_env="BOT_TOKEN"\nguild_id="123"\n'
        for extra in ('token="secret"', 'read_enabled="yes"', 'channel_id="bad"'):
            self.path.write_text(base + extra)
            with self.assertRaises(ValueError):
                load_profiles(self.path, {})

    def test_invalid_toml_sanitized(self):
        self.path.write_text('token="secret')
        with self.assertRaises(ValueError) as error:
            load_profiles(self.path, {})
        self.assertNotIn('secret', str(error.exception))


class ManagerTests(unittest.TestCase):
    def test_share_switch_reconnect_and_persist(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from communications.manager import ConnectionManager

        class Client(SimpleNamespace):
            def get_guild(self, guild_id):
                return None

            def event(self, handler):
                setattr(self, handler.__name__, handler)

        class Connection:
            state = 'connecting'
            reason = ''
            def __init__(self, token, read):
                self.client = Client(user=None)
                self.stopped = False
            def start(self):
                pass
            def stop(self):
                self.stopped = True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'communications-profiles.toml').write_text(''.join(
                f'[profiles.{pid}]\nname="{pid}"\nprovider="discord_bot"\ntoken_env="BOT_TOKEN"\nguild_id="123"\nwrite_enabled=true\n'
                for pid in ('first', 'second')))
            with patch('communications.manager.DATA', root), patch('crea_core.DB', root / 'db'), patch(
                'communications.manager.load_environment', return_value={'BOT_TOKEN': 'fixture'}
            ):
                manager = ConnectionManager(Connection)
                manager.start()
                manager.select('first', 'first')
                original = manager.connections['first'][0]
                self.assertEqual(len(manager.connections), 1)
                manager.select('first', 'second')
                self.assertEqual(len(manager.connections), 2)
                self.assertIs(manager.connections['first'][0], original)
                manager.reconnect('first')
                self.assertTrue(original.stopped)
                self.assertIsNot(manager.connections['first'][0], original)
                manager.stop()
                manager.start()
                self.assertEqual(manager.active, {'read': 'first', 'write': 'second'})
                manager.stop()

class UserProfileTests(unittest.TestCase):
    def test_example_and_optional_default_destination(self):
        example = Path(__file__).resolve().parents[1] / 'communications-profiles.example.toml'
        profiles = load_profiles(example, {})
        user = profiles['user']
        self.assertEqual(user.provider, 'discord_user')
        self.assertEqual(user.token_env, 'DISCORD_USER_TOKEN')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profiles.toml'
            path.write_text(example.read_text().rsplit(f'channel_id = "{user.channel_id}"', 1)[0] + 'read_enabled = true\nwrite_enabled = true\n')
            self.assertEqual(load_profiles(path, {})['user'].channel_id, '')

    def test_missing_worker_leaves_bot_selected(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from communications.manager import ConnectionManager

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = Path(__file__).resolve().parents[1] / 'communications-profiles.example.toml'
            settings = {'DISCORD_READ_BOT_TOKEN': 'fixture', 'DISCORD_USER_TOKEN': 'fixture'}
            manager = ConnectionManager(lambda *_: SimpleNamespace(
                client=SimpleNamespace(user=None, event=lambda callback: callback),
                state='connecting', reason='', start=lambda: None))
            manager.profiles = load_profiles(example, settings)
            manager.settings = settings
            manager.active = {'read': 'bot', 'write': 'user'}
            with patch('communications.manager.DATA', root):
                manager.apply()
            self.assertIn('bot', manager.connections)
            self.assertIn('dedicated', manager.connection_status('user')['reason'])
