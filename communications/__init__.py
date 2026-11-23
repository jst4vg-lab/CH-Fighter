"""Backend communications configuration and provider entry points."""
from .config import load_environment as config

from .incoming.discord_bot import DiscordBotIncoming
