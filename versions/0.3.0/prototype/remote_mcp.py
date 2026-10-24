"""Bounded Streamable HTTP MCP + public-client OAuth/PKCE. Standard library only.
Credentials are accessed solely through the native Keychain bridge. No HTTP redirects,
proxy environment, persistent SSE listener, remote roots, or automatic tool retries.
"""
import base64
import hashlib
import http.client
import ipaddress
import json
import secrets
import ssl
import threading
import time
from urllib.parse import urlsplit, urlencode, parse_qs

LIMIT=2_100_000
VERSIONS=('2025-11-25','2025-06-18','2025-03-26')

def endpoint(value):
    if not isinstance(value,str) or len(value)>4096:raise ValueError('URL remota no válida.')
    p=urlsplit(value)
    if p.username or p.password or p.fragment or not p.hostname or p.scheme not in ('http','https') or any(ord(c)<33 for c in value):raise ValueError('URL remota sin credenciales ni fragmentos.')
    if p.scheme=='http':
        try:local=ipaddress.ip_address(p.hostname).is_loopback
        except ValueError:local=False
        if not local:raise ValueError('MCP y OAuth requieren HTTPS; HTTP solo en una IP loopback literal.')
    _=p.port
    return value

def request(url,method='GET',body=None,headers=None,timeout=20):
    p=urlsplit(endpoint(url));conn=(http.client.HTTPSConnection(p.hostname,p.port,timeout=timeout,context=ssl.create_default_context()) if p.scheme=='https' else http.client.HTTPConnection(p.hostname,p.port,timeout=timeout))
    try:
        conn.request(method,p.path+('?' + p.query if p.query else '') or '/',body=body,headers=headers or {})
        res=conn.getresponse();status=res.status;hs={k.lower():v for k,v in res.getheaders()}
        if 300<=status<400:raise ValueError('Redirección HTTP rechazada; revisa el endpoint configurado.')
        data=bytearray();deadline=time.monotonic()+25
        if hs.get('content-type','').split(';')[0]=='text/event-stream':
            event=[]
            while time.monotonic()<deadline:
                line=res.readline(LIMIT-len(data)+1)
                if not line:break
                data.extend(line)
                if len(data)>LIMIT:raise ValueError('Respuesta remota demasiado grande.')
                if line.startswith(b'data:'):event.append(line[5:].strip())
                if not line.strip() and event:
                    msg=json.loads(b'\n'.join(event));event=[]
                    if isinstance(msg,dict) and ('result' in msg or 'error' in msg):return status,hs,msg
            raise ValueError('Stream MCP sin respuesta final dentro del límite.')
        raw=res.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('Respuesta remota demasiado grande.')
        if status>=400:return status,hs,{}
        try:obj=json.loads(raw) if raw else {}
        except (ValueError,UnicodeError):raise ValueError('Respuesta remota JSON no válida.') from None
        return status,hs,obj
    except (http.client.HTTPException,TimeoutError) as error:raise ValueError('Conexión remota interrumpida; no se reintenta la acción.') from None
    finally:conn.close()

def ok_json(url,method='GET',form=None):
    body=urlencode(form).encode() if form is not None else None
    status,_,obj=request(url,method,body,{'Accept':'application/json',**({'Content-Type':'application/x-www-form-urlencoded'} if form is not None else {})})
    if status!=200 or not isinstance(obj,dict):raise ValueError('El proveedor OAuth rechazó la petición (HTTP %s).'%status)
    return obj

