"""Public Hugging Face discovery and bounded, resumable model downloads. No weights in RAM."""
import hashlib,json,os,re,shutil,threading,time,urllib.request
from pathlib import Path
from urllib.parse import urlencode,quote,urlsplit
from remote_mcp import ok_json,request
ROOT=Path(os.environ.get('AGENTIC_STUDIO_MODEL_DOWNLOAD_ROOT',str(Path.home()/'Models')))
class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        p=urlsplit(newurl)
        if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('La descarga requiere HTTPS sin credenciales en URL.')
        # Public Hub/CDN downloads only: never forward OAuth, cookies or local session headers.
        return urllib.request.Request(newurl,headers={'User-Agent':'AgenticStudio/0.4',**({'Range':req.get_header('Range')} if req.has_header('Range') else {})})
DOWNLOAD_HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}),HTTPSRedirect())
def repo_id(repo):
    if not isinstance(repo,str) or not re.fullmatch(r'[\w.-]{1,96}/[\w.-]{1,96}',repo,flags=re.ASCII) or '..' in repo:raise ValueError('Repositorio no válido: usa propietario/modelo.')
    return repo

def search(query='',kind='',sort='lastModified'):
    if kind not in ('','gguf','mlx') or sort not in ('lastModified','createdAt','downloads','likes'):raise ValueError('Filtro de modelos no válido.')
    if not isinstance(query,str) or len(query)>200:raise ValueError('Búsqueda demasiado larga.')
    params={'limit':12,'sort':sort,'direction':-1,'search':query}
    if kind:params['filter']=kind
    status,_,items=request('https://huggingface.co/api/models?'+urlencode(params))
    if status!=200 or not isinstance(items,list):raise ValueError('No se pudo consultar Hugging Face.')
    return {'models':[{'id':x['id'],'modified':x.get('lastModified',''),'downloads':x.get('downloads',0),'likes':x.get('likes',0),'gated':x.get('gated',False)} for x in items[:12] if isinstance(x,dict) and isinstance(x.get('id'),str)],'sort':sort,'query':query,'root':str(ROOT)}
def files(repo):
    repo=repo_id(repo);status,_,data=request('https://huggingface.co/api/models/'+quote(repo,safe='/')+'?blobs=true')
    if status!=200 or not isinstance(data,dict):raise ValueError('No se puede acceder al repositorio público (HTTP '+str(status)+'). Comprueba su nombre y restricciones.')
    if data.get('private') or data.get('gated'):raise ValueError('Esta descarga admite solo repositorios públicos sin aceptación adicional. Completa los requisitos del proveedor para un repositorio restringido.')
    commit=data.get('sha','')
    if not re.fullmatch('[0-9a-f]{40,64}',commit):raise ValueError('Revisión de modelo no válida.')
    items=[]
    for f in data.get('siblings',[]):
        name=f.get('rfilename','');parts=Path(name).parts
        if not name or name.startswith('/') or any(x in ('.','..') or x.startswith('.') for x in parts):continue
        kind='gguf' if name.lower().endswith('.gguf') else 'weights' if name.endswith('.safetensors') else 'config' if name.endswith(('.json','.model','.tiktoken','.txt')) else ''
        if not kind:continue
        lfs=f.get('lfs') or {};size=lfs.get('size',f.get('size',0))
        if not isinstance(size,int) or size<0:continue
        items.append({'name':name,'size':size,'kind':kind,'sha256':lfs.get('sha256',''),'blob':f.get('blobId','')})
    if len(items)>1024:raise ValueError('Repositorio demasiado grande; máximo 1024 archivos candidatos.')
    return {'repo':repo,'commit':commit,'files':items,'root':str(ROOT)}

