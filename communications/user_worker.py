"""Discord user session entry point. Standard output is reserved for JSON replies."""
import asyncio
from importlib.metadata import version, PackageNotFoundError
import json
import sys


def emit(value):
    print(json.dumps(value), flush=True)


def load_library():
    try:
        version('discord.py')
    except PackageNotFoundError:
        pass
    else:
        raise ValueError('Mixed Discord distributions')
    if version('discord.py-self') != '2.1.0':
        raise ValueError('Unsupported worker dependency')
    import discord
    return discord


async def run(config):
    discord = load_library()
    from communications.core.mentions import directory
    from communications.incoming.discord_bot import DiscordBotIncoming
    from communications.outgoing.discord_bot import DiscordBotWriteProvider

    client = discord.Client(chunk_guilds_at_startup=False)
    reader = DiscordBotIncoming(config)
    if config.get('read_destination'):
        reader.guild_id, reader.start_channel = config['read_destination']
    if config['read_enabled']:
        reader.bind(client)
    def writer_for(guild_id, channel_id):
        settings = {'DISCORD_GUILD_ID': guild_id, 'DISCORD_WRITE_TEST_CHANNEL_ID': channel_id}
        writer = DiscordBotWriteProvider(settings)
        writer.client = client
        writer.reason = 'The outgoing profile cannot send in this channel'
        return writer

    async def login():
        try:
            await client.start(config.pop('token'))
        except discord.LoginFailure:
            emit({'state': 'authentication_failed', 'reason': 'Discord rejected the user credential'})
        except Exception:
            emit({'state': 'disconnected', 'reason': 'Discord user connection failed'})

    async with client:
        task = asyncio.create_task(login())
        try:
            while line := await asyncio.to_thread(sys.stdin.readline):
                request = json.loads(line)
                operation, args = request['operation'], request['args']
                try:
                    if operation == 'poll':
                        user = client.user
                        result = {
                            'state': 'connected' if client.is_ready() else 'connecting',
                            'account': {'id': str(user.id), 'name': user.name} if user else None,
                            'feed': reader.snapshot(*args),
                            'guilds': reader.guild_options() if client.is_ready() and config['read_enabled'] else [],
                        }
                    elif operation == 'read_destination':
                        guild_id, channel_id = args
                        guild = client.get_guild(int(guild_id))
                        if not config['read_enabled'] or not any(
                                channel['id'] == channel_id for channel in reader.visible_channels(guild)):
                            result = {'error': 'The incoming profile cannot view this channel'}
                        else:
                            with reader.lock:
                                reader.guild_id, reader.start_channel = guild_id, channel_id
                            result = {'ok': True}
                    elif operation == 'mentions':
                        guild_id, query = args
                        result = {'items': directory(client.get_guild(int(guild_id)), query)}
                    elif operation == 'history':
                        result = await asyncio.to_thread(reader.history, *args)
                    elif operation in ('write_status', 'send', 'react'):
                        guild_id, channel_id, *payload = args
                        if not config['write_enabled']:
                            raise ValueError('Sending is disabled for this profile')
                        writer = writer_for(guild_id, channel_id)
                        if operation == 'write_status':
                            result = writer.status()
                        elif operation == 'send':
                            from pathlib import Path
                            draft, content, paths, reply, mentions = payload
                            result = await asyncio.to_thread(writer.send, draft, content, list(map(Path, paths)), reply, mentions)
                        else:
                            result = await asyncio.to_thread(writer.add_reaction, *payload)
                    else:
                        raise ValueError('Unknown worker operation')
                    emit({'id': request['id'], 'result': result})
                except Exception:
                    emit({'id': request['id'], 'result': {'error': 'Discord worker request failed'}})
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--check']:
            discord = load_library()
            discord.Client(chunk_guilds_at_startup=False)
            emit({'version': discord.__version__})
        else:
            asyncio.run(run(json.loads(sys.stdin.readline())))
    except (ImportError, PackageNotFoundError, ValueError):
        emit({'state': 'unconfigured', 'reason': 'Install only discord.py-self 2.1.0 in the user worker environment'})
