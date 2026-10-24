"""Inspect installed text-model registries without loading model weights."""
import json
from pathlib import Path
import sys

engine=sys.argv[1]
from mlx_lm.utils import _get_classes
if engine=='vllm':
    from vllm.model_executor.models import ModelRegistry
    supported=ModelRegistry.get_supported_archs()
results={}
for name in json.load(sys.stdin):
    try:
        root=Path(name)
        cfg=json.loads((root/'config.json').read_text())
        _get_classes(cfg)
        arch=cfg.get('architectures') or []
        if not any('CausalLM' in a or 'ConditionalGeneration' in a for a in arch):
            raise ValueError('No es un modelo generativo de texto compatible con este panel.')
        if engine=='vllm' and not any(a in supported for a in arch):
            raise ValueError('Arquitectura no registrada en el vLLM instalado.')
        if not (root/'tokenizer_config.json').is_file() or not (root/'tokenizer.json').is_file():
            raise ValueError('Tokenizer local incompleto.')
        shards=list(root.glob('*.safetensors'))
        if not shards:raise ValueError('No hay pesos safetensors locales.')
        index=root/'model.safetensors.index.json'
        if index.is_file():
            for shard in set(json.loads(index.read_text())['weight_map'].values()):
                if Path(shard).is_absolute() or '..' in Path(shard).parts or not (root/shard).is_file():raise ValueError('Faltan fragmentos del checkpoint.')
        results[name]={'ok':True,'reason':'Registro de arquitectura y archivos locales comprobados; carga pendiente de verificar.'}
        if engine=='omlx':
            try:
                from omlx.patches.moe_offload_compat import moe_offload_compatibility
                ok,reason=moe_offload_compatibility(root)
                results[name].update(moe_offload_supported=ok,moe_offload_reason=reason)
            except Exception:
                results[name].update(moe_offload_supported=False,moe_offload_reason='No se pudo verificar la descarga de expertos de este checkpoint.')
    except Exception as error:
        results[name]={'ok':False,'reason':str(error)[:240]}
print('STUDIO_MODELS='+json.dumps(results),flush=True)
