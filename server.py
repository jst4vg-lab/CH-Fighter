from __future__ import annotations

import json
import os
import argparse
import signal
import mimetypes
import re
import threading
import hmac
import time
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs

from crea_core import ROOT,SOURCE,DATA,FORMATTED,THUMBS,db,scan,format_pending,visible_assets
import staging
import mobile_auth
import workspace
import library_settings
from communications.manager import ConnectionManager
import test_submissions
import composer
import discord_reactions
import discord_teams
import gallery_order
import used_transfer

LOCK=threading.Lock()
WAKE=threading.Event()
BUSY=False
WEB_ROOT=Path(os.environ.get('CH_WEB_ROOT', ROOT/'dist')).resolve()
REMOTE_HOST=os.environ.get('CH_REMOTE_HOST','').lower().strip()
DESKTOP_SECRET=os.environ.get('CH_DESKTOP_SECRET','')
CLIPBOARD_LOCK=threading.Lock()
CLIPBOARD_REQUESTS={}
CLIPBOARD_PENDING=None
CONNECTIONS = ConnectionManager()

def host_name(value):
    return (value or '').split(':',1)[0].lower()

def background_format():
    global BUSY
    WAKE.set()
    return True

def format_worker():
    global BUSY
    while True:
        WAKE.wait(); WAKE.clear()
        BUSY=True
        try: format_pending()
        finally: BUSY=False

