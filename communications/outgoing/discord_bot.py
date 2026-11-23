"""Authorized test-channel bot outgoing provider."""
import asyncio
import concurrent.futures
from contextlib import ExitStack

class DiscordBotWriteProvider:
    def __init__(self, settings):
        self.settings=settings
        self.channel_id=settings.get('DISCORD_WRITE_TEST_CHANNEL_ID','')
        self.guild_id=settings.get('DISCORD_GUILD_ID','')
        self.client=None
        self.channel=None
        self.member=None
        self.state='unavailable'
        self.reason='Write bot is not configured'

    def status(self):
        ready = False
        if self.client and self.client.is_ready() and self.channel_id.isdigit():
            channel = self.client.get_channel(int(self.channel_id))
            if channel and hasattr(channel, 'send') and getattr(channel, 'guild', None) and str(channel.guild.id) == self.guild_id and channel.guild.me:
                permissions = channel.permissions_for(channel.guild.me)
                threaded = hasattr(channel, 'parent_id')
                ready = permissions.view_channel and (permissions.send_messages_in_threads if threaded else permissions.send_messages)
                self.channel, self.member = channel, channel.guild.me
        return {'provider':'discord_bot','state':'connected' if ready else 'permission_limited' if self.client else 'unavailable', 'reason':'' if ready else self.reason,'guild_id':self.guild_id or None,'channel_id':self.channel_id or None,
                'sender_id':str(self.client.user.id) if ready and self.client.user else None,
                'capabilities':{'send':ready,'reply':ready,'attach':ready and self.channel.permissions_for(self.member).attach_files}}

    def send(self, draft_id, text, paths, reply_to_id=''):
        status=self.status()
        if not status['capabilities']['send'] or (paths and not status['capabilities']['attach']):
            return {'ok':False,'code':'provider_unavailable','error':status['reason'] or 'Attachment permission missing'}
        import discord
        async def submit():
            with ExitStack() as stack:
                files=[discord.File(stack.enter_context(open(path,'rb')),filename=path.name) for path in paths]
                reference=discord.MessageReference(message_id=int(reply_to_id),channel_id=int(self.channel_id),guild_id=int(self.guild_id),fail_if_not_exists=True) if reply_to_id else None
                message=await self.channel.send(content=text or None,files=files,reference=reference,
                    allowed_mentions=discord.AllowedMentions.none(),nonce=int(draft_id.replace('-','')[:16],16))
                return {'ok':True,'message_id':str(message.id),'sender_id':str(message.author.id),
                        'channel_id':str(message.channel.id),'url':message.jump_url}
        try:
            return asyncio.run_coroutine_threadsafe(submit(),self.client.loop).result(timeout=45)
        except concurrent.futures.TimeoutError:
            return {'ok':False,'code':'unverified','error':'Send timed out; check Discord before another attempt'}
        except (discord.Forbidden,discord.NotFound,discord.HTTPException) as exc:
            return {'ok':False,'code':'failed','error':type(exc).__name__}
        except Exception as exc:
            return {'ok':False,'code':'unverified','error':type(exc).__name__}


