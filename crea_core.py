from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import tempfile
import uuid
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw, ImageColor, ImageFilter

ROOT = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('CH_CREA_SOURCE', ROOT / 'Crea')).expanduser().resolve()
DATA = Path(os.environ.get('CH_DATA_DIR', ROOT / 'data')).expanduser().resolve()
DB = DATA / 'app.sqlite'
FORMATTED = DATA / 'formatted'
THUMBS = DATA / 'thumbnails'
TEMP = DATA / 'tmp'
PATTERN = re.compile(r'^(?P<branch>[a-z]{2})[-_](?P<type>[a-z]{3})[-_](?P<creator>[a-z0-9]+)-(?:(?P<bp>\d+)bp-)?(?P<seq>\d+)$', re.I)
BRANCHES = {'af':'Air Corps','ar':'Army','de':'Defense','ex':'Expeditionary Force','hf':'Space','mi':'Missiles','nf':'Naval'}
TYPES = {'afs':'Air Force Support','avi':'Helicopter','fgt':'Fighter','stk':'Strike Aircraft','ada':'Air Defence','art':'Artillery','asu':'Army Support','def':'Defences','fpv':'Drone','inf':'Infantry','mbt':'Tank','mob':'Mobility','frt':'Fortress','aas':'Air Assault','lan':'Orbital Drop','par':'Paratrooper','sct':'Space Combat','ses':'Space Escort','ssu':'Space Support','mis':'Missile','car':'Carrier','cbt':'Combat Ship','esc':'Escort','sub':'Submarine','tsb':'Transport','tsp':'Transport'}
BG = '#1B211B'
RENDER_VERSION = 'readable-bar-v3'
BAR_FONT = Path(os.environ.get('CH_FONT_PATH', ROOT / 'assets' / 'fonts' / 'NotoSans-Bold.ttf'))

def db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('pragma journal_mode=wal')
    con.execute('pragma foreign_keys=on')
    con.executescript('''
    create table if not exists creators(name text primary key,color text);
    create table if not exists assets(
      id text primary key, relpath text unique not null, sha256 text not null,
      branch text, type text, creator text, bp integer, seq integer,
      width integer, height integer, source_format text,
      status text not null, issue text, mode text not null default 'fit',
      focal_x real not null default 0.5, focal_y real not null default 0.5,
      render_key text, foreign key(creator) references creators(name));
    create index if not exists assets_filter on assets(branch,type,creator,status);
    create table if not exists packages(id text primary key, location text not null check(location in ('hot','reserve')), position integer not null default 0, submission text not null default '', needs_review integer not null default 0);
    create unique index if not exists one_hot_package on packages(location) where location='hot';
    create table if not exists package_items(package_id text not null references packages(id) on delete cascade, asset_id text not null references assets(id), position integer not null, missing integer not null default 0, primary key(package_id,asset_id));
    create table if not exists deployments(id text primary key,created_at text not null default current_timestamp,before_json text not null,after_json text not null,undone integer not null default 0);
    create table if not exists workspace_drafts(id text primary key, text text not null default '', asset_ids_json text not null default '[]', status text not null default 'draft' check(status in ('draft','prepared','handoff_pending','sent_confirmed','failed_unverified')), channel_url text not null default '', active integer not null default 1, created_at text not null default current_timestamp, updated_at text not null default current_timestamp);
    create table if not exists app_settings(key text primary key,value text not null);
    create table if not exists member_colors(user_id text primary key,color text not null);
    create table if not exists workspace_test_sends(draft_id text primary key references workspace_drafts(id),channel_id text not null,status text not null,message_id text,sender_id text,error text,updated_at text not null default current_timestamp);
    create unique index if not exists one_active_workspace_draft on workspace_drafts(active) where active=1;
    ''')
    if 'used' not in {r['name'] for r in con.execute('pragma table_info(assets)')}:
        con.execute('alter table assets add column used integer not null default 0')
        con.commit()
    if 'enabled' not in {r['name'] for r in con.execute('pragma table_info(creators)')}:
        con.execute('alter table creators add column enabled integer not null default 1')
        con.commit()
    if 'reply_to_id' not in {r['name'] for r in con.execute('pragma table_info(workspace_drafts)')}:
        con.execute("alter table workspace_drafts add column reply_to_id text not null default ''")
        con.commit()
    if 'guild_id' not in {r['name'] for r in con.execute('pragma table_info(workspace_test_sends)')}:
        con.execute('alter table workspace_test_sends add column guild_id text')
    con.execute('insert or ignore into app_settings(key,value) values(?,?)',('library_source',str(SOURCE)))
    con.commit()
    return con

