from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from communications.manager import ConnectionManager
from communications.incoming.discord_bot import DiscordBotIncoming
from communications.profiles import load_profiles
import discord_teams


class DiscordWorkspaceTests(TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch('crea_core.DB', root / 'test.sqlite'))
        self.profile_path = root / 'profiles.toml'

    def test_named_destination_changes_feed_and_bot_target(self):
        self.profile_path.write_text(
            '[profiles.main]\nname="Main"\nprovider="discord_bot"\n'
            'token_env="DISCORD_TOKEN"\nguild_id="1"\nchannel_id="11"\nwrite_enabled=true\n')
        guilds = []
        for guild_id, name, channel_id in [(1, 'Alpha', 11), (2, 'Bravo', 22)]:
            guild = SimpleNamespace(id=guild_id, name=name, me=object())
            guild.text_channels = [SimpleNamespace(id=channel_id, guild=guild, name='general',
                permissions_for=lambda _: SimpleNamespace(view_channel=True, read_message_history=True))]
            guilds.append(guild)
        client = SimpleNamespace(guilds=guilds, user=None,
                                 get_guild=lambda gid: next((g for g in guilds if g.id == gid), None))
        manager = ConnectionManager()
        manager.profiles = load_profiles(self.profile_path, {})
        manager.active = {'read':'main', 'write':'main'}
        reader = DiscordBotIncoming({'DISCORD_GUILD_ID':'1', 'DISCORD_COMBAT_CHANNEL_ID':'11'})
        reader.client = client
        reader.state = 'connected'
        manager.connections['main'] = (SimpleNamespace(client=client, state='connected', reason=''),
                                       manager.profiles['main'], reader)
        from dataclasses import replace
        outgoing = replace(manager.profiles['main'], id='outgoing', channel_id='99')
        manager.active['write'] = 'outgoing'
        manager.connections['outgoing'] = (manager.connections['main'][0], outgoing, None)
        self.assertEqual(manager.writer().channel_id, '11')
        self.assertEqual(manager.writer(configured_test=True).channel_id, '99')
        options = manager.destination_options()
        self.assertEqual([guild['name'] for guild in options['guilds']], ['Alpha', 'Bravo'])
        with self.assertRaisesRegex(ValueError, 'cannot view'):
            manager.select_destination('main', '1', '22')
        with self.assertRaisesRegex(ValueError, 'profile changed'):
            manager.select_destination('another', '2', '22')
        manager.select_destination('main', '2', '22')
        self.assertEqual(manager.snapshot()['start_channel_id'], '22')
        self.assertEqual(manager.snapshot()['generation'], 1)
        self.assertEqual(manager.writer().channel_id, '22')
        self.assertEqual(manager.history('11')['error'], 'Channel selection changed')
        self.assertEqual(manager.select_destination('main', '2', '22')['channel_id'], '22')
        self.assertEqual(manager.snapshot()['generation'], 1)
        mgr_on_restart = ConnectionManager()
        with patch.object(mgr_on_restart, 'reload', side_effect=lambda: setattr(mgr_on_restart, 'settings', {})):
            mgr_on_restart.start()
        self.assertEqual(mgr_on_restart.destinations['main'], ['2','22'])

    def test_shared_profile_without_configured_guild(self):
        self.profile_path.write_text(
            '[profiles.main]\nname="Main"\nprovider="discord_bot"\n'
            'token_env="DISCORD_TOKEN"\nwrite_enabled=true\n')
        profile = load_profiles(self.profile_path, {})['main']
        self.assertEqual(profile.guild_id, '')
        manager = ConnectionManager()
        manager.profiles = {'main': profile}
        with patch.object(manager, 'apply'):
            manager.select_shared('main')
        self.assertEqual(manager.active, {'read': 'main', 'write': 'main'})

    def test_active_threads_are_listed_only_when_visible(self):
        guild = SimpleNamespace(id=1, me=object(), text_channels=[])
        permissions = SimpleNamespace(view_channel=True, read_message_history=True, manage_threads=False)
        def thread(thread_id, private, membership):
            return SimpleNamespace(id=thread_id, guild=guild, name=str(thread_id), parent_id=10,
                                   is_private=lambda: private, me=membership, permissions_for=lambda _: permissions)
        guild.threads = [thread(11, False, None), thread(12, True, None), thread(13, True, object())]
        self.assertEqual([channel['id'] for channel in DiscordBotIncoming.visible_channels(guild)], ['11','13'])

    def test_user_writer_keeps_the_selected_channel_in_all_worker_operations(self):
        from unittest.mock import Mock
        from communications.user_connection import UserChannelWriter
        manager = ConnectionManager()
        manager.active = {'read': 'profile', 'write': 'profile'}
        worker = Mock(state='connected', reason='', account={'id': '42'})
        profile = SimpleNamespace(provider='discord_user', guild_id='1', channel_id='11')
        manager.connections['profile'] = (worker, profile, None)
        worker.snapshot.return_value = {'state': 'connected', 'channels': [{'id': '22', 'guild_id': '2'}],
                                        'start_channel_id': '22', 'events': []}
        worker.writer.side_effect = lambda guild, channel: UserChannelWriter(worker, guild, channel)
        worker.request.side_effect = [{'capabilities': {'react': True}}, {'ok': True}, {'ok': True}]
        writer = manager.writer()
        self.assertEqual(writer.status()['provider'], 'discord_user')
        self.assertTrue(writer.send('draft', 'Hello', [])['ok'])
        self.assertTrue(writer.add_reaction('3', '🔥')['ok'])
        self.assertEqual([call.args[:2] for call in worker.request.call_args_list], [
            ('write_status', ['2', '22']), ('send', ['2', '22', 'draft', 'Hello', [], '', None]),
            ('react', ['2', '22', '3', '🔥']),
        ])
        self.assertEqual(manager.writer(configured_test=True).destination, ('1', '11'))

    def test_team_assignment_moves_and_is_scoped_to_server(self):
        discord_teams.assign('1', '42', 'Alice', 'blue')
        discord_teams.assign('1', '42', 'Alice', 'red')
        discord_teams.assign('2', '42', 'Alice', 'yellow')
        self.assertEqual(discord_teams.members('1'), [{'user_id':'42', 'name':'Alice', 'team':'red'}])
        with self.assertRaises(ValueError):
            discord_teams.assign('1', '42', 'Alice', 'green')
        self.assertEqual(discord_teams.assign('1', '42', 'Alice', None), [])
        self.assertEqual(discord_teams.members('2')[0]['team'], 'yellow')
