"""Select active profiles and share their connections across directions."""
from contextlib import closing
import threading
import json
import re

from crea_core import DATA, db
from .core.mentions import directory
from .config import load_environment
from .connection import BotConnection
from .incoming.discord_bot import DiscordBotIncoming
from .outgoing.discord_bot import DiscordBotWriteProvider
from .outgoing.disabled import DisabledWriteProvider
from .user_connection import UserConnection
from .profiles import load_profiles, resolve_credential


class ConnectionManager:
    def __init__(self, factory=BotConnection):
        self.factory = factory
        self.lock = threading.RLock()
        self.profiles = {}
        self.active = {'read': '', 'write': ''}
        self.connections = {}
        self.readers = {}
        self.errors = {}
        self.config_error = ''
        self.generation = 0
        self.read_identity = None
        self.destinations = {}

    def start(self):
        with self.lock, closing(db()) as con:
            self.reload()
            saved = dict(con.execute("select key,value from app_settings where key like 'discord_active_%'"))
            self.destinations = {row['key'].removeprefix('discord_destination:'): json.loads(row['value'])
                                 for row in con.execute("select key,value from app_settings where key like 'discord_destination:%'")}
            for direction in self.active:
                fallback = f'legacy_{direction}'
                self.active[direction] = saved.get(f'discord_active_{direction}', self.settings.get(
                    f'DISCORD_ACTIVE_{direction.upper()}_PROFILE', fallback if fallback in self.profiles else ''))
            self.apply()

    def reload(self):
        self.settings = load_environment()
        try:
            self.profiles = load_profiles(DATA / 'communications-profiles.toml', self.settings)
            self.config_error = ''
        except (ValueError, OSError) as exc:
            self.config_error = str(exc) if isinstance(exc, ValueError) else 'Connection profiles are inaccessible'

    def select(self, read, write):
        with self.lock, closing(db()) as con:
            for direction, profile_id in [('read', read), ('write', write)]:
                if not isinstance(profile_id, str) or (profile_id and not self.valid(profile_id, direction)):
                    raise ValueError(f'Invalid {direction} profile')
            with con:
                con.executemany('insert or replace into app_settings(key,value) values (?,?)',
                                [('discord_active_read', read), ('discord_active_write', write)])
            self.active = {'read': read, 'write': write}
            self.apply()
            return self.status()

    def select_shared(self, profile_id):
        with self.lock:
            if not isinstance(profile_id, str) or (profile_id and not self.valid(profile_id, 'read')):
                raise ValueError('Select an incoming Discord profile')
            return self.select(profile_id, profile_id if self.valid(profile_id, 'write') else '')

    def valid(self, profile_id, direction):
        profile = self.profiles.get(profile_id)
        return profile and getattr(profile, f'{direction}_enabled')

    def reconnect(self, profile_id):
        with self.lock:
            if not profile_id or profile_id not in self.active.values():
                raise ValueError('Select an active profile to reconnect')
            self.reload()
            if not self.config_error:
                self.remove(profile_id)
                self.apply()
            return self.status()

    def remove(self, profile_id):
        entry = self.connections.pop(profile_id, None)
        if entry:
            entry[0].stop()

    def stop(self):
        with self.lock:
            for profile_id in list(self.connections):
                self.remove(profile_id)

    def apply(self):
        desired = {pid for direction, pid in self.active.items() if self.valid(pid, direction)}
        for pid in list(self.connections):
            if pid not in desired or self.connections[pid][1] != self.profiles[pid]:
                self.remove(pid)
        self.errors = {}
        for pid in desired - self.connections.keys():
            profile = self.profiles[pid]
            try:
                token = resolve_credential(profile, self.settings)
                if profile.provider == 'discord_user':
                    connection = UserConnection(profile, token, DATA, self.destinations.get(pid))
                    self.connections[pid] = (connection, profile, None)
                    connection.start()
                    continue
                connection = self.factory(token, profile.read_enabled)
            except (ValueError, ImportError) as exc:
                self.errors[pid] = str(exc) if isinstance(exc, ValueError) else 'discord.py is unavailable'
                continue
            reader = None
            if profile.read_enabled:
                guild_id, channel_id = self.destinations.get(pid, (profile.guild_id, profile.channel_id))
                reader = DiscordBotIncoming({'DISCORD_GUILD_ID': guild_id,
                                            'DISCORD_COMBAT_CHANNEL_ID': channel_id})
                old = self.readers.get(pid)
                if old and old.guild_id == profile.guild_id:
                    with old.lock:
                        reader.events.extend(old.events)
                        reader.messages.update(old.messages)
                        reader.sequence = old.sequence
                self.readers[pid] = reader
            self.connections[pid] = (connection, profile, reader)

            if reader:
                reader.bind(connection.client)
            connection.start()

        read_identity = (self.active['read'], self.connections.get(self.active['read']))
        if read_identity != self.read_identity:
            self.generation += 1
            self.read_identity = read_identity

    def connection_status(self, pid):
        entry = self.connections.get(pid)
        if not entry:
            return {'state': 'unconfigured' if pid else 'disabled',
                    'reason': self.errors.get(pid, 'Profile unavailable' if pid else 'Disabled')}
        connection, profile, _ = entry
        if profile.provider == 'discord_user':
            return {'state': connection.state, 'reason': connection.reason,
                    'guild_id': profile.guild_id, 'account': connection.account}
        user = connection.client.user
        return {'state': connection.state, 'reason': connection.reason, 'guild_id': profile.guild_id,
                'account': {'id': str(user.id), 'name': user.name} if user else None}

    def destination_options(self):
        with self.lock:
            pid = self.active['read']
            profile = self.profiles.get(pid)
            entry = self.connections.get(pid)
            selected = self.destinations.get(pid) or ([profile.guild_id, profile.channel_id] if profile else ['', ''])
            guilds = []
            if entry and entry[0].state == 'connected':
                connection, profile, reader = entry
                if profile.provider == 'discord_user':
                    guilds = connection.guild_options()
                elif reader:
                    guilds = reader.guild_options()
            guilds.sort(key=lambda guild: guild['name'].casefold())
            return {'profile_id': pid, 'guild_id': selected[0], 'channel_id': selected[1], 'guilds': guilds}

    def select_destination(self, profile_id, guild_id, channel_id):
        if any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,24}', value)
               for value in (guild_id, channel_id)):
            raise ValueError('Select a server and channel')
        with self.lock:
            options = self.destination_options()
            if profile_id != options['profile_id']:
                raise ValueError('The incoming profile changed. Refresh Settings.')
            guild = next((item for item in options['guilds'] if item['id'] == guild_id), None)
            if not guild or not any(channel['id'] == channel_id for channel in guild['channels']):
                raise ValueError('The active profile cannot view this channel')
            connection, profile, reader = self.connections[profile_id]
            changed = self.destinations.get(profile_id) != [guild_id, channel_id]
            if changed and profile.provider == 'discord_user':
                connection.set_read_destination(guild_id, channel_id)
            with closing(db()) as con, con:
                con.execute('insert or replace into app_settings(key,value) values(?,?)',
                            (f'discord_destination:{profile_id}', json.dumps([guild_id, channel_id])))
            if changed:
                self.destinations[profile_id] = [guild_id, channel_id]
                if reader:
                    with reader.lock:
                        reader.guild_id, reader.start_channel = guild_id, channel_id
                self.generation += 1
            return self.destination_options()

    def snapshot(self, after=0, channel_id=None):
        with self.lock:
            pid = self.active['read']
            entry = self.connections.get(pid)
            state = self.connection_status(pid)
            if entry and entry[1].provider == 'discord_user':
                value = entry[0].snapshot(after, channel_id)
            elif entry and entry[2]:
                value = entry[2].snapshot(after, channel_id)
                if state['state'] != 'connected':
                    value.update(state=state['state'], reason=state['reason'], channels=[], events=[])
                    value['capabilities']['read'] = False
            else:
                value = {**state, 'channels': [], 'events': [], 'sequence': 0, 'capabilities': {'read': False}}
            if pid in self.destinations:
                guild_id, selected = self.destinations[pid]
                value.update(guild_id=guild_id, start_channel_id=selected)
                value['channels'] = [channel for channel in value['channels'] if channel['guild_id'] == guild_id]
                if value['state'] == 'connected' and not any(c['id'] == selected for c in value['channels']):
                    value['reason'] = 'Selected channel unavailable. Choose another in Settings.'
                value['events'] = [event for event in value['events'] if event['channel_id'] == selected]
            return {**value, 'profile_id': pid, 'generation': self.generation}

    def mention_options(self, guild_id, query):
        if not re.fullmatch(r'[0-9]{1,24}', guild_id) or len(query)>100:
            raise ValueError('Invalid mention search')
        with self.lock:
            entry = self.connections.get(self.active['read'])
            if not entry or entry[0].state != 'connected' or self.snapshot(10**30).get('guild_id') != guild_id:
                return []
            connection, profile, _ = entry
        if profile.provider == 'discord_user':
            return connection.mention_options(guild_id, query)
        return directory(connection.client.get_guild(int(guild_id)), query)

    def history(self, channel_id, before=None, around=None, after=None):
        with self.lock:
            entry = self.connections.get(self.active['read'])
            generation = self.generation
            destination = self.destinations.get(self.active['read'])
        if destination and channel_id != destination[1]:
            return {'error': 'Channel selection changed', 'messages': [], 'generation': generation}
        if entry and entry[1].provider == 'discord_user' and entry[0].state == 'connected':
            return {**entry[0].history(channel_id, before, around, after), 'generation': generation}
        if not entry or not entry[2] or entry[0].state != 'connected':
            return {'error': 'Read connection unavailable', 'messages': [], 'generation': generation}
        return {**entry[2].history(channel_id, before, around, after), 'generation': generation}

    def writer(self, *, configured_test=False):
        with self.lock:
            pid = self.active['write']
            entry = self.connections.get(pid)
            state = self.connection_status(pid)
            if not entry or state['state'] != 'connected':
                return DisabledWriteProvider(state['reason'])
            connection, profile, _ = entry
            feed = self.snapshot(10**30) if not configured_test else None
            destination = None
            if feed:
                selected = feed.get('start_channel_id')
                channels = feed['channels']
                channel = next((item for item in channels if item['id'] == selected), None)
                if not selected and channels:
                    channel = channels[0]
                if feed['state'] != 'connected' or not channel:
                    return DisabledWriteProvider('Choose an accessible channel in Discord Settings')
                destination = (channel['guild_id'], channel['id'])
            guild_id, channel_id = destination or (profile.guild_id, profile.channel_id)
            if profile.provider == 'discord_user':
                return connection.writer(guild_id, channel_id)
            writer = DiscordBotWriteProvider({'DISCORD_GUILD_ID': guild_id,
                                              'DISCORD_WRITE_TEST_CHANNEL_ID': channel_id})
            writer.client = connection.client
            writer.reason = 'The outgoing bot cannot send in this channel'
            return writer

    def status(self):
        with self.lock:
            writer = self.writer()
            value = {'profiles': [p.public() for p in self.profiles.values()], 'active': dict(self.active),
                     'error': self.config_error, 'read': {**self.connection_status(self.active['read']),
                         'feed': {k: v for k, v in self.snapshot(10**30).items() if k != 'events'}},
                     'write': self.connection_status(self.active['write'])}
        value['write']['delivery'] = writer.status()
        return value
