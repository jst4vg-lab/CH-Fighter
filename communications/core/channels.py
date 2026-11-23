"""Normalized channel records."""

def normalize_channel(channel):
    return {"id":str(channel.id),"guild_id":str(channel.guild.id),"name":channel.name}

def can_view_channel(channel, permissions):
    if not permissions.view_channel:
        return False
    is_private = getattr(channel, 'is_private', None)
    return not (is_private and is_private()) or getattr(permissions, 'manage_threads', False) or bool(getattr(channel, 'me', None))
