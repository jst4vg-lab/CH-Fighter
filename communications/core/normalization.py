"""Convert Discord messages and forwarded snapshots to the feed model."""
import re

from .users import normalize_author
from .mentions import member_record, role_record


def _mentions(message, guild):
    targets = {('user', str(member.id)): member_record(member) for member in getattr(message, 'mentions', ())}
    targets.update({('role', str(role.id)): role_record(role) for role in getattr(message, 'role_mentions', ())})
    for prefix, value in re.findall(r'<@([!&]?)([0-9]{1,24})>', message.content or ''):
        role = prefix == '&'
        kind = 'role' if role else 'user'
        if (kind, value) in targets or not guild:
            continue
        lookup = getattr(guild, 'get_role' if role else 'get_member', None)
        target = lookup(int(value)) if lookup else None
        if target:
            targets[(kind, value)] = role_record(target) if role else member_record(target)
    return list(targets.values())


def _media(message, guild):
    return {
        'content': message.content,
        'mentions': _mentions(message, guild),
        'attachments': [{'id': str(item.id), 'name': item.filename, 'url': item.url,
                         'content_type': item.content_type, 'size': item.size}
                        for item in message.attachments],
        'embeds': [embed.to_dict() for embed in message.embeds],
        'stickers': [{'id': str(item.id), 'name': item.name, 'url': str(item.url)}
                     for item in getattr(message, 'stickers', ()) if getattr(item, 'url', None)],
    }


def normalize(message):
    ref = getattr(message, 'reference', None)
    snapshots = getattr(message, 'message_snapshots', ()) or ()
    forwarded = bool(snapshots) or getattr(getattr(ref, 'type', None), 'value', None) == 1
    return {
        **_media(message, message.guild),
        'id': str(message.id),
        'channel_id': str(message.channel.id),
        'guild_id': str(message.guild.id) if message.guild else None,
        'timestamp': message.created_at.isoformat(),
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
        'author': normalize_author(message.author),
        'reactions': [{'emoji': str(reaction.emoji), 'count': reaction.count}
                      for reaction in message.reactions],
        'reply_to': str(ref.message_id) if not forwarded and ref and ref.message_id else None,
        'reply_channel_id': str(ref.channel_id) if not forwarded and ref and getattr(ref, 'channel_id', None) else None,
        'forwarded': forwarded,
        'forwarded_messages': [
            {**_media(snapshot, message.guild), 'timestamp': snapshot.created_at.isoformat() if snapshot.created_at else None}
            for snapshot in snapshots],
        'url': message.jump_url,
    }