def source_path():
    con=db()
    try: return Path(con.execute("select value from app_settings where key='library_source'").fetchone()[0])
    finally: con.close()

def visible_assets(status='ready'):
    con=db()
    try:
        where="a.status='ready' and a.used=1" if status=='used' else "a.status=? and a.used=0" if status=='ready' else 'a.status=?'
        args=() if status=='used' else (status,)
        return [dict(row) for row in con.execute(f'''select a.id,a.relpath,a.branch,a.type,a.creator,a.bp,a.seq,a.width,a.height,a.status,a.issue,a.mode,a.focal_x,a.focal_y,a.render_key
          from assets a left join creators c on c.name=a.creator
          where {where} and (c.enabled=1 or a.creator is null)
          order by a.branch,a.type,a.creator,a.seq''',args)]
    finally:
        con.close()

def eligible_files(source=None):
    source=source or source_path()
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        parts = path.relative_to(source).parts
        if any('repost' in s.lower() or 'misc' in s.lower() for s in parts[:-1]): continue
        yield path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''): h.update(part)
    return h.hexdigest()

def parse(path, source=None):
    source=source or source_path()
    rel=path.relative_to(source)
    m=PATTERN.fullmatch(path.stem)
    if not m: return None, 'Invalid filename metadata'
    d=m.groupdict()
    branch,typ,creator=d['branch'].lower(),d['type'].lower(),d['creator'].lower()
    if branch not in BRANCHES or typ not in TYPES: return None, 'Unknown branch or type code'
    if len(rel.parts)<3 or rel.parts[0].lower()!=creator: return None, 'Creator folder differs from filename'
    if rel.parts[1].lower()!=BRANCHES[branch].lower(): return None, 'Branch folder differs from filename'
    if branch=='mi' and typ!='mis': return None, 'Missiles must use type mis'
    return {'branch':branch,'type':typ,'creator':creator,'bp':int(d['bp']) if d['bp'] else None,'seq':int(d['seq'])}, None

def scan(source=None):
    source=source or source_path()
    if not source.is_dir(): raise ValueError('Library Unavailable: source directory is not accessible')
    con=db()
    count=0; issues=0
    for path in eligible_files(source):
        rel=str(path.relative_to(source)); fields, issue=parse(path,source)
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                width,height=im.size; fmt=im.format
        except Exception as exc:
            fields=None; issue=f'Image decode failed: {exc}'; width=height=None; fmt=None
        hash_value=digest(path)
        old=con.execute('select sha256 from assets where relpath=?',(rel,)).fetchone()
        if old and old['sha256']==hash_value: count+=1; continue
        matches=con.execute('select id,relpath from assets where sha256=? and relpath!=?',(hash_value,rel)).fetchall()
        if not old and len(matches)==1 and not (source/matches[0]['relpath']).exists():
            # A uniquely identified move retains package, usage, and formatting references.
            con.execute('update assets set relpath=? where id=?',(rel,matches[0]['id']))
            old=con.execute('select sha256 from assets where relpath=?',(rel,)).fetchone()
            if old['sha256']==hash_value: count+=1; continue
        if matches:
            fields=None; issue='Ambiguous duplicate content' if len(matches)>1 else f'Exact duplicate of {matches[0]["relpath"]}'
        aid=str(uuid.uuid5(uuid.NAMESPACE_URL, rel))
        values=fields or {}
        if fields: con.execute('insert or ignore into creators(name) values(?)',(fields['creator'],))
        con.execute('''insert into assets(id,relpath,sha256,branch,type,creator,bp,seq,width,height,source_format,status,issue,render_key)
          values(?,?,?,?,?,?,?,?,?,?,?,?,?,null)
          on conflict(relpath) do update set sha256=excluded.sha256,branch=excluded.branch,type=excluded.type,
          creator=excluded.creator,bp=excluded.bp,seq=excluded.seq,width=excluded.width,height=excluded.height,
          source_format=excluded.source_format,status=excluded.status,issue=excluded.issue,render_key=null''',
          (aid,rel,hash_value,values.get('branch'),values.get('type'),values.get('creator'),values.get('bp'),values.get('seq'),width,height,fmt,'review' if issue else 'pending',issue))
        count+=1; issues+=bool(issue)
        if count%50==0: con.commit()
    con.commit(); con.close()
    return {'scanned':count,'new_issues':issues}