class Handler(BaseHTTPRequestHandler):
    def mobile_request(self):
        return bool(REMOTE_HOST and host_name(self.headers.get('Host')) == REMOTE_HOST)

    def allowed(self, method, path):
        host=host_name(self.headers.get('Host'))
        if host not in ('127.0.0.1','localhost',REMOTE_HOST) or not host:
            return False
        if not self.mobile_request():
            if DESKTOP_SECRET and path.startswith('/api/'):
                return hmac.compare_digest(self.headers.get('X-CH-Desktop',''),DESKTOP_SECRET)
            return True
        if method=='POST' and self.headers.get('Origin') != f'https://{REMOTE_HOST}': return False
        if path=='/api/mobile/pair' and method=='POST': return True
        if method=='GET' and (path in ('/mobile','/manifest.webmanifest','/mobile-sw.js','/api/mobile/session') or path.startswith(('/assets/','/icons/'))): return True
        if not mobile_auth.valid(self.headers.get('Cookie')): return False
        if method=='GET':
            if re.fullmatch(r'/api/mobile/clipboard/[0-9a-f-]{36}',path): return True
            if path=='/api/assets': return parse_qs(urlparse(self.path).query).get('status',['ready'])[0]=='ready'
            if path.startswith('/api/image/'): return bool(re.fullmatch(r'/api/image/[0-9a-f-]{36}/thumb',path))
            return path in ('/api/state','/api/staging')
        if method=='POST':
            if path=='/api/mobile/clipboard': return True
            return path in ('/api/staging/hot/items','/api/staging/hot/reserve','/api/staging/hot/confirm') or bool(re.fullmatch(r'/api/staging/hot/items/[0-9a-f-]{36}/remove|/api/staging/reserve/[0-9a-f-]{36}/activate|/api/staging/packages/[0-9a-f-]{36}/submission',path))
        return False

    def log_message(self, format, *args):
        if len(args)>1 and str(args[1]).startswith(('4','5')):
            super().log_message(format,*args)

    def send_json(self,data,status=200):
        body=json.dumps(data).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)

    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>1000000: raise ValueError('Request too large')
        return json.loads(self.rfile.read(length) or b'{}')

    def do_GET(self):
        u=urlparse(self.path); p=u.path
        if not self.allowed('GET',p): return self.send_error(403)
        if p=='/api/desktop/clipboard-request':
            global CLIPBOARD_PENDING
            with CLIPBOARD_LOCK:
                request=CLIPBOARD_REQUESTS.get(CLIPBOARD_PENDING) if CLIPBOARD_PENDING else None
                if request:
                    request['status']='processing'
                    result={'id':CLIPBOARD_PENDING,'package_id':request['package_id']}
                    CLIPBOARD_PENDING=None
                else: result=None
            return self.send_json({'request':result})
        m=re.fullmatch(r'/api/mobile/clipboard/([0-9a-f-]{36})',p)
        if m:
            with CLIPBOARD_LOCK: request=CLIPBOARD_REQUESTS.get(m.group(1))
            return self.send_json({'error':'Clipboard request expired'},404) if not request else self.send_json({'status':request['status'],'error':request.get('error'),'count':request.get('count')})
        if p=='/api/mobile/session': return self.send_json({'paired':not self.mobile_request() or mobile_auth.valid(self.headers.get('Cookie'))})
        if p=='/api/mobile/pair-code':
            if self.mobile_request(): return self.send_error(403)
            return self.send_json(mobile_auth.new_code())
        if p=='/api/mobile/config':
            if self.mobile_request(): return self.send_error(403)
            return self.send_json({'url':f'https://{REMOTE_HOST}/mobile' if REMOTE_HOST else None,'port':self.server.server_port})
        if p=='/api/state':
            con=db()
            creators=[dict(x) for x in con.execute('select name,color,enabled from creators order by name')]
            counts={x['status']:x['n'] for x in con.execute('''select a.status,count(*) n from assets a left join creators c on c.name=a.creator
                where c.enabled=1 or a.creator is null group by a.status''')}
            order=gallery_order.read(con)
            con.close();return self.send_json({'creators':creators,'counts':counts,'busy':BUSY,'gallery_order':order})
        if p=='/api/library': return self.send_json(library_settings.status())
        if p=='/api/communications':
            q=parse_qs(u.query);return self.send_json(CONNECTIONS.snapshot(int(q.get('after',['0'])[0]),q.get('channel',[None])[0]))
        if p=='/api/communications/history':
            q=parse_qs(u.query)
            channel=q.get('channel',[''])[0]
            cursors={key:q[key][0] for key in ('before','around','after') if key in q}
            if (not re.fullmatch(r'[0-9]{1,24}', channel) or len(cursors)>1
                    or any(not re.fullmatch(r'[0-9]{1,24}', value) for value in cursors.values())):
                return self.send_json({'error':'Invalid Discord history cursor'},400)
            return self.send_json(CONNECTIONS.history(channel,**cursors))
        if p=='/api/communications/quick-reactions':return self.send_json(discord_reactions.preferences())
        if p=='/api/communications/mentions':
            q=parse_qs(u.query)
            try:return self.send_json(CONNECTIONS.mention_options(q.get('guild',[''])[0],q.get('q',[''])[0]))
            except ValueError as error:return self.send_json({'error':str(error)},400)
        if p=='/api/communications/team-colors':return self.send_json(discord_teams.color_view())
        if p=='/api/communications/teams':
            guild_id=parse_qs(u.query).get('guild',[''])[0]
            try: return self.send_json(discord_teams.members(guild_id))
            except ValueError as error: return self.send_json({'error':str(error)},400)
        if p=='/api/communications/destination':return self.send_json(CONNECTIONS.destination_options())
        if p=='/api/communications/profiles':return self.send_json(CONNECTIONS.status())
        if p=='/api/communications/composer':return self.send_json(composer.status())
        if p=='/api/communications/test-mode':return self.send_json({'enabled':test_submissions.test_mode()})
        if p=='/api/communications/write-status':return self.send_json({**CONNECTIONS.writer().status(),'test_mode':test_submissions.test_mode()})
        if p=='/api/communications/test-send':return self.send_json(test_submissions.current_result())
        if p=='/api/used/export':return self.send_json(used_transfer.export_used())
        if p=='/api/assets':
            q=parse_qs(u.query); status=q.get('status',['ready'])[0]
            return self.send_json(visible_assets(status))
        if p=='/api/staging':return self.send_json(staging.snapshot())
        if p=='/api/workspace/draft':return self.send_json(workspace.current())
        if p=='/api/workspace/drafts':return self.send_json(workspace.history())
        if p.startswith('/api/image/'):
            parts=p.split('/')
            if len(parts)!=5 or parts[4] not in ('thumb','formatted'): return self.send_error(404)
            aid=parts[3]
            if not re.fullmatch(r'[0-9a-f-]{36}',aid):return self.send_error(404)
            path=(THUMBS if parts[4]=='thumb' else FORMATTED)/f'{aid}.jpg'
            return self.file(path,'image/jpeg')
        if p=='/api/health': return self.send_json({'ok':True})
        path=WEB_ROOT/p.lstrip('/')
        if p=='/' or not path.is_file(): path=WEB_ROOT/'index.html'
        if path.is_file() and path.resolve().is_relative_to(WEB_ROOT): return self.file(path,mimetypes.guess_type(path)[0] or 'application/octet-stream')
        return self.send_error(404)

    def file(self,path,typ):
        if not path.is_file(): return self.send_error(404)
        body=path.read_bytes();self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Cache-Control','no-cache');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

    def do_POST(self):
        global BUSY
        try:
            p=urlparse(self.path).path; body=self.body()
            if not self.allowed('POST',p): return self.send_error(403)
            if p=='/api/mobile/clipboard':
                global CLIPBOARD_PENDING
                package_id=body.get('package_id')
                hot=staging.snapshot()['hot']
                if not hot or hot['id']!=package_id or hot['missing_count']: return self.send_json({'error':'Hot package is unavailable'},409)
                with CLIPBOARD_LOCK:
                    if CLIPBOARD_PENDING: return self.send_json({'error':'Clipboard request already pending'},409)
                    for old_id,old in list(CLIPBOARD_REQUESTS.items()):
                        if old['created']<time.time()-120: del CLIPBOARD_REQUESTS[old_id]
                    request_id=str(uuid.uuid4())
                    CLIPBOARD_REQUESTS[request_id]={'package_id':package_id,'status':'pending','created':time.time()}
                    CLIPBOARD_PENDING=request_id
                return self.send_json({'id':request_id})
            if p=='/api/desktop/clipboard-result':
                request_id=body.get('id')
                with CLIPBOARD_LOCK:
                    request=CLIPBOARD_REQUESTS.get(request_id)
                    if not request or request['status']!='processing': return self.send_json({'error':'Clipboard request not found'},404)
                    request['status']='done' if body.get('ok') is True else 'error'
                    request['count']=body.get('count') if request['status']=='done' else None
                    request['error']=str(body.get('error','Clipboard failed'))[:300] if request['status']=='error' else None
                return self.send_json({'ok':True})
            if p=='/api/mobile/pair':
                token=mobile_auth.pair(body.get('code'))
                if not token:return self.send_json({'error':'Invalid or expired code'},401)
                payload=b'{"paired":true}'
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Set-Cookie',f'ch_mobile={token}; HttpOnly; Secure; SameSite=Strict; Path=/')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers();self.wfile.write(payload);return
            if p=='/api/mobile/revoke':
                if self.mobile_request(): return self.send_error(403)
                mobile_auth.revoke();return self.send_json({'ok':True})
            if p=='/api/staging/hot/items':return self.send_json(staging.add_to_hot(body.get('asset_ids',[])))
            if p=='/api/workspace/draft':return self.send_json(workspace.save(body.get('text'),body.get('asset_ids'),body.get('channel_url',''),body.get('reply_to_id','')))
            if p=='/api/workspace/draft/transition':return self.send_json(workspace.transition(body.get('status'),body.get('manual_confirmation',False)))
            if p=='/api/workspace/draft/new':return self.send_json(workspace.new_draft())
            if p=='/api/communications/quick-reactions':return self.send_json(discord_reactions.save(body.get('slots')))
            if p=='/api/communications/react':return self.send_json(discord_reactions.add(body, CONNECTIONS.writer()))
            if p=='/api/communications/team-colors':
                enabled=body.get('enabled')
                if type(enabled) is not bool:raise ValueError('Invalid team color preference')
                return self.send_json(discord_teams.color_view(enabled))
            if p=='/api/communications/teams':
                return self.send_json(discord_teams.assign(body.get('guild_id'),body.get('user_id'),body.get('name'),body.get('team')))
            if p=='/api/gallery/order':return self.send_json(gallery_order.save(body))
            if p=='/api/communications/destination':return self.send_json(CONNECTIONS.select_destination(body.get('profile_id'),body.get('guild_id'),body.get('channel_id')))
            if p=='/api/communications/profiles/shared':return self.send_json(CONNECTIONS.select_shared(body.get('profile_id')))
            if p=='/api/communications/profiles/select':return self.send_json(CONNECTIONS.select(body.get('read'),body.get('write')))
            if p=='/api/communications/profiles/reconnect':return self.send_json(CONNECTIONS.reconnect(body.get('profile_id')))
            if p=='/api/communications/test-mode':return self.send_json(test_submissions.set_test_mode(body.get('enabled')))
            if p=='/api/communications/composer':return self.send_json(composer.send(body, CONNECTIONS.writer()))
            if p=='/api/communications/composer/resolve':return self.send_json(composer.resolve(body.get('id'), body.get('posted')))
            if p=='/api/communications/test-send':
                provider = CONNECTIONS.writer(configured_test=True)
                return self.send_json(test_submissions.send_current(body.get('draft_id'), provider, body.get('destination'), body.get('test_mode')))
            if p=='/api/library/apply':return self.send_json(library_settings.apply(body.get('path')))
            if p=='/api/library/rescan':
                if not LOCK.acquire(blocking=False):return self.send_json({'error':'Import busy'},409)
                try: result=library_settings.rescan()
                finally: LOCK.release()
                background_format();return self.send_json(result)
            m=re.fullmatch(r'/api/staging/hot/items/([0-9a-f-]{36})/remove',p)
            if m:return self.send_json(staging.remove_from_hot(m.group(1)))
            if p=='/api/staging/hot/reserve':return self.send_json(staging.reserve_hot(body.get('package_id'),body.get('submission'),body.get('mentions')))
            if p=='/api/staging/hot/confirm':
                if self.mobile_request() and (not isinstance(body.get('package_id'),str) or not isinstance(body.get('asset_ids'),list)):
                    return self.send_json({'error':'Mobile confirmation requires a package and its crea'},400)
                return self.send_json(staging.confirm_hot(body.get('package_id'),body.get('asset_ids')))
            if p=='/api/staging/deployments/undo':return self.send_json(staging.undo_last_deployment())
            if p=='/api/used/import':return self.send_json(used_transfer.import_used(body))
            if p=='/api/used/restore':return self.send_json(staging.restore(None if body.get('all') else body.get('asset_ids',[])))
            m=re.fullmatch(r'/api/staging/reserve/([0-9a-f-]{36})/activate',p)
            if m:return self.send_json(staging.activate(m.group(1)))
            m=re.fullmatch(r'/api/staging/packages/([0-9a-f-]{36})/(submission|acknowledge)',p)
            if m:return self.send_json(staging.save_submission(m.group(1),body.get('submission'),body.get('mentions')) if m.group(2)=='submission' else staging.acknowledge(m.group(1)))
            if p=='/api/import':
                if not LOCK.acquire(blocking=False): return self.send_json({'error':'Import busy'},409)
                try: result=scan()
                finally: LOCK.release()
                background_format(); return self.send_json(result)
            if p.startswith('/api/creators/') and p.endswith('/enabled'):
                name=p.split('/')[3]; enabled=body.get('enabled')
                if not isinstance(enabled,bool):return self.send_json({'error':'Use true or false'},400)
                con=db();cur=con.execute('update creators set enabled=? where name=?',(int(enabled),name))
                if cur.rowcount==0:con.close();return self.send_json({'error':'Unknown creator'},404)
                con.commit();con.close();return self.send_json({'ok':True})
            if p.startswith('/api/creators/') and p.endswith('/color'):
                name=p.split('/')[3]; color=body.get('color')
                if not re.fullmatch(r'#[0-9a-fA-F]{6}',color or ''):return self.send_json({'error':'Use a hex color'},400)
                con=db(); cur=con.execute('update creators set color=? where name=?',(color.upper(),name))
                if cur.rowcount==0:con.close();return self.send_json({'error':'Unknown creator'},404)
                con.execute('update assets set render_key=null where creator=? and status=\'ready\'',(name,))
                con.commit();con.close(); background_format();return self.send_json({'ok':True})
            if p.startswith('/api/assets/') and p.endswith('/format'):
                aid=p.split('/')[3]; mode=body.get('mode');x=body.get('focal_x',.5);y=body.get('focal_y',.5)
                if mode not in ('fit','crop') or not all(isinstance(v,(int,float)) and 0<=v<=1 for v in (x,y)):return self.send_json({'error':'Invalid crop'},400)
                con=db();cur=con.execute('update assets set mode=?,focal_x=?,focal_y=?,render_key=null where id=? and status!=\'review\'',(mode,x,y,aid))
                if cur.rowcount==0:con.close();return self.send_json({'error':'Asset not found'},404)
                con.commit();con.close();background_format();return self.send_json({'ok':True})
            return self.send_error(404)
        except ValueError as exc:return self.send_json({'error':str(exc)},400)
        except Exception as exc: return self.send_json({'error':str(exc)},500)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if os.environ.get('CH_DESKTOP') == '1':
        from desktop_data import migrate
        migrate(Path(os.environ['CH_LEGACY_DATA']), DATA)
    db().close()
    composer.recover()
    mobile_auth.setup()
    CONNECTIONS.start()
    threading.Thread(target=format_worker,daemon=True).start()
    background_format()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'CH_READY {server.server_port}',flush=True)
    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        CONNECTIONS.stop()
        server.server_close()
