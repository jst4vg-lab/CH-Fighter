"""Manage the isolated Discord user worker and its normalized data."""
from collections import deque
from concurrent.futures import Future, TimeoutError
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


class UserConnection:
    def __init__(self, profile, token, data, destination=None):
        self.profile = profile
        self.state, self.reason = 'connecting', ''
        self.account = None
        self.terminal = False
        self.feed = {}
        self.guilds = []
        self.events = deque(maxlen=1000)
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.pending = {}
        self.ids = itertools.count(1)
        python = data / 'discord-self-venv/bin/python'
        root = Path(sys.executable).parent.parent / 'discord-worker' if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
        env = {key: os.environ[key] for key in ('HOME', 'PATH', 'LANG', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if key in os.environ}
        library_path = os.environ.get('LD_LIBRARY_PATH_ORIG' if getattr(sys, 'frozen', False) else 'LD_LIBRARY_PATH')
        if library_path:
            env['LD_LIBRARY_PATH'] = library_path
        try:
            self.process = subprocess.Popen(
                [str(python), '-E', '-s', '-m', 'communications.user_worker'],
                cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            )
            self.write({'token': token, 'read_enabled': profile.read_enabled, 'write_enabled': profile.write_enabled,
                        'read_destination': destination,
                        'DISCORD_GUILD_ID': profile.guild_id,
                        'DISCORD_COMBAT_CHANNEL_ID': profile.channel_id,
                        'DISCORD_WRITE_TEST_CHANNEL_ID': profile.channel_id if profile.write_enabled else ''})
        except OSError:
            if hasattr(self, 'process'):
                self.stop()
            raise ValueError('Set up the dedicated Discord user worker environment') from None

    def write(self, value):
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def start(self):
        self.receiver = threading.Thread(target=self.receive, daemon=True)
        self.receiver.start()
        threading.Thread(target=self.poll, daemon=True).start()

    def receive(self):
        try:
            for line in self.process.stdout:
                value = json.loads(line)
                with self.lock:
                    if 'id' in value:
                        future = self.pending.pop(value['id'], None)
                        if future:
                            future.set_result(value['result'])
                    else:
                        self.state, self.reason = value['state'], value['reason']
                        self.terminal = True
        finally:
            self.process.stdout.close()
            with self.lock:
                if not self.terminal:
                    self.state, self.reason = 'disconnected', 'Discord user worker stopped'
                self.closed.set()
                for future in self.pending.values():
                    future.set_result({})
                self.pending.clear()

    def request(self, operation, args, timeout):
        future = Future()
        with self.lock:
            if self.closed.is_set():
                return {}
            request_id = next(self.ids)
            self.pending[request_id] = future
            try:
                self.write({'id': request_id, 'operation': operation, 'args': args})
            except (OSError, ValueError):
                self.pending.pop(request_id, None)
                return {}
        try:
            return future.result(timeout)
        except TimeoutError:
            with self.lock:
                self.pending.pop(request_id, None)
            return {}

    def poll(self):
        while not self.closed.is_set():
            result = self.request('poll', [self.feed.get('sequence', 0)], 5)
            if 'feed' in result:
                with self.lock:
                    if not self.terminal and not self.closed.is_set():
                        self.state = result['state']
                    self.account = result['account']
                    self.guilds = result.get('guilds', [])
                    self.feed = result['feed']
                    self.events.extend(self.feed.pop('events', []))
            self.closed.wait(0.5)

    def snapshot(self, after, channel_id):
        with self.lock:
            visible = {c['id'] for c in self.feed.get('channels', [])}
            events = [e for e in self.events if e['sequence'] > after and e['channel_id'] in visible
                      and (channel_id is None or e['channel_id'] == channel_id)]
            return {**self.feed, 'guild_id': self.feed.get('guild_id', self.profile.guild_id), 'state': self.state,
                    'reason': self.reason or self.feed.get('reason', ''), 'channels': self.feed.get('channels', []) if self.state == 'connected' else [],
                    'events': events if self.state == 'connected' else [],
                    'sequence': self.feed.get('sequence', 0),
                    'capabilities': self.feed.get('capabilities', {}) if self.state == 'connected' else {'read': False}}

    def guild_options(self):
        with self.lock:
            return list(self.guilds)

    def set_read_destination(self, guild_id, channel_id):
        response = self.request('read_destination', [guild_id, channel_id], 5)
        if not response.get('ok'):
            raise ValueError(response.get('error') or 'The incoming profile could not switch channels')

    def mention_options(self, guild_id, query):
        return self.request('mentions', [guild_id, query], 4).get('items', [])

    def history(self, channel_id, before=None, around=None, after=None):
        result = self.request('history', [channel_id, before, around, after], 17)
        return result if 'messages' in result else {'messages': [], 'error': 'Read connection unavailable'}

    def writer(self, guild_id, channel_id):
        return UserChannelWriter(self, guild_id, channel_id)

    def stop(self):
        self.closed.set()
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdin.close()
        if not hasattr(self, 'receiver'):
            self.process.stdout.close()

class UserChannelWriter:
    """Keep permission checks and outgoing actions pinned to one channel."""
    def __init__(self, connection, guild_id, channel_id):
        self.connection = connection
        self.destination = (guild_id, channel_id)

    def status(self):
        result = self.connection.request('write_status', list(self.destination), 4)
        if 'capabilities' in result:
            return {**result, 'provider': 'discord_user'}
        return {'provider': 'discord_user', 'state': 'unavailable',
                'reason': 'The outgoing profile is unavailable',
                'capabilities': {'send': False, 'attach': False, 'reply': False, 'react': False}}

    def send(self, draft_id, content, paths, reply_to_id='', mentions=None):
        result = self.connection.request('send', [
            *self.destination, draft_id, content, list(map(str, paths)), reply_to_id, mentions], 47)
        if 'ok' in result:
            return result
        return {'ok': False, 'code': 'unverified',
                'error': 'Delivery outcome unknown. Check Discord before sending again.'}

    def add_reaction(self, message_id, emoji):
        result = self.connection.request('react', [*self.destination, message_id, emoji], 17)
        if 'ok' in result:
            return result
        return {'ok': False, 'error': 'Discord did not confirm the reaction. Check the message before retrying.'}
