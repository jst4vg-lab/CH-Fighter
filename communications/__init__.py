"""Backend communications configuration and provider entry points."""
from .config import load_environment as config

from .core.users import colors, set_color
from .incoming.discord_bot import DiscordBotIncoming
