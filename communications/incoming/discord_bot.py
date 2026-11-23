"""Authorized Discord bot incoming provider."""
import asyncio
import logging
from itertools import chain

logger = logging.getLogger(__name__)
from .. import config
from ..core.channels import can_view_channel, normalize_channel
from ..core.messages import MessageEventStore
from ..core.normalization import normalize

class DiscordBotIncoming(MessageEventStore):
    def __init__(self,settings=None):
        super().__init__(); self.settings=settings or config()
        self.channels=[]; self.state='unavailable'; self.reason='Read bot is not configured'; self.client=None
        self.guild_id=self.settings.get('DISCORD_GUILD_ID',''); self.start_channel=self.settings.get('DISCORD_COMBAT_CHANNEL_ID','')

    @staticmethod
    def visible_channels(guild):
        if not guild or not guild.me:
            return []
        return [{**normalize_channel(channel), 'history': permissions.read_message_history,
                 'thread': getattr(channel, 'parent_id', None) is not None}
                for channel in chain(guild.text_channels, getattr(guild, 'threads', ()))
                if can_view_channel(channel, permissions := channel.permissions_for(guild.me))]

    def guild_options(self):
        return [{'id': str(guild.id), 'name': guild.name,
                 'channels': sorted(self.visible_channels(guild), key=lambda channel: channel['name'].casefold())}
                for guild in getattr(self.client, 'guilds', ())]

    def snapshot(self,after=0,channel_id=None):
        guild = self.client.get_guild(int(self.guild_id)) if self.client and self.guild_id.isdigit() else None
        channels = self.visible_channels(guild)
        visible = {c['id'] for c in channels}
        with self.lock:
            return {'state':self.state,'reason':self.reason,'guild_id':self.guild_id,'guild_name':getattr(guild, 'name', None),'start_channel_id':self.start_channel,
                    'channels':channels,'capabilities':{'read':self.state=='connected' and bool(channels),'history':any(c['history'] for c in channels),'send':False,'reply':False,'attach':False,'react':False},
                    'sequence':self.sequence,'events':[e for e in self.events if e['sequence']>after and (not self.client or e['channel_id'] in visible) and (channel_id is None or e['channel_id']==channel_id)]}

    def start(self):
        # Kept for callers that use a standalone, disabled store.
        if self.settings.get('DISCORD_READ_PROVIDER') == 'disabled':
            self.reason = 'Read provider disabled'

    def bind(self, client):
        self.client = client
        hub = self
        previous_ready = getattr(client, 'on_ready', None)
        @client.event
        async def on_ready():
            if previous_ready:
                await previous_ready()
            with hub.lock:
                hub.state='connected';hub.reason=''
        @client.event
        async def on_message(message):
            if message.guild and str(message.guild.id)==hub.guild_id:
                hub.publish('upsert',message.channel.id,message.id,normalize(message))
        @client.event
        async def on_raw_message_delete(event):
            if str(event.guild_id)==hub.guild_id:hub.publish('delete',event.channel_id,event.message_id)
        @client.event
        async def on_raw_message_edit(event):
            if str(event.guild_id)!=hub.guild_id:return
            channel=client.get_channel(event.channel_id)
            if channel:
                try: hub.publish('upsert',event.channel_id,event.message_id,normalize(await channel.fetch_message(event.message_id)))
                except Exception as exc: logger.debug("Discord message refresh failed: %s", type(exc).__name__)
        @client.event
        async def on_raw_reaction_add(event): await refresh_reaction(event)
        @client.event
        async def on_raw_reaction_remove(event): await refresh_reaction(event)
        async def refresh_reaction(event):
            if str(event.guild_id)!=hub.guild_id:return
            channel=client.get_channel(event.channel_id)
            if channel:
                try: hub.publish('upsert',event.channel_id,event.message_id,normalize(await channel.fetch_message(event.message_id)))
                except Exception as exc: logger.debug("Discord message refresh failed: %s", type(exc).__name__)
    def history(self, channel_id, before=None, around=None, after=None, limit=50):
        if self.state!='connected': return {'error':self.reason,'messages':[]}
        channel=self.client.get_channel(int(channel_id)) if channel_id.isdigit() else None
        guild = getattr(channel, 'guild', None)
        if not guild or str(guild.id) != self.guild_id or not guild.me or not hasattr(channel, 'history'):
            return {'error': 'Channel unavailable', 'messages': []}
        permissions = channel.permissions_for(guild.me)
        if not can_view_channel(channel, permissions) or not permissions.read_message_history:
            return {'error': 'Channel history unavailable', 'messages': []}
        import asyncio, discord
        async def get():
            cursors = {key: discord.Object(id=int(value)) for key, value in
                       [('before', before), ('around', around), ('after', after)] if value}
            return [normalize(message) async for message in channel.history(
                limit=min(limit, 100), oldest_first=bool(after), **cursors)]
        try:
            future=asyncio.run_coroutine_threadsafe(get(),self.client.loop)
            return {'messages':future.result(timeout=15),'error':None}
        except Exception as exc: return {'messages':[],'error':type(exc).__name__}

