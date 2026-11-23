"""Guild author data."""

def normalize_author(author):
    member=author if hasattr(author,"roles") else None
    roles=sorted((r for r in getattr(member,"roles",[]) if r.name!="@everyone"),key=lambda r:r.position,reverse=True)
    role_color=next((str(r.color) for r in roles if r.color.value),None)
    return {"id":str(author.id),"username":author.name,"display_name":author.display_name,"nickname":getattr(member,"nick",None),
            "avatar_url":str(author.display_avatar.url),"role_color":role_color,
            "roles":[{"id":str(r.id),"name":r.name,"color":str(r.color)} for r in roles]}