def render_asset(a, color, source=None, formatted=FORMATTED, thumbs=THUMBS):
    source=source or source_path()
    from type_icons import draw_icon
    key=hashlib.sha256(json.dumps([a['sha256'],a['mode'],a['focal_x'],a['focal_y'],a['type'],a['bp'],color,RENDER_VERSION]).encode()).hexdigest()
    output=formatted/f"{a['id']}.jpg"; thumb=thumbs/f"{a['id']}.jpg"
    if a['render_key']==key and output.exists() and thumb.exists(): return key
    for p in (formatted,thumbs,TEMP): p.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGB',(1920,1920),BG)
    with Image.open(source/a['relpath']) as raw:
        art=ImageOps.exif_transpose(raw).convert('RGBA')
        if a['mode']=='crop':
            scale=max(1920/art.width,1680/art.height)
            art=art.resize((round(art.width*scale),round(art.height*scale)),Image.Resampling.LANCZOS)
            dx=max(0,art.width-1920); dy=max(0,art.height-1680)
            x=round(dx*a['focal_x']); y=round(dy*a['focal_y'])
            art=art.crop((x,y,x+1920,y+1680)); image.paste(art,(0,0),art)
        else:
            scale=min(1920/art.width,1680/art.height)
            fitted=art.resize((min(1920,round(art.width*scale)),min(1680,round(art.height*scale))),Image.Resampling.LANCZOS)
            if fitted.size!=(1920,1680):
                blurred=ImageOps.fit(art.convert('RGB'),(480,420),method=Image.Resampling.LANCZOS)
                blurred=blurred.filter(ImageFilter.GaussianBlur(12)).resize((1920,1680),Image.Resampling.BILINEAR)
                blurred=Image.blend(blurred,Image.new('RGB',(1920,1680),BG),0.25)
                image.paste(blurred,(0,0))
            x=(1920-fitted.width)//2; y=(1680-fitted.height)//2
            image.paste(fitted,(x,y),fitted)
    d=ImageDraw.Draw(image)
    d.rectangle((0,1680,1919,1919),fill=color)
    red,green,blue=ImageColor.getrgb(color)
    ink='#111111' if (0.2126*red+0.7152*green+0.0722*blue)>150 else '#ffffff'
    draw_icon(d,a['type'],(72,1720,232,1880),ink)
    from PIL import ImageFont
    type_font=ImageFont.truetype(BAR_FONT,132)
    d.text((288,1800),a['type'].upper(),font=type_font,anchor='lm',fill=ink,stroke_width=2,stroke_fill='#ffffff' if ink=='#111111' else '#111111')
    if a['bp'] is not None:
        bp_font=ImageFont.truetype(BAR_FONT,148)
        d.text((1840,1800),f"{a['bp']} BP",font=bp_font,anchor='rm',fill=ink,stroke_width=2,stroke_fill='#ffffff' if ink=='#111111' else '#111111')
    atomic_jpeg(image,output,quality=92)
    preview=image.copy(); preview.thumbnail((480,480),Image.Resampling.LANCZOS)
    atomic_jpeg(preview,thumb,quality=84)
    return key

def atomic_jpeg(im,path,quality):
    with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.jpg',delete=False) as f: tmp=Path(f.name)
    try:
        im.save(tmp,'JPEG',quality=quality,subsampling=0,optimize=True)
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def format_pending(limit=None):
    if not source_path().is_dir(): return 0
    con=db(); rows=con.execute('''select a.*,c.color from assets a join creators c on c.name=a.creator
      where a.status in ('pending','ready') and c.color is not null order by a.relpath''').fetchall()
    done=0
    for a in rows:
        if limit is not None and done>=limit: break
        if not (source_path()/a['relpath']).is_file(): continue
        try:
            key=render_asset(a,a['color'])
            con.execute("update assets set render_key=?,status='ready',issue=null where id=?",(key,a['id']))
        except Exception as exc:
            con.execute("update assets set status='review',issue=? where id=?",(f'Formatting failed: {exc}',a['id']))
        con.commit(); done+=1
    con.close(); return done
