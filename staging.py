"""Authoritative, transactional package and Used Crea operations."""
import uuid
import json
from crea_core import db

def _package(con, row):
    items=[dict(r) for r in con.execute('''select i.asset_id id,i.position,i.missing,a.relpath,a.branch,a.type,a.creator,a.bp,a.render_key
      from package_items i join assets a on a.id=i.asset_id where i.package_id=? order by i.position''',(row['id'],))]
    return {**dict(row),'items':items,'missing_count':sum(i['missing'] for i in items)}

def _deployment_state(con):
    return {'packages':[dict(r) for r in con.execute('select * from packages order by id')],
            'items':[dict(r) for r in con.execute('select * from package_items order by package_id,asset_id')],
            'used':[r['id'] for r in con.execute('select id from assets where used=1 order by id')]}

def snapshot():
    con=db()
    packages=[_package(con,r) for r in con.execute('select * from packages order by case location when \'hot\' then 0 else 1 end,position,id')]
    last=con.execute('select after_json from deployments where undone=0 order by rowid desc limit 1').fetchone()
    result={'hot':next((p for p in packages if p['location']=='hot'),None),'reserve':[p for p in packages if p['location']=='reserve'],'used_count':con.execute('''select count(*) from assets a join creators c on c.name=a.creator where a.used=1 and c.enabled=1''').fetchone()[0],
            'can_undo':bool(last and json.dumps(_deployment_state(con),sort_keys=True)==last['after_json'])}
    con.close();return result

def add_to_hot(asset_ids):
    ids=list(dict.fromkeys(asset_ids))
    if not ids: raise ValueError('Select at least one crea')
    con=db()
    try:
        con.execute('begin immediate')
        for aid in ids:
            r=con.execute("select a.status,a.used,c.enabled from assets a left join creators c on c.name=a.creator where a.id=?",(aid,)).fetchone()
            if not r or r['status']!='ready' or r['used'] or r['enabled']!=1: raise ValueError('Selected crea is unavailable')
        hot=con.execute("select id from packages where location='hot'").fetchone()
        pid=hot['id'] if hot else str(uuid.uuid4())
        existing={r['asset_id'] for r in con.execute('select asset_id from package_items where package_id=?',(pid,))}
        if len(existing)+sum(aid not in existing for aid in ids)>10:
            raise ValueError('Hot Staging is full (10 crea)')
        if not hot:con.execute("insert into packages(id,location) values(?,'hot')",(pid,))
        pos=con.execute('select coalesce(max(position),-1)+1 from package_items where package_id=?',(pid,)).fetchone()[0]
        for aid in ids:
            if not con.execute('select 1 from package_items where package_id=? and asset_id=?',(pid,aid)).fetchone():
                con.execute('insert into package_items(package_id,asset_id,position) values(?,?,?)',(pid,aid,pos));pos+=1
        con.commit();return snapshot()
    except Exception:
        con.rollback();raise
    finally:con.close()

def reserve_hot(expected_package_id=None):
    con=db()
    try:
        con.execute('begin immediate')
        hot=con.execute("select id from packages where location='hot'").fetchone()
        if not hot:raise ValueError('Hot Staging is empty')
        if expected_package_id is not None and hot['id']!=expected_package_id:
            raise ValueError('Hot package changed; refresh staging')
        pos=con.execute("select coalesce(max(position),-1)+1 from packages where location='reserve'").fetchone()[0]
        con.execute("update packages set location='reserve',position=? where id=?",(pos,hot['id']))
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()

def activate(pid):
    con=db()
    try:
        con.execute('begin immediate')
        target=con.execute("select id from packages where id=? and location='reserve'",(pid,)).fetchone()
        if not target:raise ValueError('Reserve package not found')
        hot=con.execute("select id from packages where location='hot'").fetchone()
        if hot:
            pos=con.execute("select coalesce(max(position),-1)+1 from packages where location='reserve'").fetchone()[0]
            con.execute("update packages set location='reserve',position=? where id=?",(pos,hot['id']))
        con.execute("update packages set location='hot',position=0 where id=?",(pid,))
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()

def save_submission(pid,text):
    if not isinstance(text,str) or len(text)>5000:raise ValueError('Submission must be under 5000 characters')
    con=db()
    try:
        con.execute('begin immediate')
        if not con.execute('update packages set submission=? where id=?',(text,pid)).rowcount:raise ValueError('Package not found')
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()

