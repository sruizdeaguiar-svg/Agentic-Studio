"""Explicit memory admission override: tiny fictitious files, never large allocations."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
s=core.studio

class MemoryOverrideTests(unittest.TestCase):
    def test_default_and_strict_boolean(self):
        self.assertFalse(s.memory_override({}));self.assertTrue(s.memory_override({'ignore_memory_admission':True}))
        for value in ('true','false',1,None):
            with self.assertRaises(ValueError):s.memory_override({'ignore_memory_admission':value})

    def test_llama_rejects_insufficient_memory_unless_opted_in(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);binary=root/'llama-server';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755);model=root/'tiny.gguf';model.write_bytes(b'GGUFfixture')
            budget={'moe':True,'required_bytes':64*1024**3,'weights_bytes':10,'architecture':'fixture','experts':64,'active_experts':6}
            body={'engine':'llama','binary':str(binary),'model':str(model),'context':4096,'confirm_load':True}
            with patch.object(s,'stop_engine'),patch.object(s.BROWSER,'available',return_value=False),patch.object(s,'provider',return_value={'url':'http://127.0.0.1:8792/v1'}),patch.object(s.subprocess,'check_output',return_value=b'--api-key'),patch.object(s.runtimes,'estimate_gguf_memory',return_value=budget),patch.object(s,'resources',return_value={'available_mb':0,'memory_pressure':'critical'}),patch.object(s.socket,'socket'),patch.object(s,'set_setting') as save,patch.object(s,'audit'),patch.object(s,'ENGINE',None),patch.object(s,'ENGINE_META',{}),patch.object(s,'ENGINE_KEY',None),patch.object(s.subprocess,'Popen') as launch:
                with self.assertRaisesRegex(ValueError,'presupuesto conservador'):s.start_engine(body)
                launch.assert_not_called()
                try:
                    s.start_engine({**body,'ignore_memory_admission':True})
                    launch.assert_called_once()
                    profile=next(call.args[1] for call in save.call_args_list if call.args[0]=='engine_config')
                    self.assertTrue(profile['ignore_memory_admission']);self.assertEqual(profile['context'],4096)
                    with self.assertRaisesRegex(ValueError,'Contexto'):s.start_engine({**body,'ignore_memory_admission':True,'context':999999})
                finally:
                    if s.ENGINE_LOG:s.ENGINE_LOG.close();s.ENGINE_LOG=None

    def test_omlx_override_disables_guard_without_conflicting_ceiling(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model';model.mkdir();(model/'config.json').write_text('{}');(model/'weights.safetensors').write_bytes(b'fixture');data=root/'data';data.mkdir()
            with patch.object(s.runtimes,'runtime_inventory',return_value={'omlx':{'installed':True}}),patch.object(s.runtimes.tempfile,'mkdtemp',return_value=str(root/'view')):
                args,env,meta=s.runtimes.launch_spec('omlx',str(model),4096,'f16',8792,'fictitious',data,1,ignore_memory_admission=True)
            self.assertIn('--memory-guard',args);self.assertEqual(args[args.index('--memory-guard')+1],'off');self.assertNotIn('--memory-guard-gb',args)
            settings=json.loads((data/'omlx/settings.json').read_text());self.assertFalse(settings['memory']['prefill_memory_guard']);self.assertIsNone(meta['memory_ceiling_gb'])
            self.assertEqual(args[args.index('--max-concurrent-requests')+1],'1')

    def test_vllm_override_skips_budget_but_preserves_context_sized_kv(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model';model.mkdir();(model/'config.json').write_text('{}');(model/'weights.safetensors').write_bytes(b'fixture');data=root/'data';data.mkdir()
            with patch.object(s.runtimes,'runtime_inventory',return_value={'vllm':{'installed':True}}),patch.object(s.runtimes.tempfile,'mkdtemp',side_effect=[str(root/'view1'),str(root/'view2')]),patch.object(s.runtimes.subprocess,'run',return_value=MagicMock(returncode=0)):
                with self.assertRaisesRegex(ValueError,'superan el límite'):s.runtimes.launch_spec('vllm',str(model),4096,'f16',8792,'fictitious',data,1)
                args,env,meta=s.runtimes.launch_spec('vllm',str(model),4096,'f16',8792,'fictitious',data,1,ignore_memory_admission=True)
            self.assertEqual(args[args.index('--max-model-len')+1],'4096');self.assertEqual(args[args.index('--max-num-seqs')+1],'1');self.assertIn('--kv-cache-memory-bytes',args);self.assertTrue(meta['ignore_memory_admission'])

class MemoryOverrideProfileTests(core.StudioTests):
    def test_explicit_model_profile_persists_and_rejects_string_flags(self):
        with tempfile.NamedTemporaryFile(suffix='.gguf') as model:
            body={'engine':'llama','model':model.name,'kv':'q8_0','ignore_memory_admission':True}
            self.request('/api/engine/profile',body)
            profile=s.setting('engine_profile:llama:'+str(Path(model.name).resolve()));self.assertTrue(profile['ignore_memory_admission'])
            import urllib.error
            with self.assertRaises(urllib.error.HTTPError):self.request('/api/engine/profile',{**body,'ignore_memory_admission':'false'})
for name in dir(core.StudioTests):
    if name.startswith('test_') and name not in MemoryOverrideProfileTests.__dict__:setattr(MemoryOverrideProfileTests,name,None)
