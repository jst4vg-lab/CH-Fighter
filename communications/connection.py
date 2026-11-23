"""Own the Discord client, worker loop, and authentication lifecycle."""
import asyncio
from importlib.metadata import PackageNotFoundError, version
import threading


class BotConnection:
    def __init__(self, token, read):
        try:
            version('discord.py-self')
        except PackageNotFoundError:
            pass
        else:
            raise ValueError('Install only discord.py in the bot backend environment')
        import discord
        self.token = token
        self.discord = discord
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = intents.guild_reactions = intents.message_content = read
        self.client = discord.Client(intents=intents)
        self.state, self.reason = 'connecting', 'Connecting to Discord'
        self.loop = self.task = None
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

        @self.client.event
        async def on_ready():
            self.state, self.reason = 'connected', ''

        @self.client.event
        async def on_disconnect():
            if not self.closed.is_set():
                self.state, self.reason = 'reconnecting', 'Reconnecting to Discord'

        @self.client.event
        async def on_resumed():
            self.state, self.reason = 'connected', ''

    def run(self):
        async def connect():
            async with self.client:
                self.loop = asyncio.get_running_loop()
                self.task = asyncio.current_task()
                if not self.closed.is_set():
                    await self.client.start(self.token)
        try:
            asyncio.run(connect())
        except self.discord.LoginFailure:
            self.state, self.reason = 'authentication_failed', 'Discord rejected the bot credential'
        except self.discord.PrivilegedIntentsRequired:
            self.state, self.reason = 'permission_limited', 'Enable Message Content intent in the Discord Developer Portal'
        except Exception:
            self.state, self.reason = 'disconnected', 'Discord connection failed'
        finally:
            if self.closed.is_set():
                self.state, self.reason = 'disconnected', 'Connection closed'

    def start(self):
        self.thread.start()

    def stop(self):
        self.closed.set()
        if self.loop and self.task:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass
        self.thread.join(timeout=5)