def remove_from_hot(aid):
    con=db()
    try:
        con.execute('begin immediate')
        hot=con.execute("select id from packages where location='hot'").fetchone()
        if not hot or not con.execute('delete from package_items where package_id=? and asset_id=?',(hot['id'],aid)).rowcount:
            raise ValueError('Crea is not in Hot Staging')
        if not con.execute('select 1 from package_items where package_id=?',(hot['id'],)).fetchone():
            con.execute('delete from packages where id=?',(hot['id'],))
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()

def acknowledge(pid):
    con=db()
    try:
        con.execute('begin immediate')
        if not con.execute('update packages set needs_review=0 where id=?',(pid,)).rowcount:raise ValueError('Package not found')
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()

def confirm_hot(expected_package_id=None, expected_asset_ids=None):
    con=db()
    try:
        con.execute('begin immediate')
        hot=con.execute("select id from packages where location='hot'").fetchone()
        if not hot:raise ValueError('Hot Staging is empty')
        if expected_package_id is not None and hot['id']!=expected_package_id:
            raise ValueError('Hot package changed; refresh staging')
        current_ids=[row['asset_id'] for row in con.execute(
            'select asset_id from package_items where package_id=? order by position',(hot['id'],))]
        if expected_asset_ids is not None and current_ids!=expected_asset_ids:
            raise ValueError('Hot package contents changed; copy it again')
        items=con.execute('''select i.asset_id,a.branch,a.type,a.bp from package_items i join assets a on a.id=i.asset_id
          where i.package_id=? and i.missing=0 order by i.position''',(hot['id'],)).fetchall()
        if con.execute('select 1 from package_items where package_id=? and missing=1',(hot['id'],)).fetchone():raise ValueError('Resolve missing crea before confirming')
        if not items:raise ValueError('Package has no crea')
        before=json.dumps(_deployment_state(con),sort_keys=True)
        for item in items: con.execute('update assets set used=1 where id=?',(item['asset_id'],))
        for item in items:
            slots=con.execute('''select i.package_id from package_items i join packages p on p.id=i.package_id
              where p.location='reserve' and i.asset_id=? and i.missing=0''',(item['asset_id'],)).fetchall()
            for slot in slots:
                pid=slot['package_id']
                candidate=con.execute('''select a.id from assets a join creators c on c.name=a.creator where c.enabled=1 and a.status='ready' and a.used=0 and a.branch=? and a.type=?
                  and not exists(select 1 from package_items x where x.package_id=? and x.asset_id=a.id)
                  order by a.creator,a.seq,a.id limit 1''',(item['branch'],item['type'],pid)).fetchone()
                if candidate:con.execute('update package_items set asset_id=? where package_id=? and asset_id=?',(candidate['id'],pid,item['asset_id']))
                else:con.execute('update package_items set missing=1 where package_id=? and asset_id=?',(pid,item['asset_id']))
                if item['bp'] is not None:con.execute('update packages set needs_review=1 where id=?',(pid,))
        con.execute('delete from packages where id=?',(hot['id'],))
        after=json.dumps(_deployment_state(con),sort_keys=True)
        con.execute('insert into deployments(id,before_json,after_json) values(?,?,?)',(str(uuid.uuid4()),before,after))
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()

def undo_last_deployment():
    con=db()
    try:
        con.execute('begin immediate')
        row=con.execute('select id,before_json,after_json from deployments where undone=0 order by rowid desc limit 1').fetchone()
        if not row:raise ValueError('No deployment to undo')
        if json.dumps(_deployment_state(con),sort_keys=True)!=row['after_json']:
            raise ValueError('Staging or usage changed since deployment; undo is unavailable')
        before=json.loads(row['before_json'])
        con.execute('delete from packages')
        con.execute('update assets set used=0 where used=1')
        for aid in before['used']:con.execute('update assets set used=1 where id=?',(aid,))
        for p in before['packages']:
            con.execute('insert into packages(id,location,position,submission,needs_review) values(?,?,?,?,?)',
                        (p['id'],p['location'],p['position'],p['submission'],p['needs_review']))
        for i in before['items']:
            con.execute('insert into package_items(package_id,asset_id,position,missing) values(?,?,?,?)',
                        (i['package_id'],i['asset_id'],i['position'],i['missing']))
        con.execute('update deployments set undone=1 where id=?',(row['id'],))
        con.commit();return snapshot()
    except Exception:
        con.rollback();raise
    finally:con.close()

def restore(ids=None):
    con=db()
    try:
        con.execute('begin immediate')
        if ids is None:con.execute('update assets set used=0 where used=1')
        else:
            for aid in set(ids):con.execute('update assets set used=0 where id=?',(aid,))
        con.commit();return snapshot()
    except Exception:con.rollback();raise
    finally:con.close()
