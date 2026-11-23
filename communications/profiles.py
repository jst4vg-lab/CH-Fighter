"""Validated, nonsecret connection profiles and legacy configuration migration."""
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import tomllib


@dataclass(frozen=True)
class ConnectionProfile:
    id: str
    name: str
    provider: str
    token_env: str
    guild_id: str
    channel_id: str = ''
    read_enabled: bool = True
    write_enabled: bool = False
    description: str = ''

    def public(self):
        return asdict(self)


def load_profiles(path: Path, settings: dict):
    profiles = {}
    if path.exists():
        try:
            with path.open('rb') as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError):
            raise ValueError('Cannot read connection profiles: check TOML syntax and file access') from None
        if set(document) - {'profiles'} or not isinstance(document.get('profiles', {}), dict):
            raise ValueError('Expected a profiles table')
        for profile_id, values in document.get('profiles', {}).items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', profile_id) or not isinstance(values, dict):
                raise ValueError('Invalid profile ID or table')
            allowed = set(ConnectionProfile.__dataclass_fields__) - {'id'}
            if set(values) - allowed:
                raise ValueError(f'Unknown fields in profile {profile_id}; store credentials in environment variables')
            try:
                profile = ConnectionProfile(id=profile_id, **values)
            except TypeError:
                raise ValueError(f'Missing required fields in profile {profile_id}') from None
            for field in ('name', 'provider', 'token_env', 'guild_id', 'channel_id', 'description'):
                if not isinstance(getattr(profile, field), str):
                    raise ValueError(f'Invalid field type in profile {profile_id}')
            if not profile.name.strip() or profile.provider != 'discord_bot':
                raise ValueError(f'Invalid name or unsupported provider in profile {profile_id}')
            if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', profile.token_env):
                raise ValueError(f'Invalid credential environment reference in profile {profile_id}')
            if not re.fullmatch(r'\d{1,24}', profile.guild_id) or (profile.channel_id and not re.fullmatch(r'\d{1,24}', profile.channel_id)):
                raise ValueError(f'Invalid guild or channel ID in profile {profile_id}')
            if type(profile.read_enabled) is not bool or type(profile.write_enabled) is not bool:
                raise ValueError(f'Invalid direction flags in profile {profile_id}')
            profiles[profile_id] = profile
    for direction in ('read', 'write'):
        key = direction.upper()
        if settings.get(f'DISCORD_{key}_PROVIDER', 'discord_bot' if direction == 'read' else 'disabled') != 'discord_bot':
            continue
        profile_id = f'legacy_{direction}'
        profiles.setdefault(profile_id, ConnectionProfile(
            profile_id, f'Legacy {direction} bot', 'discord_bot', f'DISCORD_{key}_BOT_TOKEN',
            settings.get('DISCORD_GUILD_ID', ''),
            settings.get('DISCORD_COMBAT_CHANNEL_ID' if direction == 'read' else 'DISCORD_WRITE_TEST_CHANNEL_ID', ''),
            direction == 'read', direction == 'write'))
    return profiles


def resolve_credential(profile, settings):
    value = settings.get(profile.token_env, '')
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Configure backend environment variable {profile.token_env}')
    return value.strip()
