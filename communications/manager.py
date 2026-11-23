"""Select active profiles and share their connections across directions."""
from contextlib import closing
import threading

from crea_core import DATA, db
from .config import load_environment
from .connection import BotConnection
from .incoming.discord_bot import DiscordBotIncoming
from .outgoing.discord_bot import DiscordBotWriteProvider
from .outgoing.disabled import DisabledWriteProvider
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

    def start(self):
        with self.lock, closing(db()) as con:
            self.reload()
            saved = dict(con.execute("select key,value from app_settings where key like 'discord_active_%'"))
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
                if not profile.guild_id.isdigit():
                    raise ValueError('Configure a valid Discord guild ID')
                token = resolve_credential(profile, self.settings)
                connection = self.factory(token, profile.read_enabled)
            except (ValueError, ImportError) as exc:
                self.errors[pid] = str(exc) if isinstance(exc, ValueError) else 'discord.py is unavailable'
                continue
            reader = None
            if profile.read_enabled:
                reader = DiscordBotIncoming({'DISCORD_GUILD_ID': profile.guild_id,
                                            'DISCORD_COMBAT_CHANNEL_ID': profile.channel_id})
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
        user = connection.client.user
        return {'state': connection.state, 'reason': connection.reason, 'guild_id': profile.guild_id,
                'account': {'id': str(user.id), 'name': user.name} if user else None}

    def snapshot(self, after=0, channel_id=None):
        with self.lock:
            pid = self.active['read']
            entry = self.connections.get(pid)
            state = self.connection_status(pid)
            if entry and entry[2]:
                value = entry[2].snapshot(after, channel_id)
                if state['state'] != 'connected':
                    value.update(state=state['state'], reason=state['reason'], channels=[], events=[])
                    value['capabilities']['read'] = False
            else:
                value = {**state, 'channels': [], 'events': [], 'sequence': 0, 'capabilities': {'read': False}}
            return {**value, 'profile_id': pid, 'generation': self.generation}

    def history(self, channel_id, before=None):
        with self.lock:
            entry = self.connections.get(self.active['read'])
            generation = self.generation
        if not entry or not entry[2] or entry[0].state != 'connected':
            return {'error': 'Read connection unavailable', 'messages': [], 'generation': generation}
        return {**entry[2].history(channel_id, before), 'generation': generation}

    def writer(self):
        with self.lock:
            pid = self.active['write']
            entry = self.connections.get(pid)
            state = self.connection_status(pid)
            if not entry or state['state'] != 'connected':
                return DisabledWriteProvider(state['reason'])
            connection, profile, _ = entry
            writer = DiscordBotWriteProvider({'DISCORD_GUILD_ID': profile.guild_id,
                                              'DISCORD_WRITE_TEST_CHANNEL_ID': profile.channel_id})
            writer.client = connection.client
            writer.reason = 'Test channel missing or bot lacks send permission'
            return writer

    def status(self):
        with self.lock:
            return {'profiles': [p.public() for p in self.profiles.values()], 'active': dict(self.active),
                    'error': self.config_error, 'read': {**self.connection_status(self.active['read']),
                                                        'feed': {k: v for k, v in self.snapshot(10**30).items() if k != 'events'}},
                    'write': {**self.connection_status(self.active['write']), 'delivery': self.writer().status()}}
