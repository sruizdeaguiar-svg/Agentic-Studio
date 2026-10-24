"""Opt-in project-scoped LAN HTTPS gateway. Tokens never replace the desktop session.
Native clients pin the certificate shown on the Mac; each pairing code is single-use.
"""
import collections,hashlib,http.client,ipaddress,json,os,secrets,socket,ssl,subprocess,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlencode

class Gateway:
    def __init__(self,local,backend,token,project,query,scope):
        self.local=Path(local);self.backend=backend;self.token=token;self.project_lookup=project;self.query=query;self.scope=scope
        self.lock=threading.RLock();self.server=None;self.project='';self.project_scope='';self.codes={};self.sessions={};self.address='';self.pin=''
    def status(self):
        with self.lock:
            now=time.time();self.codes={k:v for k,v in self.codes.items() if v>now};self.sessions={k:v for k,v in self.sessions.items() if v>now}
            return {'running':self.server is not None,'url':self.address,'project':self.project,'clients':len(self.sessions),'fingerprint':self.pin}
    def scope_valid(self):
        try:return bool(self.project and self.project_scope==self.scope(self.project))
        except (ValueError,OSError,KeyError):return False
    def stop(self):
        with self.lock:server=self.server;self.server=None;self.codes.clear();self.sessions.clear();self.address='';self.project='';self.project_scope=''
        if server:server.shutdown();server.server_close()
        return {'running':False}
    def certificate(self,host):
        self.local.mkdir(parents=True,exist_ok=True,mode=0o700)
        cert=self.local/'lan-cert.pem';key=self.local/'lan-key.pem';leaf=self.local/'lan-leaf.pem';ca=self.local/'lan-ca.pem';cakey=self.local/'lan-ca-key.pem';metadata=self.local/'lan-cert.json'
        valid=cert.exists() and key.exists() and leaf.exists() and ca.exists() and metadata.exists() and json.loads(metadata.read_text()).get('host')==host
        if valid:valid=subprocess.run(['/usr/bin/openssl','x509','-checkend','86400','-noout','-in',str(leaf)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
        if not valid:
            run=lambda args:subprocess.run(['/usr/bin/openssl']+args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            run(['req','-x509','-newkey','rsa:2048','-sha256','-nodes','-keyout',str(cakey),'-out',str(ca),'-days','3650','-subj','/CN=Agentic Studio LAN CA','-addext','basicConstraints=critical,CA:TRUE,pathlen:0','-addext','keyUsage=critical,keyCertSign,cRLSign'])
            csr=self.local/'lan-request.csr';ext=self.local/'lan-extensions.cnf'
            run(['req','-new','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(csr),'-subj','/CN=Agentic Studio LAN'])
            ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:'+host+',IP:127.0.0.1\n')
            run(['x509','-req','-in',str(csr),'-CA',str(ca),'-CAkey',str(cakey),'-CAcreateserial','-out',str(leaf),'-days','365','-sha256','-extfile',str(ext)])
            cert.write_text(leaf.read_text()+ca.read_text())
            for path in (key,cakey,cert,leaf,ca):path.chmod(0o600)
            metadata.write_text(json.dumps({'host':host}))
        self.pin=hashlib.sha256(ssl.PEM_cert_to_DER_cert(leaf.read_text())).hexdigest()
        return cert,key
    def start(self,pid,approved=False,host=None):
        if approved is not True:raise ValueError('Confirma activar el acceso al proyecto en red local.')
        self.project_lookup(pid)
        if host is None:
            for interface in ('en0','en1','en2'):
                p=subprocess.run(['/usr/sbin/ipconfig','getifaddr',interface],capture_output=True,text=True)
                candidate=p.stdout.strip()
                if p.returncode==0 and candidate:
                    host=candidate;break
        try:address=ipaddress.ip_address(host or '')
        except ValueError:raise ValueError('No se encontró una interfaz de red local IPv4.') from None
        if address.version!=4 or not (address.is_loopback or any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))):raise ValueError('Usa una interfaz privada de tu red local.')
        with self.lock:same=self.server is not None and self.project==pid and self.project_scope==self.scope(pid)
        if not same:
            self.stop();cert,key=self.certificate(str(address));self.project=pid;self.project_scope=self.scope(pid)
            outer=self
            class Handler(BaseHTTPRequestHandler):
                protocol_version='HTTP/1.1'
                def log_message(self,*args):pass
                def json(self,obj,status=200,headers=None):
                    raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
                    for k,v in (headers or {}).items():self.send_header(k,v)
                    self.end_headers();self.wfile.write(raw)
                def authorized(self):
                    if self.headers.get('Host')!=outer.address.removeprefix('https://'):return False
                    if self.headers.get('Origin') not in (None,outer.address):return False
                    if not outer.scope_valid():return False
                    auth=self.headers.get('Authorization','').removeprefix('Bearer ')
                    import http.cookies
                    cookie=http.cookies.SimpleCookie()
                    try:cookie.load(self.headers.get('Cookie',''))
                    except http.cookies.CookieError:return False
                    if not auth and cookie.get('studio_mobile'):auth=cookie['studio_mobile'].value
                    with outer.lock:return bool(auth and outer.sessions.get(auth,0)>time.time())
                def do_GET(self):
                    parsed=urlsplit(self.path);params=parse_qs(parsed.query)
                    if parsed.path=='/' and 'pair' in params:
                        if self.headers.get('Host')!=outer.address.removeprefix('https://'):return self.json({'error':'Host no permitido.'},403)
                        if len(params['pair'])!=1:return self.json({'error':'Vinculación no válida.'},403)
                        with outer.lock:
                            expiry=outer.codes.pop(params['pair'][0],0)
                            if expiry<time.time() or not outer.scope_valid():return self.json({'error':'Vinculación caducada, usada o permisos cambiados.'},403)
                            if len(outer.sessions)>=8:return self.json({'error':'Máximo ocho clientes. Revoca las conexiones desde el Mac.'},403)
                            auth=secrets.token_urlsafe(32);outer.sessions[auth]=time.time()+86400
                        self.send_response(303);self.send_header('Location','/');self.send_header('Set-Cookie','studio_mobile='+auth+'; Secure; HttpOnly; SameSite=Strict; Path=/');self.send_header('Content-Length','0');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers();return
                    if not self.authorized():return self.json({'error':'Vuelve a vincular el móvil desde el Mac; sesión o permisos cambiados.'},401)
                    if parsed.path in ('/','/mobile.js','/mobile.css'):
                        path=Path(__file__).parent/'web'/('mobile.html' if parsed.path=='/' else parsed.path[1:]);raw=path.read_bytes();self.send_response(200);self.send_header('Content-Type',{'/':'text/html; charset=utf-8','/mobile.js':'text/javascript','/mobile.css':'text/css'}[parsed.path]);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'");self.send_header('Referrer-Policy','no-referrer');self.end_headers();self.wfile.write(raw);return
                    self.proxy('GET',parsed,params,None)
                def do_POST(self):
                    if not self.authorized():return self.json({'error':'Vinculación no válida.'},401)
                    try:
                        length=int(self.headers.get('Content-Length',0))
                        if length<0 or length>250000:raise ValueError('Petición demasiado grande.')
                        body=json.loads(self.rfile.read(length));parsed=urlsplit(self.path)
                        self.proxy('POST',parsed,parse_qs(parsed.query),body)
                    except (ValueError,KeyError,TypeError):self.json({'error':'Petición no válida.'},400)
                def proxy(self,method,parsed,params,body):
                    path=parsed.path
                    try:
                        if not outer.allowed(method,path,params,body):return self.json({'error':'Operación fuera del proyecto o reservada al Mac.'},403)
                        conn=http.client.HTTPConnection('127.0.0.1',outer.backend(),timeout=180)
                        headers={'Authorization':'Bearer '+outer.token,'Content-Type':'application/json'}
                        conn.request(method,self.path,body=None if body is None else json.dumps(body).encode(),headers=headers);res=conn.getresponse()
                        if path=='/api/state' and res.status==200:
                            data=json.load(res);data['projects']=[p for p in data['projects'] if p['id']==outer.project];data['sessions']=[s for s in data['sessions'] if s['project_id']==outer.project];data['workspace']={'project':outer.project,'session':next((s['id'] for s in data['sessions']), '')};data.pop('data_path',None);data.pop('engine_config',None);data['skills']=[];conn.close();return self.json(data)
                        self.send_response(res.status);self.send_header('Content-Type',res.getheader('Content-Type','application/json'));self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers()
                        if 'ndjson' in res.getheader('Content-Type',''):
                            while True:
                                raw=res.readline(512001)
                                if not raw:break
                                if len(raw)>512000:raise ValueError('Evento demasiado grande.')
                                self.wfile.write(raw);self.wfile.flush()
                        else:
                            while True:
                                raw=res.read(65536)
                                if not raw:break
                                self.wfile.write(raw)
                        self.close_connection=True;conn.close()
                    except (ValueError,KeyError,OSError,http.client.HTTPException):
                        self.close_connection=True
                
            server=ThreadingHTTPServer((str(address),0),Handler);server.daemon_threads=True
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(str(cert),str(key));server.socket=context.wrap_socket(server.socket,server_side=True)
            with self.lock:self.server=server;self.address='https://'+str(address)+':'+str(server.server_port)
            threading.Thread(target=server.serve_forever,daemon=True).start()
        with self.lock:
            self.status()
            if len(self.codes)>=4:raise ValueError('Ya hay cuatro vinculaciones pendientes; espera cinco minutos o desactiva la red.')
            code=secrets.token_urlsafe(32);self.codes[code]=time.time()+300
            pair='agenticstudio://pair?'+urlencode({'url':self.address,'token':code,'pin':self.pin})
            return {**self.status(),'pair_url':pair,'expires_in':300}
    def owns_session(self,sid):return bool(self.query('SELECT id FROM sessions WHERE id=? AND project_id=?',(sid,self.project),True))
    def allowed(self,method,path,params,body):
        if method=='GET':
            if path in ('/api/state','/api/resources','/api/models'):return True
            if path in ('/api/messages','/api/proposals','/api/export','/api/command-live'):return self.owns_session(params.get('session',[''])[0])
            if path in ('/api/files','/api/search'):return params.get('project')==[self.project]
            return False
        if path=='/api/sessions':return body.get('project_id')==self.project
        if path=='/api/chat':return self.owns_session(body.get('session_id',''))
        if path in ('/api/extension/resolve','/api/proposal/resolve','/api/command/resolve'):
            table={'/api/extension/resolve':'extension_actions','/api/proposal/resolve':'proposals','/api/command/resolve':'commands'}[path]
            return bool(self.query('SELECT id FROM '+table+' WHERE id=? AND project_id=?',(body.get('id',''),self.project),True))
        return False
