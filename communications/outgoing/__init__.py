"""Outgoing provider selection."""
from .disabled import DisabledWriteProvider
from .discord_bot import DiscordBotWriteProvider

def select_provider(settings):
    value=settings.get("DISCORD_WRITE_PROVIDER","disabled")
    if value=="discord_bot": return DiscordBotWriteProvider(settings)
    if value=="disabled": return DisabledWriteProvider()
    return DisabledWriteProvider("Unknown write provider")
