"""Authorized Discord bot incoming provider."""
import asyncio
import logging

logger = logging.getLogger(__name__)
from .. import config
from ..core.channels import normalize_channel
from ..core.messages import MessageEventStore
from ..core.normalization import normalize

class DiscordBotIncoming(MessageEventStore):
    def __init__(self,settings=None):
        super().__init__(); self.settings=settings or config()
        self.channels=[]; self.state='unavailable'; self.reason='Read bot is not configured'; self.client=None
        self.guild_id=self.settings.get('DISCORD_GUILD_ID',''); self.start_channel=self.settings.get('DISCORD_COMBAT_CHANNEL_ID','')

    def snapshot(self,after=0,channel_id=None):
        guild = self.client.get_guild(int(self.guild_id)) if self.client and self.guild_id.isdigit() else None
        channels = []
        if guild and guild.me:
            for channel in guild.text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.view_channel:
                    channels.append({**normalize_channel(channel), 'history': permissions.read_message_history})
        visible = {c['id'] for c in channels}
        with self.lock:
            return {'state':self.state,'reason':self.reason,'guild_id':self.guild_id,'start_channel_id':self.start_channel,
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
            guild=client.get_guild(int(hub.guild_id))
            with hub.lock:
                if not guild: hub.state='unavailable';hub.reason='Configured guild is not accessible';return
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
    def history(self,channel_id,before=None,limit=50):
        if self.state!='connected': return {'error':self.reason,'messages':[]}
        channel=self.client.get_channel(int(channel_id)) if channel_id.isdigit() else None
        if not channel or not hasattr(channel, 'history') or str(channel.guild.id)!=self.guild_id or not channel.guild.me or not (channel.permissions_for(channel.guild.me).view_channel and channel.permissions_for(channel.guild.me).read_message_history): return {'error':'Channel unavailable','messages':[]}
        import asyncio, discord
        async def get():
            cursor=discord.Object(id=int(before)) if before and before.isdigit() else None
            return [normalize(m) async for m in channel.history(limit=min(limit,100),before=cursor)]
        try:
            future=asyncio.run_coroutine_threadsafe(get(),self.client.loop)
            return {'messages':future.result(timeout=15),'error':None}
        except Exception as exc: return {'messages':[],'error':type(exc).__name__}

