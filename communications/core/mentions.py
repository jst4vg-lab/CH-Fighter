"""Mention labels, draft selections, and Discord notification allowlists."""
import re
from .users import normalize_author

ID = re.compile(r'[0-9]{1,24}')


def member_record(member):
    return {'kind': 'user', **normalize_author(member)}


def role_record(role):
    return {'kind': 'role', 'id': str(role.id), 'name': role.name,
            'role_color': str(role.color) if role.color.value else None}


def directory(guild, query):
    if not guild:
        return []
    query = query.casefold()
    roles = [role_record(role) for role in guild.roles
             if not role.is_default() and query in role.name.casefold()][:20]
    members = []
    for member in guild.members:
        if query in member.display_name.casefold() or query in member.name.casefold():
            members.append(member_record(member))
            if len(members) == 20:
                break
    return members + roles


def selections(text, values):
    if not isinstance(text, str) or not isinstance(values, list) or len(values) > 100:
        raise ValueError('Invalid mention selections')
    encoded = text.encode('utf-16-le')
    validated = []
    previous = 0
    for value in values:
        if not isinstance(value, dict) or value.get('kind') not in ('user', 'role'):
            raise ValueError('Invalid mention selection')
        if any(not isinstance(value.get(key), str) or not ID.fullmatch(value[key])
               for key in ('id', 'guild_id', 'channel_id')):
            raise ValueError('Invalid mention destination')
        name, start, end = (value.get(key) for key in ('name', 'start', 'end'))
        if (not isinstance(name, str) or not 1 <= len(name) <= 100
                or type(start) is not int or type(end) is not int
                or not previous <= start < end <= len(encoded) // 2
                or encoded[start * 2:end * 2] != ('@' + name).encode('utf-16-le')):
            raise ValueError('A selected mention no longer matches the draft')
        validated.append({key: value[key] for key in ('id', 'kind', 'name', 'start', 'end', 'guild_id', 'channel_id')})
        previous = end
    return validated


def prepare(text, values, destination):
    values = selections(text, values)
    encoded = text.encode('utf-16-le')
    result, last = [], 0
    allowed = {'users': [], 'roles': []}
    for value in values:
        if any(value[key] != destination.get(key) for key in ('guild_id', 'channel_id')):
            raise ValueError('A mention targets a different channel. Remove it and select it again.')
        start, end = value['start'] * 2, value['end'] * 2
        result.append(encoded[last:start].decode('utf-16-le'))
        role = value['kind'] == 'role'
        result.append(f'<@{"&" if role else ""}{value["id"]}>')
        allowed['roles' if role else 'users'].append(value['id'])
        last = end
    result.append(encoded[last:].decode('utf-16-le'))
    return ''.join(result), {key: list(dict.fromkeys(ids)) for key, ids in allowed.items()}
