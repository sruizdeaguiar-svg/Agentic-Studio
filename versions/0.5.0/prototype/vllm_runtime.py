"""Local vllm-metal 0.31 compatibility copy: honor explicit KV byte limits.

The installed Homebrew runtime is unchanged. Its adaptive commit probe is useful
for automatic pools, but must not replace an explicit, context-sized allocation
with a pool inferred from momentary free RAM during model loading/compression.
"""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import sys


def prepare(destination):
    if importlib.metadata.version('vllm-metal') != '0.31.0':
        raise RuntimeError('Este adaptador requiere vllm-metal 0.31.0; revisa la compatibilidad antes de actualizar.')
    source = Path(importlib.util.find_spec('vllm_metal').origin).parent
    original = source / 'v1/cache_policy.py'
    source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    root = Path(destination).resolve()
    manifest = root / 'compatibility.json'
    target = root / 'vllm_metal/v1/cache_policy.py'
    if manifest.exists() and target.exists():
        record = json.loads(manifest.read_text())
        if record['source_sha256'] == source_hash and record['patched_sha256'] == hashlib.sha256(target.read_bytes()).hexdigest():
            return
    text = original.read_text()
    marker = '        kv_offload_pool = self._resolve_kv_offload_pool(base_kv_budget, per_block_bytes)'
    replacement = '''        explicit = self._worker.vllm_config.cache_config.kv_cache_memory_bytes
        if explicit is not None:
            if explicit <= 0 or explicit > base_kv_budget:
                raise ValueError(f"La caché KV explícita ({explicit} bytes) supera el presupuesto Metal disponible ({base_kv_budget} bytes).")
            base_kv_budget = explicit
        kv_offload_pool = self._resolve_kv_offload_pool(base_kv_budget, per_block_bytes)'''
    probe_marker = '        if not envs.VLLM_METAL_KV_COMMIT_PROBE or plan.kv_budget <= 0:'
    probe_replacement = '''        if self._worker.vllm_config.cache_config.kv_cache_memory_bytes is not None:
            logger.info("Panel local: caché KV explícita acotada a %.2f MiB; se conserva durante la recuperación de memoria de macOS", plan.kv_budget / 2**20)
            return plan
        if not envs.VLLM_METAL_KV_COMMIT_PROBE or plan.kv_budget <= 0:'''
    if text.count(marker) != 1 or text.count(probe_marker) != 1:
        raise RuntimeError('El código del backend cambió; no se aplica el adaptador automáticamente.')
    patched = text.replace(marker, replacement).replace(probe_marker, probe_replacement)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, root / 'vllm_metal', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('._*', '__pycache__', '*.pyc'))
    target.write_text(patched)
    manifest.write_text(json.dumps(dict(backend='vllm-metal', version='0.31.0', source=str(source),
         source_sha256=source_hash, patched_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
         change='Respect kv_cache_memory_bytes within the Metal budget; adaptive probe retained for automatic pools.'), indent=2) + '\n')
    print('Adaptador local KV preparado:', target, flush=True)


if __name__ == '__main__':
    prepare(sys.argv[1])
