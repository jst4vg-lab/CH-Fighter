"""Guild author data and local name-color overrides."""
from crea_core import db

def normalize_author(author):
    member=author if hasattr(author,"roles") else None
    roles=sorted((r for r in getattr(member,"roles",[]) if r.name!="@everyone"),key=lambda r:r.position,reverse=True)
    role_color=next((str(r.color) for r in roles if r.color.value),None)
    return {"id":str(author.id),"username":author.name,"display_name":author.display_name,"nickname":getattr(member,"nick",None),
            "avatar_url":str(author.display_avatar.url),"role_color":role_color,
            "roles":[{"id":str(r.id),"name":r.name,"color":str(r.color)} for r in roles]}

def colors():
    con=db()
    try:return {r['user_id']:r['color'] for r in con.execute('select user_id,color from member_colors')}
    finally:con.close()

def set_color(user_id,color):
    import re
    if not isinstance(user_id,str) or not re.fullmatch(r'\d{1,24}',user_id):raise ValueError('Invalid Discord user ID')
    if color is not None and (not isinstance(color,str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}',color)):raise ValueError('Invalid color')
    con=db()
    try:
        with con:
            if color is None:con.execute('delete from member_colors where user_id=?',(user_id,))
            else:con.execute('insert into member_colors(user_id,color) values(?,?) on conflict(user_id) do update set color=excluded.color',(user_id,color.upper()))
    finally:con.close()
    return colors()