class Downloads:
    def __init__(self,root=ROOT):self.root=Path(root);self.lock=threading.RLock();self.cancelled=threading.Event();self.thread=None;self.state={'status':'idle'}
    def status(self):
        with self.lock:return dict(self.state)
    def cancel(self):self.cancelled.set();return self.status()
    def start(self,repo,names,approved=False):
        if approved is not True:raise ValueError('Revisa tamaño y archivos antes de descargar.')
        if not isinstance(names,list) or not names or len(names)>1024 or any(not isinstance(n,str) for n in names):raise ValueError('Selecciona archivos del modelo.')
        with self.lock:
            if self.state.get('status')=='preparing' or (self.thread and self.thread.is_alive()):raise ValueError('Ya hay una descarga activa; cancélala o espera.')
            self.state={'status':'preparing'}
        try:
            meta=files(repo);selected=[f for f in meta['files'] if f['name'] in names]
            if len(selected)!=len(set(names)):raise ValueError('Hay archivos fuera de la revisión del repositorio.')
            if self.root.is_symlink():raise ValueError('La carpeta de modelos no puede ser un enlace simbólico.')
            self.root.mkdir(parents=True,exist_ok=True);root=self.root.resolve();destination=root/(repo.replace('/','--'))
            if destination.is_symlink():raise ValueError('La carpeta destino es un enlace simbólico.')
            destination.mkdir(exist_ok=True)
            total=sum(f['size'] for f in selected)
            remaining=0
            for f in selected:
                target=self.safe(destination,f['name']);part=self.safe(destination,f['name']+'.part')
                remaining+=0 if target.exists() else max(0,f['size']-(part.stat().st_size if part.exists() else 0))
            if shutil.disk_usage(root).free<remaining+100*1024*1024:raise ValueError('Espacio insuficiente para la selección y margen de 100 MiB.')
            self.cancelled.clear()
            with self.lock:self.state={'status':'downloading','repo':repo,'commit':meta['commit'],'destination':str(destination),'total':total,'done':0,'file':'','started':time.time(),'files_done':0}
            self.thread=threading.Thread(target=self.run,args=(meta,selected,destination),daemon=True);self.thread.start();return self.status()
        except BaseException:
            with self.lock:self.state={'status':'failed','error':'No se pudo preparar la descarga.'}
            raise
    def safe(self,destination,name):
        target=destination/name
        for component in [target,*target.parents]:
            if component==destination.parent:break
            if component.is_symlink():raise ValueError('Descarga rechazada: enlace simbólico en el destino.')
        target.resolve().relative_to(destination.resolve())
        target.parent.mkdir(parents=True,exist_ok=True);return target
    def verify(self,path,item):
        size=path.stat().st_size
        if size!=item['size']:return False
        sha=hashlib.sha256();git=hashlib.sha1();git.update(('blob '+str(size)+'\0').encode())
        with path.open('rb') as stream:
            while True:
                if self.cancelled.is_set():raise InterruptedError()
                chunk=stream.read(131072)
                if not chunk:break
                sha.update(chunk);git.update(chunk)
        if item['sha256']:return sha.hexdigest()==item['sha256']
        if re.fullmatch('[0-9a-f]{40}',item['blob']):return git.hexdigest()==item['blob']
        raise ValueError('El Hub no proporciona un hash verificable para '+item['name'])
    def run(self,meta,selected,destination):
        try:
            for item in selected:
                if self.cancelled.is_set():raise InterruptedError()
                target=self.safe(destination,item['name']);part=self.safe(destination,item['name']+'.part')
                with self.lock:self.state['file']=item['name']
                if target.exists():
                    if not self.verify(target,item):raise ValueError('Ya existe un archivo diferente; no se sobrescribe: '+item['name'])
                    with self.lock:self.state['done']+=item['size'];self.state['files_done']+=1
                    continue
                note=self.safe(destination,item['name']+'.part.json')
                identity={'repo':meta['repo'],'commit':meta['commit'],'name':item['name'],'size':item['size'],'sha256':item['sha256'],'blob':item['blob']}
                if part.exists() and part.stat().st_size and (not note.exists() or json.loads(note.read_text())!=identity):raise ValueError('El parcial corresponde a otra revisión o no tiene metadatos. Revísalo antes de iniciar una descarga nueva.')
                note.write_text(json.dumps(identity))
                offset=part.stat().st_size if part.exists() else 0
                if offset>item['size']:raise ValueError('El archivo parcial supera el tamaño esperado; revísalo antes de continuar.')
                if offset<item['size']:
                    url='https://huggingface.co/'+quote(meta['repo'],safe='/')+'/resolve/'+meta['commit']+'/'+quote(item['name'],safe='/')
                    headers={'User-Agent':'AgenticStudio/0.4'}
                    if offset:headers['Range']='bytes='+str(offset)+'-'
                    with DOWNLOAD_HTTP.open(urllib.request.Request(url,headers=headers),timeout=20) as response:
                        if offset and response.status==206:
                            if not response.headers.get('Content-Range','').startswith('bytes '+str(offset)+'-'):raise ValueError('Rango de reanudación no válido.')
                        elif response.status==200:offset=0
                        else:raise ValueError('Respuesta de descarga inesperada.')
                        mode=os.O_WRONLY|os.O_CREAT|getattr(os,'O_NOFOLLOW',0)|(os.O_APPEND if offset else os.O_TRUNC)
                        with os.fdopen(os.open(str(part),mode,0o600),'ab' if offset else 'wb') as stream:
                            with self.lock:self.state['done']+=offset
                            count=offset
                            while True:
                                if self.cancelled.is_set():raise InterruptedError()
                                chunk=response.read(131072)
                                if not chunk:break
                                count+=len(chunk)
                                if count>item['size']:raise ValueError('El servidor excedió el tamaño anunciado.')
                                stream.write(chunk)
                                with self.lock:self.state['done']+=len(chunk)
                else:
                    with self.lock:self.state['done']+=offset
                if not self.verify(part,item):raise ValueError('Hash o tamaño incorrecto. Archivo parcial conservado para revisión.')
                if target.exists():raise ValueError('El destino apareció durante la descarga; no se sobrescribe.')
                part.rename(target)
                note.unlink()
                with self.lock:self.state['files_done']+=1
            with self.lock:self.state.update(status='completed',finished=time.time())
        except InterruptedError:
            with self.lock:self.state.update(status='cancelled',finished=time.time())
        except (OSError,ValueError) as e:
            with self.lock:self.state.update(status='failed',error=str(e)[:500],finished=time.time())
