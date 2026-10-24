"""Local runtime catalog and isolated launch preparation. Never loads weights."""
import hashlib
import json
import os
from pathlib import Path
import struct
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
def executable(path):
    try:return Path(path).is_file() and os.access(path,os.X_OK)
    except OSError:return False

def find_executable(candidates):
    return next((Path(p) for p in candidates if p and executable(p)),None)

def resolve_runtime_paths():
    vllm=find_executable([os.environ.get('AGENTIC_VLLM_PYTHON',''),
        '/opt/homebrew/opt/vllm-metal/libexec/bin/python3',
        '/usr/local/opt/vllm-metal/libexec/bin/python3',
        '/opt/homebrew/opt/vllm-metal/libexec/bin/python3.12'])
    configured=os.environ.get('AGENTIC_OMLX_ROOT','')
    roots=[Path(configured)] if configured else [Path('/Applications/oMLX.app/Contents/Resources'),Path.home()/'Applications/oMLX.app/Contents/Resources']
    root=next((p for p in roots if executable(p.parent/'MacOS/omlx-cli')),roots[0])
    return vllm or Path('/nonexistent/agentic/vllm-python'),root

VLLM_PYTHON,OMLX_ROOT=resolve_runtime_paths()
OMLX_PYTHON=OMLX_ROOT/'Python/cpython-3.11/bin/python3'
OMLX_CLI=OMLX_ROOT.parent/'MacOS/omlx-cli'
PROBE_CACHE={}

def runtime_environment(engine):
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    if engine=='omlx':
        env['PYTHONHOME']=str(OMLX_ROOT/'Python/cpython-3.11')
        env['PYTHONPATH']=str(OMLX_ROOT)+':'+str(OMLX_ROOT/'Python/framework-mlx-base/lib/python3.11/site-packages')
    return env

def llama_binary():
    configured=os.environ.get('AGENTIC_LLAMA_SERVER','')
    candidates=[configured,shutil.which('llama-server') or '', '/opt/homebrew/bin/llama-server','/usr/local/bin/llama-server']
    for p in candidates:
        if p and executable(p):return p
    return ''

def runtime_inventory():
    return {'llama':{'installed':bool(llama_binary()),'binary':llama_binary(),'format':'GGUF'}, 'vllm':{'installed':executable(VLLM_PYTHON),'python':str(VLLM_PYTHON),'format':'Safetensors / MLX · registro vLLM Metal'}, 'omlx':{'installed':executable(OMLX_CLI) and executable(OMLX_PYTHON),'binary':str(OMLX_CLI),'format':'Safetensors / MLX · registro MLX-LM'}}

def qualify(models,engine):
    paths=[m['path'] for m in models if m['format']!='GGUF']
    if not paths:return {}
    runtime=runtime_inventory()[engine]
    if not runtime['installed']:return {p:{'ok':False,'reason':'Motor no instalado.'} for p in paths}
    python=VLLM_PYTHON if engine=='vllm' else OMLX_PYTHON
    identity=tuple((p,(Path(p)/'config.json').stat().st_mtime_ns) for p in paths)
    key=(engine,identity,str(python.resolve()))
    if key in PROBE_CACHE:return PROBE_CACHE[key]
    env=runtime_environment(engine)
    env.update(HF_HOME='/private/tmp/agentic-studio-probe/hf',VLLM_CACHE_ROOT='/private/tmp/agentic-studio-probe/vllm',XDG_CACHE_HOME='/private/tmp/agentic-studio-probe/cache')
    run=subprocess.run([str(python),str(ROOT/'runtime_probe.py'),engine],input=json.dumps(paths),text=True,capture_output=True,timeout=90,env=env)
    line=next((line for line in run.stdout.splitlines() if line.startswith('STUDIO_MODELS=')),None)
    if not line:raise ValueError('No se pudo comprobar el registro de '+engine+': '+run.stderr[-450:])
    result=json.loads(line.split('=',1)[1])
    if len(PROBE_CACHE)>8:PROBE_CACHE.clear()
    PROBE_CACHE[key]=result
    return result

def gguf_metadata(path):
    result={}
    try:
        with Path(path).open('rb') as f:
            def number(fmt):
                size=struct.calcsize(fmt);data=f.read(size)
                if len(data)!=size:raise ValueError('Cabecera truncada.')
                return struct.unpack(fmt,data)[0]
            def string(keep=True):
                size=number('<Q')
                if size>16_000_000:raise ValueError('Metadato desmesurado.')
                if keep and size<8192:return f.read(size).decode('utf-8','replace')
                f.seek(size,1);return ''
            sizes={0:'<B',1:'<b',2:'<H',3:'<h',4:'<I',5:'<i',6:'<f',7:'<?',10:'<Q',11:'<q',12:'<d'}
            def value(t,keep=True):
                if t==8:return string(keep)
                if t==9:
                    subtype=number('<I');count=number('<Q')
                    if count>1000000:raise ValueError('Metadato desmesurado.')
                    if subtype in sizes:f.seek(struct.calcsize(sizes[subtype])*count,1)
                    else:
                        for _ in range(count):value(subtype,False)
                    return None
                if t not in sizes:raise ValueError('Tipo de metadato desconocido.')
                return number(sizes[t])
            if f.read(4)!=b'GGUF':return result
            if number('<I') not in (2,3):return result
            number('<Q');count=number('<Q')
            for _ in range(min(count,300)):
                key=string()
                if key.startswith('tokenizer.'):break
                kind=number('<I');v=value(kind)
                if v is not None:result[key]=v
    except (OSError,ValueError,struct.error):pass
    return result

