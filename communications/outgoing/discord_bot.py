"""Discord channel operations for the destination chosen by the connection manager."""
import asyncio
import concurrent.futures
from contextlib import ExitStack
from ..core.channels import can_view_channel

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
        can_react = False
        visible = False
        if self.client and self.client.is_ready() and self.channel_id.isdigit():
            channel = self.client.get_channel(int(self.channel_id))
            if channel and hasattr(channel, 'send') and getattr(channel, 'guild', None) and str(channel.guild.id) == self.guild_id and channel.guild.me:
                permissions = channel.permissions_for(channel.guild.me)
                threaded = hasattr(channel, 'parent_id')
                visible = can_view_channel(channel, permissions)
                ready = visible and (permissions.send_messages_in_threads if threaded else permissions.send_messages)
                can_react = visible and permissions.read_message_history
                self.channel, self.member = channel, channel.guild.me
        return {'provider':'discord_bot','state':'connected' if ready else 'permission_limited' if self.client else 'unavailable', 'reason':'' if ready else self.reason,'guild_id':self.guild_id or None,'channel_id':self.channel_id or None,
                'sender_id':str(self.client.user.id) if (ready or can_react) and self.client.user else None,
                'sender_name':getattr(self.client.user, 'display_name', None) if ready else None,
                'channel_name':getattr(self.channel, 'name', None) if visible else None,
                'capabilities':{'send':ready,'reply':ready,'react':can_react,'attach':ready and self.channel.permissions_for(self.member).attach_files}}

    def add_reaction(self, message_id, emoji):
        import discord
        from ..core.normalization import normalize

        if not self.status()['capabilities']['react']:
            return {'ok': False, 'error': 'The active profile cannot react in this channel'}
        channel = self.channel

        async def submit():
            message = await channel.fetch_message(int(message_id))
            value = discord.PartialEmoji.from_str(emoji) if emoji.startswith('<') else emoji
            await message.add_reaction(value)
            try:
                return {'ok': True, 'message': normalize(await channel.fetch_message(int(message_id)))}
            except discord.HTTPException:
                return {'ok': True}

        future = asyncio.run_coroutine_threadsafe(submit(), self.client.loop)
        try:
            return future.result(timeout=15)
        except discord.Forbidden:
            return {'ok': False, 'error': 'Discord denied permission to add this reaction'}
        except discord.NotFound as exc:
            message = 'This emoji is unavailable' if exc.code == 10014 else 'The message was deleted or is unavailable'
            return {'ok': False, 'error': message}
        except discord.HTTPException as exc:
            message = 'This emoji is unavailable' if exc.code == 10014 else 'Discord could not add the reaction'
            return {'ok': False, 'error': message}
        except concurrent.futures.TimeoutError:
            future.cancel()
            return {'ok': False, 'error': 'Discord did not confirm the reaction. Check the message before retrying.'}

    def send(self, draft_id, text, paths, reply_to_id='', mentions=None):
        status=self.status()
        if not status['capabilities']['send'] or (paths and not status['capabilities']['attach']):
            return {'ok':False,'code':'provider_unavailable','error':status['reason'] or 'Attachment permission missing'}
        import discord
        async def submit():
            guild = self.channel.guild
            selected = mentions or {}
            permissions = self.channel.permissions_for(guild.me)
            users, roles = [], []
            for user_id in selected.get('users', ()):
                try:
                    member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
                except discord.NotFound:
                    return {'ok': False, 'code': 'failed', 'error': 'A mentioned member is no longer in this server'}
                if not self.channel.permissions_for(member).view_channel:
                    return {'ok': False, 'code': 'failed', 'error': 'A mentioned member cannot view this channel'}
                users.append(discord.Object(id=int(user_id)))
            for role_id in selected.get('roles', ()):
                role = guild.get_role(int(role_id))
                if not role or role.is_default() or not (role.mentionable or permissions.mention_everyone):
                    return {'ok': False, 'code': 'failed', 'error': 'The active profile cannot mention that role'}
                roles.append(role)
            allowed = discord.AllowedMentions(everyone=False, users=users, roles=roles, replied_user=False)
            with ExitStack() as stack:
                files=[discord.File(stack.enter_context(open(path,'rb')),filename=path.name) for path in paths]
                reference=discord.MessageReference(message_id=int(reply_to_id),channel_id=int(self.channel_id),guild_id=int(self.guild_id),fail_if_not_exists=True) if reply_to_id else None
                message=await self.channel.send(content=text or None,files=files,reference=reference,
                    allowed_mentions=allowed,nonce=int(draft_id.replace('-','')[:16],16))
                return {'ok':True,'message_id':str(message.id),'sender_id':str(message.author.id),
                        'channel_id':str(message.channel.id),'url':message.jump_url}
        try:
            return asyncio.run_coroutine_threadsafe(submit(),self.client.loop).result(timeout=45)
        except concurrent.futures.TimeoutError:
            return {'ok':False,'code':'unverified','error':'Send timed out; check Discord before another attempt'}
        except discord.HTTPException as exc:
            if exc.status >= 500:
                return {'ok':False,'code':'unverified','error':'Discord returned a server error. Check the channel before retrying.'}
            reason = 'The original message was deleted or is unavailable' if reply_to_id and (exc.status == 404 or exc.code in (10008, 160002)) else type(exc).__name__
            return {'ok':False,'code':'failed','error':reason}
        except Exception as exc:
            return {'ok':False,'code':'unverified','error':type(exc).__name__}


