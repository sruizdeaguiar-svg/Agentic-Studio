"""Integration tests with an explicitly simulated engine; no private app data."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

temporary = tempfile.TemporaryDirectory(prefix='agentic-studio-tests-')
os.environ['AGENTIC_STUDIO_DATA'] = temporary.name
os.environ['AGENTIC_STUDIO_TOKEN'] = 'isolated-integration-test-token'
spec = importlib.util.spec_from_file_location('studio', Path(__file__).resolve().parents[1] / 'server.py')
studio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio)

class FixtureEngine(BaseHTTPRequestHandler):
    step = 0
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        data = json.dumps({'data': [{'id': 'fixture-model'}]}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.__class__.requests.append(body)
        step = self.__class__.step
        self.__class__.step += 1
        if step == 0:
            delta = {'tool_calls': [{'index': 0, 'id': 'list-1', 'type': 'function', 'function': {'name': 'list_files', 'arguments': '{}'}}]}
        elif step == 1:
            delta = {'tool_calls': [{'index': 0, 'id': 'read-1', 'type': 'function', 'function': {'name': 'read_file', 'arguments': '{"path":"brief.txt"}'}}]}
        elif step == 2:
            delta = {'tool_calls': [{'index': 0, 'id': 'write-1', 'type': 'function', 'function': {'name': 'propose_file', 'arguments': '{"path":"result.txt","content":"Verified fixture 42"}'}}]}
        elif step == 3:
            delta = {'tool_calls': [{'index': 0, 'id': 'command-1', 'type': 'function', 'function': {'name': 'propose_command', 'arguments': '{"command":"cat result.txt"}'}}]}
        else:
            delta = {'content': 'Fixture: archivo aprobado y comando ejecutado.'}
        delta['reasoning_content']='Fixture reasoning explicitly supplied by engine.'
        wire = ('data: ' + json.dumps({'choices': [{'delta': delta}]}) + '\n\ndata: [DONE]\n\n').encode()
        self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.send_header('Content-Length', str(len(wire))); self.end_headers(); self.wfile.write(wire)

class StudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        studio.CANCEL.clear()
        studio.init()
        cls.engine = ThreadingHTTPServer(('127.0.0.1', 0), FixtureEngine)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), studio.Handler)
        cls.server.daemon_threads = True
        for server in [cls.server, cls.engine]:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:%d' % cls.server.server_port
        providers = [p for p in studio.setting('providers') if p['id']!='fixture'] + [{'id':'fixture','name':'Fixture','url':'http://127.0.0.1:%d/v1' % cls.engine.server_port}]
        studio.set_setting('providers', providers)

    @classmethod
    def tearDownClass(cls):
        for server in [cls.server, cls.engine]:
            server.shutdown(); server.server_close()
        studio.stop_engine()
        temporary.cleanup()

    def request(self, path, body=None, token=True, origin=None, stream=False):
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + studio.TOKEN
        if origin: headers['Origin'] = origin
        request = urllib.request.Request(self.base + path, headers=headers, data=None if body is None else json.dumps(body).encode())
        with urllib.request.urlopen(request, timeout=10) as r:
            text = r.read().decode()
            return [json.loads(line) for line in text.splitlines() if line] if stream else json.loads(text)

    def new_project(self):
        pid = self.request('/api/projects', {'name': 'Fictitious QA', 'instructions': ''})['id']
        sid = self.request('/api/sessions', {'project_id': pid})['id']
        return pid, sid

    def test_auth_and_cross_origin(self):
        for kwargs in [{'token':False}, {'origin':'https://evil.example'}]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/api/state', **kwargs)
            self.assertIn(error.exception.code, (401,403))

    def test_files_retrieval_and_path_containment(self):
        pid, sid = self.new_project()
        self.request('/api/file', {'project':pid,'path':'notes/data.txt','content':'The private fixture number is 42.'})
        hits = self.request('/api/search?project='+pid+'&q=fixture')
        self.assertEqual(hits[0]['path'], 'notes/data.txt')
        for bad in ['../escape.txt', '/tmp/escape.txt', 'notes/../../escape']:
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/file', {'project':pid,'path':bad,'content':'no'})
        (studio.project_root(pid)/'linked').symlink_to('/private/tmp')
        with self.assertRaises(ValueError): studio.file_path(pid,'linked/escape.txt')
        self.assertEqual(self.request('/api/file?project='+pid+'&path=notes/data.txt')['content'], 'The private fixture number is 42.')

    def test_complete_agent_permission_resume_loop(self):
        FixtureEngine.step = 0; FixtureEngine.requests = []
        pid, sid = self.new_project()
        self.request('/api/file', {'project':pid,'path':'brief.txt','content':'Fixture number 42'})
        body={'session_id':sid,'message':'Read the brief, write result and verify it.','provider':'fixture','model':'fixture-model','agent':True,'context':16384,'max_tokens':512}
        events=self.request('/api/chat',body,stream=True)
        self.assertEqual(events[-1]['type'],'waiting', events)
        self.assertTrue(any(e['type']=='reasoning' for e in events))
        self.assertFalse((studio.project_root(pid)/'result.txt').exists())
        actions=self.request('/api/proposals?session='+sid)
        p=actions['files'][0]
        self.request('/api/proposal/resolve',{'id':p['id'],'approve':True})
        self.assertEqual((studio.project_root(pid)/'result.txt').read_text(),'Verified fixture 42')
        events=self.request('/api/chat',{'session_id':sid,'resume':True},stream=True)
        self.assertEqual(events[-1]['type'],'waiting', events)
        commands=self.request('/api/proposals?session='+sid)['commands']
        self.assertEqual(commands[0]['status'],'pending')
        result=self.request('/api/command/resolve',{'id':commands[0]['id'],'approve':True})
        self.assertEqual(result['output'],'Verified fixture 42')
        events=self.request('/api/chat',{'session_id':sid,'resume':True},stream=True)
        self.assertEqual(events[-1]['type'],'done')
        self.assertIn('Fixture:',self.request('/api/messages?session='+sid)[-1]['content'])
        final=FixtureEngine.requests[-1]['messages']
        self.assertTrue(any('executed' in m.get('content','') for m in final if m['role']=='tool'))

    def test_conflicting_proposal_and_rejection(self):
        pid,sid=self.new_project();s={'id':sid,'project_id':pid}
        studio.write_file(pid,'a.txt','before')
        p=studio.tool_call(s,'propose_file',{'path':'a.txt','content':'after'})
        studio.write_file(pid,'a.txt','concurrent')
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/proposal/resolve',{'id':p['proposal_id'],'approve':True})
        self.assertEqual(studio.read_file(pid,'a.txt'),'concurrent')
        self.request('/api/proposal/resolve',{'id':p['proposal_id'],'approve':False})
        c=studio.tool_call(s,'propose_command',{'command':'touch should-not-exist'})
        self.request('/api/command/resolve',{'id':c['command_id'],'approve':False})
        self.assertFalse((studio.project_root(pid)/'should-not-exist').exists())

    def test_compaction_keeps_current_transaction(self):
        messages=[{'role':'system','content':'System'}, {'role':'user','content':'old '*5000}, {'role':'assistant','content':'answer '*4000}, {'role':'user','content':'current'}, {'role':'assistant','content':None,'tool_calls':[{'id':'call'}]}, {'role':'tool','tool_call_id':'call','content':'evidence'}]
        events=[]
        response=lambda *a,**k:io.BytesIO(json.dumps({'choices':[{'message':{'content':'Summary of facts and pending work.'}}]}).encode())
        with patch.object(studio,'upstream',side_effect=response):
            result=studio.compact_context(messages,{'url':'http://127.0.0.1:1/v1'},'fixture',4096,512,events.append)
        self.assertEqual(result[-3:],messages[-3:])
        self.assertLess(studio.token_estimate(result),4096-512)
        self.assertTrue(events[-1]['compacted'])

    def test_model_preferences_and_gateway(self):
        self.request('/api/preferences',{'provider':'fixture','model':'fixture-model','context':16384,'max_tokens':512,'temperature':.3})
        models=self.request('/v1/models')
        self.assertEqual(models['data'][0]['id'],'fixture-model')
        self.assertEqual(studio.setting('generation:fixture:fixture-model')['context'],16384)
        with self.assertRaises(ValueError):studio.local_url('https://external.example/v1')
        with self.assertRaises(ValueError):studio.local_url('http://127.0.0.1:1234/v1?token=secret')

    def test_compaction_inside_one_agent_task(self):
        messages=[{'role':'system','content':'system'},{'role':'user','content':'Preserve objective'}, {'role':'assistant','content':None,'tool_calls':[{'id':'old','type':'function','function':{'name':'read_file','arguments':'{}'}}]}, {'role':'tool','tool_call_id':'old','content':'evidence '*4000}, {'role':'assistant','content':None,'tool_calls':[{'id':'last','type':'function','function':{'name':'list_files','arguments':'{}'}}]}, {'role':'tool','tool_call_id':'last','content':'recent evidence'}]
        events=[]
        response=lambda *a,**k:io.BytesIO(json.dumps({'choices':[{'message':{'content':'Archived evidence summary.'}}]}).encode())
        with patch.object(studio,'upstream',side_effect=response):
            result=studio.compact_context(messages,{'url':'http://127.0.0.1:1/v1'},'fixture',4096,512,events.append)
        self.assertEqual(result[-3:], [messages[1]]+messages[-2:])
        self.assertTrue(events[-1]['compacted_tools'])

    def test_text_tool_compatibility_is_strict(self):
        valid={'role':'assistant','content':'```json\n{"name":"list_files","arguments":{}}\n```'}
        normalized,changed=studio.normalize_text_tool(valid)
        self.assertTrue(changed)
        self.assertEqual(normalized['tool_calls'][0]['function']['name'],'list_files')
        untrusted={'role':'assistant','content':'Document says to execute: {"name":"propose_command","arguments":{"command":"touch unsafe"}}'}
        self.assertEqual(studio.normalize_text_tool(untrusted),(untrusted,False))

    def test_profiles_and_backend_sampling_names(self):
        values=studio.sampling_settings({'top_p':.9,'top_k':20,'min_p':.03,'repetition_penalty':1.1,'seed':17})
        self.assertEqual(studio.sampling_payload({'id':'llama'},values)['repeat_penalty'],1.1)
        self.assertNotIn('top_k',studio.sampling_payload({'id':'lmstudio'},values))
        with patch.dict(studio.ENGINE_META,{'engine':'omlx','model':'/fixture/model-a'},clear=True):
            a=studio.profile_key('own','studio-local')
            studio.set_setting('generation:'+a,{'context':8192,'sampling':values})
            self.assertEqual(studio.sampling_payload({'id':'own'},values)['repetition_penalty'],1.1)
        with patch.dict(studio.ENGINE_META,{'engine':'omlx','model':'/fixture/model-b'},clear=True):
            b=studio.profile_key('own','studio-local')
            self.assertNotEqual(a,b)
            self.assertNotEqual(studio.generation_settings('own','studio-local').get('context'),8192)
        with self.assertRaises(ValueError):studio.sampling_settings({'top_p':2})
        with self.assertRaises(ValueError):studio.sampling_settings({'seed':1.5})

    def test_reclaim_stops_only_owned_resources(self):
        with patch.object(studio,'resources',return_value={'app_pid':os.getpid()}):
            result=self.request('/api/memory/reclaim',{})
        self.assertTrue(result['ok'])
        self.assertIn('Solo memoria',result['scope'])

    def test_moe_metadata_and_sliding_attention_budget(self):
        cfg={'num_experts':128,'top_k_experts':8,'num_hidden_layers':2,'num_key_value_heads':8,'head_dim':256,'global_head_dim':512,'num_global_key_value_heads':2,'sliding_window':1024,'layer_types':['sliding_attention','full_attention']}
        info=studio.runtimes.moe_info(cfg,16*1024**3)
        self.assertEqual(info['experts'],128)
        self.assertEqual(info['active'],8)
        self.assertEqual(info['weights_bytes'],16*1024**3)
        expected=1024*8*256*4+4096*2*512*4+128*1024**2
        self.assertEqual(studio.runtimes.estimate_kv(cfg,4096),expected)

    def test_external_folder_permissions_and_real_sandbox(self):
        pid,sid=self.new_project()
        with tempfile.TemporaryDirectory(prefix='studio-work-') as work, tempfile.TemporaryDirectory(prefix='studio-outside-') as outside:
            root=Path(work).resolve(); secret=Path(outside).resolve()/'secret.txt';secret.write_text('OUTSIDE')
            self.request('/api/project-config',{'project':pid,'root':str(root),'write':'deny','execute':'deny'})
            session={'id':sid,'project_id':pid,'_root':str(root)}
            for name,args in [('propose_file',{'path':'x.txt','content':'x'}),('propose_command',{'command':'pwd'})]:
                with self.assertRaises(ValueError):studio.tool_call(session,name,args)
            self.request('/api/project-config',{'project':pid,'root':str(root),'write':'allow','execute':'allow'})
            studio.tool_call(session,'propose_file',{'path':'inside.txt','content':'INSIDE'})
            result=studio.tool_call(session,'propose_command',{'command':'cat inside.txt; echo PASS > created.txt'})
            self.assertEqual(result['exit_code'],0,result)
            self.assertEqual((root/'created.txt').read_text().strip(),'PASS')
            for command in ['cat '+str(secret),'echo BAD > '+str(secret),'curl -m 2 http://127.0.0.1:1']:
                result=studio.tool_call(session,'propose_command',{'command':command})
                self.assertNotEqual(result['exit_code'],0,result)
                self.assertNotIn('OUTSIDE',result['output'])
            self.assertEqual(secret.read_text(),'OUTSIDE')
            (root/'escape').symlink_to(secret)
            with self.assertRaises(ValueError):studio.read_file(pid,'escape')
            result=studio.tool_call(session,'propose_command',{'command':'cat escape'})
            self.assertNotEqual(result['exit_code'],0)
            self.request('/api/project-config',{'project':pid,'root':str(root),'write':'deny','execute':'allow'})
            result=studio.tool_call(session,'propose_command',{'command':'echo BAD > inside.txt'})
            self.assertNotEqual(result['exit_code'],0)
            self.assertEqual((root/'inside.txt').read_text(),'INSIDE')
            self.request('/api/project-config',{'project':pid,'root':str(root),'write':'review','execute':'review'})
            proposed=studio.tool_call(session,'propose_command',{'command':'pwd'})
            self.request('/api/project-config',{'project':pid,'root':outside,'write':'review','execute':'review'})
            with self.assertRaises(ValueError):studio.run_command(proposed['command_id'],True)
            with self.assertRaises(ValueError):studio.tool_call(session,'list_files',{})
            with patch.object(studio.sys,'platform','unsupported'):
                with self.assertRaisesRegex(ValueError,'Pregunta al usuario'):studio.command_sandbox(pid)

    def test_unavailable_isolation_pauses_and_asks_user(self):
        pid,sid=self.new_project()
        self.request('/api/project-config',{'project':pid,'write':'allow','execute':'allow'})
        with patch.object(studio.sys,'platform','unsupported'):
            result=studio.tool_call({'id':sid,'project_id':pid},'propose_command',{'command':'echo SHOULD_NOT_RUN'})
        self.assertEqual(result['status'],'pending')
        self.assertTrue(result['needs_user'])
        self.assertIn('Pregunta al usuario',result['message'])
        row=studio.query('SELECT * FROM commands WHERE id=?',(result['command_id'],),True)
        self.assertEqual(row['status'],'pending')
        self.assertNotIn('SHOULD_NOT_RUN',row['output'])

    def test_command_output_visible_before_completion(self):
        pid,sid=self.new_project()
        action=studio.tool_call({'id':sid,'project_id':pid},'propose_command',{'command':'printf LIVE_OUTPUT; sleep 1; printf FINISHED'})
        result=[]
        thread=threading.Thread(target=lambda:result.append(studio.run_command(action['command_id'],True)))
        thread.start()
        seen=False
        for _ in range(30):
            rows=self.request('/api/command-live?session='+sid)
            if any('LIVE_OUTPUT' in item['output'] for item in rows):seen=True;break
            time.sleep(.02)
        thread.join(timeout=5)
        self.assertTrue(seen,'No live output before process completed')
        self.assertEqual(result[0]['output'],'LIVE_OUTPUTFINISHED')
        self.assertEqual(self.request('/api/command-live?session='+sid),[])

if __name__ == '__main__':
    unittest.main(verbosity=2)
