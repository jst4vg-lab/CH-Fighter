"""Convert Discord messages to the frontend model."""
from .users import normalize_author

def normalize(message):
    author=message.author
    ref=getattr(message,'reference',None)
    return {'id':str(message.id),'channel_id':str(message.channel.id),'guild_id':str(message.guild.id) if message.guild else None,
            'content':message.content,'timestamp':message.created_at.isoformat(),'edited_at':message.edited_at.isoformat() if message.edited_at else None,
            'author':normalize_author(author),
            'attachments':[{'id':str(a.id),'name':a.filename,'url':a.url,'content_type':a.content_type,'size':a.size} for a in message.attachments],
            'embeds':[e.to_dict() for e in message.embeds],
            'reactions':[{'emoji':str(r.emoji),'count':r.count} for r in message.reactions],
            'reply_to':str(ref.message_id) if ref and ref.message_id else None,
            'url':message.jump_url}

