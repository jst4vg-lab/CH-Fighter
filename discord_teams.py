"""Local team assignments for Discord participants, scoped to a server."""
from contextlib import closing
import re

from crea_core import db

TEAMS = ('blue', 'red', 'yellow')


def validate_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,24}', value):
        raise ValueError('Invalid Discord server or member ID')


def members(guild_id):
    validate_id(guild_id)
    with closing(db()) as con:
        return [dict(row) for row in con.execute(
            'select user_id, name, team from discord_teams where guild_id=? order by name, user_id', (guild_id,))]


def assign(guild_id, user_id, name, team):
    validate_id(guild_id)
    validate_id(user_id)
    if team is not None and team not in TEAMS:
        raise ValueError('Choose Blue, Red, Yellow, or Unassigned')
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError('Invalid member name')
    with closing(db()) as con, con:
        if team is None:
            con.execute('delete from discord_teams where guild_id=? and user_id=?', (guild_id, user_id))
        else:
            con.execute('''insert into discord_teams(guild_id,user_id,name,team) values(?,?,?,?)
                         on conflict(guild_id,user_id) do update set name=excluded.name,team=excluded.team''',
                        (guild_id, user_id, name.strip(), team))
    return members(guild_id)

def color_view(enabled=None):
    with closing(db()) as con, con:
        if enabled is not None:
            if type(enabled) is not bool:
                raise ValueError('Invalid team color preference')
            con.execute("insert or replace into app_settings(key,value) values('team_colors',?)",
                        ('1' if enabled else '0',))
        row = con.execute("select value from app_settings where key='team_colors'").fetchone()
        return {'enabled': bool(row and row['value'] == '1')}