def estimate_gguf_memory(path,context,kv='f16'):
    meta=gguf_metadata(path);arch=meta.get('general.architecture','');layers=int(meta.get(arch+'.block_count',32));heads=int(meta.get(arch+'.attention.head_count',8));kv_heads=int(meta.get(arch+'.attention.head_count_kv',heads));dim=int(meta.get(arch+'.embedding_length',4096))//max(1,heads)
    key_dim=int(meta.get(arch+'.attention.key_length',dim));value_dim=int(meta.get(arch+'.attention.value_length',dim))
    precision={'f16':2,'q8_0':1.0625,'q4_0':.5625}.get(kv,2)
    # Budget a full non-compressed attention layout, even for MLA/sliding models.
    cache=int(context*layers*kv_heads*(key_dim+value_dim)*precision)
    weights=Path(path).stat().st_size;reserve=1024**3
    return {'weights_bytes':weights,'kv_estimate_bytes':cache,'reserve_bytes':reserve,'required_bytes':weights+cache+reserve,'moe':bool(meta.get(arch+'.expert_count')),'experts':meta.get(arch+'.expert_count'),'active_experts':meta.get(arch+'.expert_used_count'),'architecture':arch,'conservative':True}

def annotate_gguf(item):
    meta=gguf_metadata(item['path']);arch=meta.get('general.architecture','')
    name=Path(item['path']).name.lower()
    standalone=not (name.startswith(('mmproj','ggml-vocab')) or 'dflash' in name or 'draft' in name or arch in ('clip','siglip','vision') or meta.get('general.type') in ('mmproj','adapter') or meta.get('split.no',0)>0)
    item.update(architecture=arch,native_context=meta.get(arch+'.context_length'),role='model' if standalone else 'auxiliary',compatible_llama=standalone)
    count=meta.get(arch+'.expert_count')
    if count:
        item['moe']={'experts':count,'active':meta.get(arch+'.expert_used_count'),'weights_bytes':item['bytes']}
    return item

def moe_info(config,size):
    cfg=config.get('text_config') or config
    experts=cfg.get('num_experts') or cfg.get('num_local_experts') or cfg.get('n_routed_experts')
    if not experts:return None
    return {'experts':experts,'active':cfg.get('num_experts_per_tok') or cfg.get('num_experts_per_token') or cfg.get('top_k_experts') or cfg.get('n_activated_experts'),'weights_bytes':size,'layer_types':sorted(set(cfg.get('layer_types') or ['full_attention']))}

def clean_view(source, root):
    """Fresh APFS metadata view with links to weights. No checkpoint duplication."""
    source=Path(source).resolve();root=Path(root);root.mkdir(parents=True,exist_ok=True)
    destination=root/'checkpoint';destination.mkdir()
    for p in source.rglob('*'):
        rel=p.relative_to(source)
        if any(part.startswith('.') for part in rel.parts):continue
        if p.is_file():
            target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(p.resolve())
    return destination

