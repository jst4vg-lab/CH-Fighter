"""Desktop quick reaction preferences and explicit Discord dispatch."""
from contextlib import closing
import json
import re

from crea_core import db

DEFAULTS = ('❌', '✅', '🧱', '🔥', '😐')
CUSTOM = re.compile(r'<a?:[A-Za-z0-9_]{2,32}:[0-9]{1,24}>')
BASE = r'[\u00a9\u00ae\u203c\u2049\u2122\u2139\u2194-\u2199\u21a9\u21aa\u231a\u231b\u2328\u23cf\u23e9-\u23f3\u23f8-\u23fa\u24c2\u25aa\u25ab\u25b6\u25c0\u25fb-\u27bf\u2934\u2935\u2b05-\u2b07\u2b1b\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299\U0001f000-\U0001f1e5\U0001f200-\U0001f3fa\U0001f400-\U0001faff]'
UNIT = BASE + r'\ufe0f?[\U0001f3fb-\U0001f3ff]?'
UNICODE = re.compile(rf'(?:{UNIT}(?:\u200d{UNIT})*|[\U0001f1e6-\U0001f1ff]{{2}}|[0-9#*]\ufe0f?\u20e3|\U0001f3f4[\U000e0020-\U000e007e]+\U000e007f)')


def preferences():
    with closing(db()) as con:
        row = con.execute("select value from app_settings where key='quick_reactions'").fetchone()
    return {'slots': json.loads(row['value']) if row else list(DEFAULTS), 'defaults': list(DEFAULTS)}


def save(slots):
    if (not isinstance(slots, list) or len(slots) != 5 or
            any(not isinstance(emoji, str) or len(emoji) > 64 or
                not (CUSTOM.fullmatch(emoji) or UNICODE.fullmatch(emoji)) for emoji in slots)):
        raise ValueError('Enter one Unicode or Discord custom emoji in each of the five slots')
    with closing(db()) as con, con:
        con.execute("insert or replace into app_settings(key,value) values('quick_reactions',?)",
                    (json.dumps(slots),))
    return {'slots': slots, 'defaults': list(DEFAULTS)}


def add(body, provider):
    state = provider.status()
    if not state['capabilities'].get('react'):
        raise ValueError('The active profile cannot react in this channel')
    if any(body.get(key) != state.get(key) for key in ('guild_id', 'channel_id', 'sender_id')):
        raise ValueError('The active reaction destination changed')
    message_id, emoji = body.get('message_id'), body.get('emoji')
    if not isinstance(message_id, str) or not re.fullmatch(r'[0-9]{1,24}', message_id):
        raise ValueError('Invalid message ID')
    if emoji not in preferences()['slots']:
        raise ValueError('Choose a current quick reaction preset')
    return provider.add_reaction(message_id, emoji)