class HTTPClient:
    def __init__(self,spec,credential):
        self.url=endpoint(spec['url']);self.credential=credential;self.proc=None;self.closed=False;self.last=time.monotonic();self.lock=threading.Lock();self.serial=0;self.session='';self.last_token='';self.version=VERSIONS[0];self.tools=[]
        try:
            result=self.request('initialize',{'protocolVersion':self.version,'capabilities':{},'clientInfo':{'name':'Agentic Studio','version':'0.3.0'}})
            if result.get('protocolVersion') not in VERSIONS:raise ValueError('Versión Streamable HTTP MCP no admitida.')
            self.version=result['protocolVersion'];self.request('notifications/initialized',{},notification=True)
            cursor=None
            for _ in range(4):
                page=self.request('tools/list',{'cursor':cursor} if cursor else {})
                self.tools+=page.get('tools',[]);cursor=page.get('nextCursor')
                if len(self.tools)>128:raise ValueError('Máximo 128 herramientas remotas.')
                if not cursor:break
            if cursor or any(not isinstance(t,dict) or not isinstance(t.get('name'),str) or len(t['name'])>128 for t in self.tools):raise ValueError('Catálogo MCP remoto no válido o demasiado grande.')
        except BaseException:self.close();raise
    def headers(self):
        h={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':self.version}
        token=self.credential();self.last_token=token
        if token:h['Authorization']='Bearer '+token
        if self.session:h['Mcp-Session-Id']=self.session
        return h
    def request(self,method,params,notification=False):
        with self.lock:
            if self.closed:raise ValueError('Cliente MCP cerrado.')
            self.serial+=1;rid=self.serial;self.last=time.monotonic()
            body={'jsonrpc':'2.0','method':method,'params':params}
            if not notification:body['id']=rid
            raw=json.dumps(body).encode()
            if len(raw)>250000:raise ValueError('Petición MCP demasiado grande.')
            status,hs,msg=request(self.url,'POST',raw,self.headers())
            if status in (401,403):raise ValueError('MCP requiere autorización OAuth o permisos adicionales. Pide al usuario conectar OAuth; no se amplían permisos automáticamente.')
            if status==404 and self.session:raise ValueError('Sesión MCP caducada. Reconecta antes de una nueva acción; no se reintenta.')
            if status not in (200,202):raise ValueError('Servidor MCP rechazó la petición (HTTP %s).'%status)
            if method=='initialize':
                self.session=hs.get('mcp-session-id','')
                if len(self.session)>512 or any(ord(c)<33 or ord(c)>126 for c in self.session):raise ValueError('Sesión MCP no válida.')
            if notification and status==202:return {}
            if not isinstance(msg,dict) or msg.get('jsonrpc')!='2.0' or msg.get('id')!=rid:raise ValueError('Respuesta MCP no corresponde a la petición.')
            if 'error' in msg:raise ValueError('El servidor MCP devolvió un error; revisa la acción antes de repetirla.')
            if not isinstance(msg.get('result'),dict):raise ValueError('Resultado MCP no válido.')
            self.last=time.monotonic();return msg['result']
    def call(self,name,arguments):
        if name not in [t['name'] for t in self.tools]:raise ValueError('Herramienta remota no anunciada.')
        try:return self.request('tools/call',{'name':name,'arguments':arguments})
        except (ValueError,OSError):self.close();raise
    def close(self):
        if self.closed:return
        self.closed=True
        if self.session:
            # No refresh or credential requests during idle/quit cleanup.
            try:request(self.url,'DELETE',headers={'Mcp-Session-Id':self.session,'MCP-Protocol-Version':self.version,**({'Authorization':'Bearer '+self.last_token} if self.last_token else {})},timeout=2)
            except (ValueError,OSError):pass
        self.session='';self.last_token='';self.tools=[];self.credential=lambda:''

class OAuth:
    def __init__(self,spec,scope,native):
        self.spec=spec;self.scope=scope;self.native=native;self.lock=threading.RLock();self.prepared={};self.flows={}
    def identity(self,pid,sid):
        spec=self.spec(pid,sid)
        return hashlib.sha256(json.dumps([pid,sid,spec['url']],sort_keys=True).encode()).hexdigest()
    def vault(self,pid,sid,op,value=None):
        args={'account':self.identity(pid,sid)}
        if value is not None:args['value']=json.dumps(value,separators=(',',':'))
        return self.native(pid,'vault_'+op,args).get('value','')
    def record(self,pid,sid):
        raw=self.vault(pid,sid,'get')
        return json.loads(raw) if raw else {}
    def status(self,pid,sid):
        r=self.record(pid,sid)
        return {'connected':bool(r.get('access_token')),'scopes':r.get('scopes',[]),'expires_at':r.get('expires_at',0)}
    def forget(self,pid,sid):
        self.vault(pid,sid,'delete')
        with self.lock:
            self.flows={k:v for k,v in self.flows.items() if (v['pid'],v['sid'])!=(pid,sid)}
        return {'disconnected':True}
    def cancel(self):
        with self.lock:self.flows.clear();self.prepared.clear()
    def expire(self):
        now=time.time()
        with self.lock:
            self.prepared={k:v for k,v in self.prepared.items() if v['deadline']>now}
            self.flows={k:v for k,v in self.flows.items() if v['deadline']>now}
    def prepare(self,pid,sid):
        url=endpoint(self.spec(pid,sid)['url']);p=urlsplit(url);base=p.scheme+'://'+p.netloc
        # A challenge may only point to metadata on the configured resource origin.
        status,hs,_=request(url,'POST',json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':VERSIONS[0],'capabilities':{},'clientInfo':{'name':'Agentic Studio','version':'0.3.0'}}}).encode(),{'Content-Type':'application/json','Accept':'application/json, text/event-stream'})
        import re
        challenge=hs.get('www-authenticate','');match=re.search(r'resource_metadata="([^"\r\n]+)"',challenge)
        candidates=[match.group(1)] if match else [base+'/.well-known/oauth-protected-resource'+p.path.rstrip('/'),base+'/.well-known/oauth-protected-resource']
        metadata=None
        for candidate in dict.fromkeys(candidates):
            q=urlsplit(endpoint(candidate))
            if (q.scheme,q.netloc)!=(p.scheme,p.netloc):raise ValueError('Metadatos OAuth fuera del origen MCP; configura explícitamente el endpoint correcto.')
            try:metadata=ok_json(candidate);break
            except ValueError:
                if match:raise
        if not metadata or metadata.get('resource')!=url:raise ValueError('El recurso OAuth no coincide exactamente con el endpoint MCP.')
        issuers=metadata.get('authorization_servers',[])
        if not isinstance(issuers,list) or not 1<=len(issuers)<=8:raise ValueError('El recurso no anuncia un proveedor OAuth válido.')
        for issuer in issuers:
            endpoint(issuer)
            if urlsplit(issuer).query:raise ValueError('Issuer OAuth no válido.')
        scopes_match=re.search(r'\bscope="([^"\r\n]*)"',challenge)
        scopes=scopes_match.group(1).split() if scopes_match else metadata.get('scopes_supported',[])
        if not isinstance(scopes,list) or len(scopes)>64 or any(not isinstance(s,str) or len(s)>200 for s in scopes):raise ValueError('Scopes OAuth no válidos.')
        self.expire()
        key=secrets.token_urlsafe(24)
        with self.lock:
            if len(self.prepared)>=8:raise ValueError('Demasiados intentos OAuth pendientes; espera cinco minutos.')
            self.prepared[key]={'pid':pid,'sid':sid,'scope':self.scope(pid),'resource':url,'issuers':issuers,'scopes':scopes,'deadline':time.time()+300}
        return {'id':key,'resource':url,'issuers':issuers,'scopes':scopes,'default_scopes':scopes if scopes_match else []}
    def prepared_for(self,key,pid,sid):
        self.expire();v=self.prepared.get(key)
        if not v or (v['pid'],v['sid'])!=(pid,sid) or v['scope']!=self.scope(pid):raise ValueError('Preparación OAuth caducada o permisos del proyecto cambiados.')
        return v
    def metadata(self,pid,sid,key,issuer):
        v=self.prepared_for(key,pid,sid)
        if issuer not in v['issuers']:raise ValueError('Proveedor OAuth no anunciado por el recurso.')
        p=urlsplit(issuer);base=p.scheme+'://'+p.netloc;path=p.path.rstrip('/')
        candidates=[base+'/.well-known/oauth-authorization-server'+path,base+'/.well-known/openid-configuration'+path]
        if path:candidates.append(issuer.rstrip('/')+'/.well-known/openid-configuration')
        meta=None
        for url in candidates:
            try:meta=ok_json(url);break
            except ValueError:pass
        if not meta or meta.get('issuer')!=issuer:raise ValueError('No se pudo verificar el issuer OAuth exacto.')
        for field in ('authorization_endpoint','token_endpoint'):endpoint(meta.get(field))
        if 'S256' not in meta.get('code_challenge_methods_supported',[]):raise ValueError('El proveedor no anuncia PKCE S256 obligatorio.')
        if 'none' not in meta.get('token_endpoint_auth_methods_supported',['client_secret_basic']):raise ValueError('Se necesita un cliente público OAuth (token auth: none).')
        if meta.get('registration_endpoint'):endpoint(meta['registration_endpoint'])
        v['metadata']={k:meta[k] for k in ('issuer','authorization_endpoint','token_endpoint','registration_endpoint') if k in meta}
        return {**v['metadata'],'scopes':v['scopes'],'resource':v['resource']}
    def start(self,pid,sid,key,client_id,scopes,redirect):
        with self.lock:
            v=dict(self.prepared_for(key,pid,sid));meta=v.get('metadata')
            if not meta:raise ValueError('Revisa primero los endpoints del proveedor OAuth.')
            if not isinstance(scopes,list) or len(scopes)>64 or any(not isinstance(s,str) or not s or len(s)>200 or any(ord(c)<=32 or ord(c)>=127 or c in '"\\' for c in s) for s in scopes):raise ValueError('Scopes no válidos.')
            if not set(scopes).issubset(v['scopes']):raise ValueError('Scope no anunciado; repite el descubrimiento ante permisos adicionales.')
            if not isinstance(client_id,str) or len(client_id)>2048 or any(ord(c)<32 for c in client_id):raise ValueError('Client ID no válido.')
            if not client_id:
                registration=meta.get('registration_endpoint')
                if not registration:raise ValueError('Introduce el client_id público registrado por tu proveedor; no ofrece registro dinámico.')
                status,_,registered=request(registration,'POST',json.dumps({'client_name':'Agentic Studio','redirect_uris':[redirect],'grant_types':['authorization_code','refresh_token'],'response_types':['code'],'token_endpoint_auth_method':'none'}).encode(),{'Content-Type':'application/json','Accept':'application/json'})
                if status not in (200,201) or not isinstance(registered,dict) or registered.get('client_secret') or registered.get('token_endpoint_auth_method','none')!='none' or not registered.get('client_id'):raise ValueError('El proveedor no registró un cliente público compatible.')
                client_id=registered['client_id']
                if not isinstance(client_id,str) or not client_id or len(client_id)>2048 or any(ord(c)<32 for c in client_id):raise ValueError('Client ID registrado no válido.')
            if len(self.flows)>=4:raise ValueError('Demasiadas autorizaciones abiertas.')
            state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
            flow={**v,'client_id':client_id,'scopes':scopes,'redirect':redirect,'verifier':verifier,'deadline':time.time()+300}
            self.flows[state]=flow
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params={'response_type':'code','client_id':client_id,'redirect_uri':redirect,'state':state,'code_challenge':challenge,'code_challenge_method':'S256','resource':v['resource']}
        if scopes:params['scope']=' '.join(scopes)
        target=meta['authorization_endpoint']
        if set(parse_qs(urlsplit(target).query)).intersection(params):
            with self.lock:self.flows.pop(state,None)
            raise ValueError('Endpoint de autorización contiene parámetros OAuth reservados.')
        url=target+('&' if urlsplit(target).query else '?')+urlencode(params)
        try:self.native(pid,'oauth_open',{'url':url})
        except BaseException:
            with self.lock:self.flows.pop(state,None)
            raise
        return {'started':True,'expires_in':300}
    def save_token(self,f,token,previous=None):
        if not isinstance(token,dict) or str(token.get('token_type','')).lower()!='bearer' or not isinstance(token.get('access_token'),str) or not token['access_token'] or len(token['access_token'])>16000 or any(ord(c)<=32 or ord(c)>=127 for c in token['access_token']):raise ValueError('Respuesta OAuth sin token Bearer válido.')
        scopes=token.get('scope',' '.join(f['scopes'])).split()
        if not set(scopes).issubset(f['scopes']):raise ValueError('El proveedor devolvió permisos superiores a los aprobados.')
        lifetime=float(token.get('expires_in',300))
        if not 0<lifetime<=31536000:raise ValueError('Caducidad OAuth no válida.')
        r={k:f[k] for k in ('metadata','client_id','resource','scopes')};r.update(scopes=scopes,access_token=token['access_token'],refresh_token=token.get('refresh_token',(previous or {}).get('refresh_token','')),expires_at=time.time()+lifetime)
        if not isinstance(r['refresh_token'],str) or len(r['refresh_token'])>16000:raise ValueError('Refresh token no válido.')
        self.vault(f['pid'],f['sid'],'put',r)
        return r
    def callback(self,params):
        if any(len(v)!=1 for v in params.values()) or not params.get('state'):raise ValueError('Callback OAuth no válido.')
        self.expire()
        with self.lock:f=self.flows.pop(params['state'][0],None)
        if not f or f['scope']!=self.scope(f['pid']):raise ValueError('Estado OAuth caducado, ya utilizado o permisos cambiados.')
        if params.get('iss') and params['iss']!=[f['metadata']['issuer']]:raise ValueError('Issuer del callback OAuth no coincide.')
        if params.get('error'):raise ValueError('Autorización cancelada o denegada por el proveedor.')
        code=params.get('code',[''])[0]
        if not code or len(code)>4096:raise ValueError('Código OAuth no válido.')
        token=ok_json(f['metadata']['token_endpoint'],'POST',{'grant_type':'authorization_code','client_id':f['client_id'],'code':code,'redirect_uri':f['redirect'],'code_verifier':f['verifier'],'resource':f['resource']})
        if f['scope']!=self.scope(f['pid']):raise ValueError('Permisos cambiados durante OAuth; no se guardaron credenciales.')
        self.save_token(f,token)
        return {'connected':True,'message':'OAuth conectado. Puedes cerrar esta pestaña y volver a Agentic Studio.'}
    def token(self,pid,sid):
        with self.lock:
            r=self.record(pid,sid)
            if not r:return ''
            if r['expires_at']>time.time()+30:return r['access_token']
            if not r.get('refresh_token'):raise ValueError('OAuth caducado. Pide al usuario volver a conectar.')
            scope=self.scope(pid)
            token=ok_json(r['metadata']['token_endpoint'],'POST',{'grant_type':'refresh_token','client_id':r['client_id'],'refresh_token':r['refresh_token'],'resource':r['resource']})
            if scope!=self.scope(pid):raise ValueError('Permisos cambiados durante la renovación OAuth.')
            return self.save_token({**r,'pid':pid,'sid':sid},token,r)['access_token']
