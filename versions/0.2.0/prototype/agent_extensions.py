"""Bounded local MCP stdio client and native browser request broker. No third-party runtime."""
import json
import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

MAX_MESSAGE=2_100_000

def origin(value):
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Origen no válido: usa http(s)://host[:puerto], sin credenciales.')
    if parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Configura un origen, sin ruta ni parámetros.')
    host=parsed.hostname.lower()
    if ':' in host:host='['+host+']'
    port=parsed.port
    return parsed.scheme+'://'+host+(':'+str(port) if port and port!={'http':80,'https':443}[parsed.scheme] else '')

def check_url(url,origins):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or parsed.username or parsed.password:raise ValueError('Solo navegación HTTP(S) sin credenciales en la URL.')
    base=origin(parsed.scheme+'://'+parsed.netloc)
    if base not in origins:raise ValueError('Origen no autorizado para este proyecto: '+base)
    if len(url)>4096:raise ValueError('URL demasiado larga.')
    return url

class MCPClient:
    def __init__(self,spec,root,sandbox,env):
        self.lock=threading.Lock();self.responses=queue.Queue(maxsize=32);self.serial=0;self.last=time.monotonic();self.closed=False;self.root=root;self.tools=[]
        # Arguments never pass through shell interpolation. Environment is deliberately minimal.
        self.proc=subprocess.Popen(sandbox+['exec "$@"','studio-mcp',spec['command']]+spec.get('args',[]),cwd=str(root),env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        threading.Thread(target=self.read,daemon=True).start()
        try:
            result=self.request('initialize',{'protocolVersion':'2025-11-25','capabilities':{'roots':{'listChanged':False}},'clientInfo':{'name':'Agentic Studio','version':'0.2.0'}})
            if result.get('protocolVersion') not in ('2025-11-25','2025-06-18','2025-03-26','2024-11-05'):raise ValueError('Versión MCP no admitida por este cliente stdio.')
            self.send({'jsonrpc':'2.0','method':'notifications/initialized'})
            cursor=None
            for _ in range(4):
                page=self.request('tools/list',{'cursor':cursor} if cursor else {})
                self.tools+=page.get('tools',[])
                if len(self.tools)>128:raise ValueError('Máximo 128 herramientas por servidor.')
                cursor=page.get('nextCursor')
                if not cursor:break
            if cursor:raise ValueError('Catálogo demasiado grande: más de cuatro páginas.')
            if any(not isinstance(t.get('name'),str) or len(t['name'])>128 for t in self.tools):raise ValueError('Catálogo MCP no válido.')
        except BaseException:
            self.close();raise
    def send(self,message):
        data=(json.dumps(message,ensure_ascii=False)+'\n').encode()
        if len(data)>MAX_MESSAGE:raise ValueError('Mensaje MCP demasiado grande.')
        self.proc.stdin.write(data);self.proc.stdin.flush()
    def read(self):
        try:
            while not self.closed:
                line=self.proc.stdout.readline(MAX_MESSAGE+1)
                if not line:break
                if len(line)>MAX_MESSAGE:raise ValueError('Servidor MCP excedió el límite de mensaje.')
                msg=json.loads(line)
                if not isinstance(msg,dict):raise ValueError('Mensaje MCP no válido.')
                self.responses.put(msg,timeout=1)
        except (ValueError,OSError,queue.Full):pass
        finally:
            try:self.responses.put_nowait({'_disconnected':True})
            except queue.Full:pass
    def request(self,method,params):
        with self.lock:
            self.serial+=1;rid=self.serial;self.last=time.monotonic()
            self.send({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
            deadline=time.monotonic()+25
            for _ in range(256):
                try:msg=self.responses.get(timeout=max(.01,deadline-time.monotonic()))
                except queue.Empty:raise ValueError('MCP agotó el tiempo. La acción no se reintenta automáticamente.')
                if msg.get('_disconnected'):raise ValueError('Servidor MCP desconectado. La acción no se reintenta automáticamente.')
                if 'method' in msg and 'id' in msg:
                    if msg['method']=='roots/list':reply={'result':{'roots':[{'uri':Path(self.root).as_uri(),'name':'Proyecto autorizado'}]}}
                    elif msg['method']=='ping':reply={'result':{}}
                    else:reply={'error':{'code':-32601,'message':'Client capability not available'}}
                    self.send({'jsonrpc':'2.0','id':msg['id'],**reply})
                elif msg.get('id')==rid and 'method' not in msg:
                    if 'error' in msg:raise ValueError('Error MCP: '+str(msg['error'].get('message',''))[:1000])
                    result=msg.get('result',{})
                    if not isinstance(result,dict):raise ValueError('Resultado MCP no válido.')
                    self.last=time.monotonic();return result
                if time.monotonic()>deadline:break
            raise ValueError('Límite de mensajes MCP alcanzado.')
    def call(self,name,arguments):
        if name not in [t['name'] for t in self.tools]:raise ValueError('Herramienta no anunciada por este servidor.')
        try:return self.request('tools/call',{'name':name,'arguments':arguments})
        except (ValueError,OSError):
            self.close();raise
    def close(self):
        if self.closed:return
        self.closed=True
        try:os.killpg(self.proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:pass
        for stream in (self.proc.stdin,self.proc.stdout):
            try:stream.close()
            except OSError:pass

class BrowserBroker:
    def __init__(self):
        self.lock=threading.RLock();self.queue=queue.Queue(maxsize=1);self.pending={};self.last_native=None;self.active_project='';self.active_scope='';self.last_use=0
    def available(self):return self.last_native is not None and time.monotonic()-self.last_native<25
    def request(self,project,scope,operation,args,origins):
        if not self.available():raise ValueError('Navegador nativo no disponible. Abre la aplicación macOS; no se ejecutó la acción.')
        import uuid
        rid=str(uuid.uuid4());event=threading.Event();slot={'event':event,'result':None}
        with self.lock:
            if self.pending:raise ValueError('Ya hay una acción del navegador en curso.')
            self.pending[rid]=slot
            self.active_project=project;self.active_scope=scope;self.last_use=time.monotonic()
            self.queue.put_nowait({'id':rid,'project':project,'scope':scope,'operation':operation,'args':args,'origins':origins,'deadline':time.time()+30})
        try:
            if not event.wait(32):raise ValueError('Navegador sin respuesta. No se reintenta la acción automáticamente.')
            result=slot['result']
            if result.get('error'):raise ValueError(result['error'])
            return result
        finally:
            with self.lock:self.pending.pop(rid,None)
    def poll(self):
        self.last_native=time.monotonic()
        try:
            job=self.queue.get(timeout=8)
            with self.lock:
                if job['id'] in self.pending and job['deadline']>time.time():return job
        except queue.Empty:pass
        return {}
    def complete(self,rid,result):
        with self.lock:
            slot=self.pending.get(rid)
            if slot:slot['result']=result;slot['event'].set()
    def invalidate(self):
        with self.lock:
            for slot in self.pending.values():slot['result']={'error':'Permisos o carpeta cambiados. Acción cancelada.'};slot['event'].set()
            self.active_project='';self.active_scope=''