def estimate_kv(config,context):
    cfg=config.get('text_config') or config
    layers=int(cfg.get('num_hidden_layers') or 32)
    types=cfg.get('layer_types')
    types=list(types) if types else ['full_attention']*layers
    heads=int(cfg.get('num_key_value_heads') or cfg.get('num_attention_heads') or 8)
    dim=int(cfg.get('head_dim') or int(cfg.get('hidden_size',4096))//int(cfg.get('num_attention_heads') or 32))
    global_heads=int(cfg.get('num_global_key_value_heads') or heads)
    global_dim=int(cfg.get('global_head_dim') or dim)
    linear=sum(t in ('linear_attention','mamba','gated_delta_net') for t in types)
    recurrent=linear*int(cfg.get('linear_num_value_heads',0))*int(cfg.get('linear_key_head_dim',128))*int(cfg.get('linear_value_head_dim',128))*8
    sliding=int(cfg.get('sliding_window') or context)
    kv=0
    for layer in types:
        if layer in ('linear_attention','mamba','gated_delta_net'):continue
        if layer=='sliding_attention':kv+=min(context,sliding)*heads*dim*4
        else:kv+=context*global_heads*global_dim*4
    return int(kv+recurrent+128*1024**2)

def launch_spec(engine,model,context,kv,port,key,data,memory_gb,batch=256,prefill_priority='context',moe_offload=False,moe_fraction=.25):
    if not 64<=batch<=8192 or prefill_priority not in ('context','speed'):
        raise ValueError('Prefill batch o prioridad fuera de rango.')
    if engine=='vllm' and kv!='f16':raise ValueError('vLLM Metal usa KV nativa en este perfil.')
    if engine=='omlx' and kv not in ('f16','tq8','tq6','tq4'):raise ValueError('Perfil KV de oMLX no válido.')
    if not 0<moe_fraction<=1:raise ValueError('Fracción residente MoE entre 0 y 1.')
    inventory=runtime_inventory()[engine]
    if not inventory['installed']:raise ValueError('Motor no instalado: '+engine)
    folder=Path(tempfile.mkdtemp(prefix='agentic-studio-'+engine+'-',dir='/private/tmp'))
    view=clean_view(model,folder)
    config=json.loads((view/'config.json').read_text())
    size=sum(p.stat().st_size for p in view.glob('*.safetensors'))
    env=runtime_environment(engine)
    env.update(HF_HOME=str(data/'hf-cache'),VLLM_CACHE_ROOT=str(data/'vllm-cache'),VLLM_API_KEY=key,OMLX_API_KEY=key,OMLX_BASE_PATH=str(data/'omlx'))
    if engine=='vllm':
        if size+estimate_kv(config,context)+int(1.5*1024**3)>memory_gb*1024**3:
            raise ValueError('Pesos, KV estimada y reserva vLLM superan el límite de memoria elegido.')
        # Preserve the installed runtime. A version-checked local compatibility
        # copy honors an explicit, context-sized KV budget on this Metal build.
        adapter=ROOT/'vllm_runtime.py'
        if not adapter.is_file():raise ValueError('Falta el adaptador local verificado de vLLM Metal.')
        prepared=folder/'runtime'
        run=subprocess.run([str(VLLM_PYTHON),str(adapter),str(prepared)],env=env,text=True,capture_output=True,timeout=30)
        if run.returncode:raise ValueError('Adaptador vLLM: '+run.stderr[-500:])
        env['PYTHONPATH']=str(prepared)
        args=[str(VLLM_PYTHON),str(ROOT/'vllm_boot.py'),'serve',str(view),'--host','127.0.0.1','--port',str(port),'--served-model-name','studio-local','--max-model-len',str(context),'--max-num-seqs','1','--max-num-batched-tokens',str(batch),'--kv-cache-memory-bytes',str(estimate_kv(config,context)),'--language-model-only','--generation-config','vllm','--no-enable-prefix-caching','--enable-auto-tool-choice','--tool-call-parser','hermes']
        if kv!='f16':
            raise ValueError('vLLM Metal utiliza KV nativa; selecciona F16 / nativa. No admite los tipos Q8/Q4 de llama.cpp.')
    else:
        base=data/'omlx';base.mkdir(exist_ok=True)
        models=folder/'models';models.mkdir();(models/'studio-local').symlink_to(view,target_is_directory=True)
        (base/'settings.json').write_text(json.dumps({'server':{'host':'127.0.0.1','port':port},'scheduler':{'max_concurrent_requests':1,'embedding_batch_size':1,'prefill_priority':prefill_priority,'chunked_prefill':True},'sampling':{'max_context_window':context,'max_context_window_policy':context,'max_tokens':2048},'cache':{'enabled':False,'hot_cache_max_size':'0'},'memory':{'prefill_memory_guard':True,'memory_guard_tier':'safe'}}))
        model_settings={'max_context_window':context,'max_tokens':2048,'model_alias':'studio-local','enable_thinking':False}
        # oMLX TurboQuant is not llama.cpp Q8/Q4; do not silently equate them.
        if kv.startswith('tq'):
            model_settings.update(turboquant_kv_enabled=True,turboquant_kv_bits=float(kv[2:]))
        if moe_offload:
            model_settings.update(moe_expert_offload_enabled=True,moe_expert_offload_resident_fraction=moe_fraction)
        (base/'model_settings.json').write_text(json.dumps({'version':1,'models':{'studio-local':model_settings}}))
        args=[str(OMLX_CLI),'serve','--base-path',str(base),'--model-dir',str(models),'--host','127.0.0.1','--port',str(port),'--max-concurrent-requests','1','--embedding-batch-size','1','--no-cache','--no-hf-cache','--hot-cache-max-size','0','--initial-cache-blocks','4','--memory-guard-gb',str(memory_gb),'--log-level','warning']
    return args,env,{'engine':engine,'model':str(model),'context':context,'kv':'native' if kv=='f16' else kv,'bytes':size,'ready':False,'runtime_view':str(folder),'memory_ceiling_gb':memory_gb}
