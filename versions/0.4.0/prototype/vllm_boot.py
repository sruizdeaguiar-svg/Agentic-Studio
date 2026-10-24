"""Start the actual installed vLLM CLI with a bounded local Metal KV budget."""
import sys
from pathlib import Path
def boot():
    import mlx.core as mx
    source=Path(sys.argv[2])
    kv=int(sys.argv[sys.argv.index('--kv-cache-memory-bytes')+1])
    weights=sum(p.stat().st_size for p in source.glob('*.safetensors') if not p.name.startswith('.'))
    limit=mx.device_info()['max_recommended_working_set_size']
    budget=weights+kv+int(1.5*1024**3)
    fraction=min(.90,max(.05,budget/limit))
    sys.argv.extend(['--gpu-memory-utilization',str(fraction)])
    from vllm.entrypoints.cli.main import main
    main()

if __name__=='__main__':
    boot()
