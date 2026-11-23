"""Normalized channel records."""

def normalize_channel(channel):
    return {"id":str(channel.id),"guild_id":str(channel.guild.id),"name":channel.name}
