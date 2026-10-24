"""Project isolation over real TLS, Hub file integrity, compact MCP and official OpenAI sandbox."""
import hashlib,http.cookiejar,json,os,ssl,sys,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
studio=core.studio
import model_hub,agent_extensions,openai_oauth

class LANTests(unittest.TestCase):
    request=core.StudioTests.request
    new_project=core.StudioTests.new_project
    @classmethod
    def setUpClass(cls):
        core.StudioTests.setUpClass.__func__(cls);studio.BACKEND_PORT=cls.server.server_port
    @classmethod
    def tearDownClass(cls):
        studio.LAN.stop();core.StudioTests.tearDownClass.__func__(cls)
    def setUp(self):
        studio.LAN.stop();self.pid,self.sid=self.new_project();self.other,self.other_sid=self.new_project()
        self.request('/api/project-config',{'project':self.pid,'write':'review','execute':'review'})
        self.info=studio.LAN.start(self.pid,True,'127.0.0.1');self.url=self.info['url']
        context=ssl.create_default_context(cafile=str(studio.LAN.local/'lan-ca.pem'))
        self.cookies=http.cookiejar.CookieJar();self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(self.cookies))
    def mobile(self,path,body=None):
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with self.http.open(req,timeout=10) as r:
            raw=r.read()
            return json.loads(raw) if r.headers.get('Content-Type','').startswith('application/json') else raw
    def pair(self):
        from urllib.parse import parse_qs,urlsplit
        code=parse_qs(urlsplit(self.info['pair_url']).query)['token'][0];self.mobile('/?pair='+code);return code
    def test_silent_tls_client_cannot_block_pairing(self):
        import socket
        from urllib.parse import urlsplit
        address=urlsplit(self.url)
        stalled=socket.create_connection((address.hostname,address.port),timeout=3)
        try:
            self.pair()
            self.assertEqual(self.mobile('/api/state')['mobile_project'],self.pid)
        finally:stalled.close()

    def test_invalid_mobile_json_is_rejected(self):
        self.pair()
        for body in ([],None,'text',42):
            request=urllib.request.Request(self.url+'/api/mobile/project',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:self.http.open(request,timeout=3)
            self.assertEqual(error.exception.code,400)

    def test_tls_pin_and_pair_single_use(self):
        cert=ssl.PEM_cert_to_DER_cert((studio.LAN.local/'lan-leaf.pem').read_text());self.assertEqual(hashlib.sha256(cert).hexdigest(),self.info['fingerprint'])
        with self.assertRaises(urllib.error.HTTPError):self.mobile('/api/state')
        code=self.pair();self.assertTrue(any(c.secure for c in self.cookies))
        with self.assertRaises(urllib.error.HTTPError):self.mobile('/?pair='+code)
        data=self.mobile('/api/state');self.assertEqual([p['id'] for p in data['projects']],[self.pid]);self.assertNotIn('data_path',data)
    def test_mobile_cannot_cross_project_or_admin_native_routes(self):
        self.pair()
        for path in ['/api/messages?session='+self.other_sid,'/api/files?project='+self.other,'/api/native-browser/poll','/api/oauth/status']:
            with self.assertRaises(urllib.error.HTTPError) as e:self.mobile(path)
            self.assertEqual(e.exception.code,403)
        for path,body in [('/api/project-config',{'project':self.pid,'write':'allow'}),('/api/engine/start',{}),('/api/chat',{'session_id':self.other_sid})]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.mobile(path,body)
            self.assertEqual(e.exception.code,403)
    def test_mobile_desktop_panels_remain_project_scoped(self):
        self.pair();studio.CANCEL.clear()
        studio.write_file(self.pid,'shared.txt','FICTITIOUS-IPAD-SHARED')
        self.assertIn(b'--lime',self.mobile('/style.css'))
        self.assertIn(b'Contexto y acciones',self.mobile('/'))
        from urllib.parse import urlencode
        self.assertEqual(self.mobile('/api/file?'+urlencode({'project':self.pid,'path':'shared.txt'}))['content'],'FICTITIOUS-IPAD-SHARED')
        self.assertEqual(self.mobile('/api/tool-events?session='+self.sid),[])
        for path in ['/api/file?'+urlencode({'project':self.other,'path':'secret.txt'}),'/api/file?'+urlencode({'project':self.pid,'path':'../secret.txt'}),'/api/tool-events?session='+self.other_sid]:
            with self.assertRaises(urllib.error.HTTPError):self.mobile(path)
        with patch.object(studio,'CHAT_SESSION',self.other_sid):
            with self.assertRaises(urllib.error.HTTPError):self.mobile('/api/mobile/cancel',{'session_id':self.sid})
            self.assertFalse(studio.CANCEL.is_set())
        with patch.object(studio,'CHAT_SESSION',self.sid),patch.object(studio,'stop_commands'),patch.object(studio,'stop_extensions'),patch.object(studio,'stop_openai'):
            self.assertTrue(self.mobile('/api/mobile/cancel',{'session_id':self.sid})['ok'])
            self.assertTrue(studio.CANCEL.is_set())
        studio.CANCEL.clear()

    def test_mobile_project_selector_only_authorized_projects(self):
        hidden,hidden_sid=self.new_project()
        self.request('/api/project-config',{'project':self.other,'write':'deny','execute':'deny'})
        self.info=studio.LAN.start(self.pid,True,'127.0.0.1',projects=[self.pid,self.other]);self.url=self.info['url'];self.pair()
        data=self.mobile('/api/state')
        self.assertEqual({p['id'] for p in data['projects']},{self.pid,self.other})
        self.assertEqual(data['mobile_project'],self.pid)
        with self.assertRaises(urllib.error.HTTPError):self.mobile('/api/messages?session='+self.other_sid)
        self.mobile('/api/mobile/project',{'project':self.other})
        data=self.mobile('/api/state');self.assertEqual(data['mobile_project'],self.other)
        self.assertEqual({s['id'] for s in data['sessions']},{self.other_sid})
        self.assertEqual(next(p for p in data['projects'] if p['id']==self.other)['config']['write'],'deny')
        self.assertEqual(self.mobile('/api/messages?session='+self.other_sid),[])
        for sid in (self.sid,hidden_sid):
            with self.assertRaises(urllib.error.HTTPError):self.mobile('/api/messages?session='+sid)
        with self.assertRaises(urllib.error.HTTPError):self.mobile('/api/mobile/project',{'project':hidden})
        self.mobile('/api/mobile/project',{'project':self.pid})
        self.assertEqual(self.mobile('/api/state')['mobile_project'],self.pid)
        self.request('/api/project-config',{'project':self.other,'write':'review','execute':'deny'})
        with self.assertRaises(urllib.error.HTTPError) as e:self.mobile('/api/state')
        self.assertEqual(e.exception.code,401)

    def test_reviewed_write_and_scope_revocation(self):
        self.pair();a=studio.tool_call({'id':self.sid,'project_id':self.pid},'propose_file',{'path':'mobile.txt','content':'FICTITIOUS-TLS-901'})
        self.assertFalse((studio.project_root(self.pid)/'mobile.txt').exists())
        result=self.mobile('/api/proposal/resolve',{'id':a['proposal_id'],'approve':True});self.assertTrue(result['ok'])
        self.assertEqual((studio.project_root(self.pid)/'mobile.txt').read_text(),'FICTITIOUS-TLS-901')
        self.request('/api/project-config',{'project':self.pid,'write':'deny','execute':'review'})
        with self.assertRaises(urllib.error.HTTPError) as e:self.mobile('/api/state')
        self.assertEqual(e.exception.code,401)
    def test_stop_closes_tls_port_and_rejects_public_bind(self):
        import socket
        port=studio.LAN.server.server_port;studio.LAN.stop();s=socket.socket();self.assertNotEqual(s.connect_ex(('127.0.0.1',port)),0);s.close()
        for host in ['0.0.0.0','8.8.8.8','169.254.1.2']:
            with self.assertRaises(ValueError):studio.LAN.start(self.pid,True,host)

class CompactCatalogTests(unittest.TestCase):
    def test_catalog_excludes_large_output_schema_and_bounds_description(self):
        source=[{'name':'read','description':'D'*20000,'inputSchema':{'type':'object'},'outputSchema':{'padding':'X'*500000}}]
        compact=agent_extensions.compact_tools(source);self.assertNotIn('outputSchema',compact[0]);self.assertEqual(len(compact[0]['description']),2000);self.assertLess(len(json.dumps(compact)),2200)
    def test_huggingface_public_exception_requires_exact_endpoints(self):
        from remote_mcp import OAuth
        oauth=OAuth(lambda p,s:{'url':'https://huggingface.co/mcp'},lambda p:'scope',lambda *args:{})
        oauth.prepared['qa']={'pid':'p','sid':'s','scope':'scope','resource':'https://huggingface.co/mcp','issuers':['https://huggingface.co'],'scopes':['read-mcp'],'deadline':time.time()+60}
        meta={'issuer':'https://huggingface.co','authorization_endpoint':'https://huggingface.co/oauth/authorize','token_endpoint':'https://huggingface.co/oauth/token','registration_endpoint':'https://huggingface.co/oauth/register','code_challenge_methods_supported':['S256'],'token_endpoint_auth_methods_supported':['client_secret_basic','client_secret_post']}
        with patch('remote_mcp.ok_json',return_value=meta):self.assertTrue(oauth.metadata('p','s','qa','https://huggingface.co')['compatibility_note'])
        with patch('remote_mcp.ok_json',return_value={**meta,'token_endpoint':'https://example.com/token'}):
            with self.assertRaises(ValueError):oauth.metadata('p','s','qa','https://huggingface.co')

class HubTests(unittest.TestCase):
    def test_hash_verification_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            downloads=model_hub.Downloads(folder);root=Path(folder)/'repo';root.mkdir();p=root/'weights.gguf';p.write_bytes(b'actual-weight-fixture')
            item={'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'blob':''};self.assertTrue(downloads.verify(p,item));p.write_bytes(b'WRONG');self.assertFalse(downloads.verify(p,item))
            (root/'link').symlink_to(Path(folder)/'elsewhere')
            with self.assertRaises(ValueError):downloads.safe(root,'link/weights.gguf')
            with self.assertRaises(ValueError):downloads.safe(root,'../escape.gguf')
    def test_search_defaults_latest_and_download_needs_approval(self):
        with patch('model_hub.request',return_value=(200,{},[])) as req:
            self.assertEqual(model_hub.search()['sort'],'lastModified');self.assertIn('direction=-1',req.call_args[0][0]);self.assertIn('sort=lastModified',req.call_args[0][0])
        with self.assertRaises(ValueError):model_hub.Downloads().start('owner/repo',['weights.gguf'],False)
        for bad in ('../outside','/private/secret','owner/repo/third'):
            with self.assertRaises(ValueError):model_hub.repo_id(bad)

class OpenAISandboxTests(unittest.TestCase):
    def test_official_adapter_cannot_read_external_documents_or_spawn_shell(self):
        if not openai_oauth.BINARY.is_file():self.skipTest('Official Codex CLI not installed')
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)/'adapter';outside=Path(folder)/'outside-private.txt';outside.write_text('MUST-NOT-READ-492')
            with patch('openai_oauth.subprocess.Popen',wraps=__import__('subprocess').Popen) as launch:
                client=openai_oauth.Client(home)
            self.assertEqual(launch.call_args.kwargs['env']['HOME'],str(Path.home()))
            self.assertEqual(launch.call_args.kwargs['env']['CODEX_HOME'],str(home.resolve()))
            try:
                self.assertFalse(client.status()['connected'])
                self.assertTrue(client.models())
                own=home/'own.txt';own.write_text('OWN-RUNTIME-FIXTURE')
                result=client.request('fs/readFile',{'path':str(own)})
                self.assertTrue(result)
                with self.assertRaises(ValueError) as e:client.request('fs/readFile',{'path':str(outside)})
                self.assertNotIn('MUST-NOT-READ',str(e.exception))
                with self.assertRaises(ValueError):client.request('process/spawn',{'command':['/bin/sh','-c','cat '+str(outside)],'cwd':str(home),'processHandle':'qa-denied-shell'})
                pid=client.proc.pid
            finally:client.close()
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)

class HubTransferTests(unittest.TestCase):
    def test_cancel_resume_hash_and_no_clobber(self):
        import io
        with tempfile.TemporaryDirectory() as folder:
            data=b'RESUMABLE-WEIGHT-FIXTURE'*24000
            item={'name':'weight.gguf','size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'blob':'','kind':'gguf'}
            meta={'repo':'owner/model','commit':'a'*40,'files':[item]}
            downloads=model_hub.Downloads(folder)
            class Response(io.BytesIO):
                status=200;headers={}
                def read(self,n=-1):
                    if n>131072:raise AssertionError('Unbounded download read')
                    chunk=super().read(n)
                    if self.tell()>=131072:downloads.cancelled.set()
                    return chunk
            with patch('model_hub.files',return_value=meta),patch.object(model_hub.DOWNLOAD_HTTP,'open',return_value=Response(data)):
                downloads.start('owner/model',['weight.gguf'],True);downloads.thread.join(5)
            self.assertEqual(downloads.status()['status'],'cancelled');destination=Path(folder)/'owner--model';part=destination/'weight.gguf.part';self.assertGreater(part.stat().st_size,0);offset=part.stat().st_size
            class Remaining(io.BytesIO):
                status=206;headers={'Content-Range':'bytes '+str(offset)+'-'+str(len(data)-1)+'/'+str(len(data))}
                def read(self,n=-1):
                    if n>131072:raise AssertionError('Unbounded download read')
                    return super().read(n)
            def resumed(req,**kwargs):
                self.assertEqual(req.get_header('Range'),'bytes='+str(offset)+'-');return Remaining(data[offset:])
            with patch('model_hub.files',return_value=meta),patch.object(model_hub.DOWNLOAD_HTTP,'open',side_effect=resumed):
                downloads.start('owner/model',['weight.gguf'],True);downloads.thread.join(5)
            self.assertEqual(downloads.status()['status'],'completed');self.assertEqual((destination/'weight.gguf').read_bytes(),data)
            target=destination/'weight.gguf';target.write_bytes(b'KEEP-EXISTING-FILE')
            with patch('model_hub.files',return_value=meta):
                downloads.start('owner/model',['weight.gguf'],True);downloads.thread.join(5)
            self.assertEqual(downloads.status()['status'],'failed');self.assertEqual(target.read_bytes(),b'KEEP-EXISTING-FILE')

class OpenAIAdapterLogicTests(unittest.TestCase):
    class Simulated(openai_oauth.Client):
        def __init__(self,data):
            import threading
            self.lock=threading.RLock();self.home=Path('/isolated-runtime');self.closed=False;self.serial=1;self.data=data;self.methods=[];self.index=0
        def status(self):return {'connected':True}
        def request(self,method,params=None):
            self.methods.append(method)
            if method=='thread/start':return {'thread':{'id':'fixture-thread'}}
            if method=='turn/start':return {'turn':{'id':'fixture-turn'}}
            return {}
        def receive(self,timeout=1):
            self.index+=1
            if self.index==1:return {'method':'item/agentMessage/delta','params':{'delta':self.data}}
            return {'method':'turn/completed','params':{'turn':{'status':'completed'}}}
        def close(self):self.closed=True
    def test_structured_reply_releases_its_context(self):
        import threading
        client=self.Simulated(json.dumps({'content':'FICTITIOUS-CLOUD-117','tool_name':'','arguments_json':'{}'}));events=[]
        result,_=client.generate({'model':'fixture','messages':[]},events.append,threading.Event())
        self.assertEqual(result['content'],'FICTITIOUS-CLOUD-117');self.assertTrue(client.closed);self.assertIn('thread/unsubscribe',client.methods)
    def test_model_cannot_select_unavailable_tool(self):
        import threading
        client=self.Simulated(json.dumps({'content':'','tool_name':'builtin_shell','arguments_json':'{}'}))
        with self.assertRaises(ValueError):client.generate({'model':'fixture','messages':[],'tools':[]},lambda e:None,threading.Event())
        self.assertTrue(client.closed)
    def test_output_limit_interrupts_model_and_releases_helper(self):
        import threading
        client=self.Simulated('X'*5000)
        with self.assertRaises(ValueError):client.generate({'model':'fixture','messages':[],'max_tokens':1},lambda e:None,threading.Event())
        self.assertIn('turn/interrupt',client.methods);self.assertTrue(client.closed)

class OpenAIGatewayTests(unittest.TestCase):
    request=core.StudioTests.request
    @classmethod
    def setUpClass(cls):core.StudioTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):core.StudioTests.tearDownClass.__func__(cls)
    def test_compatible_json_and_streaming_gateway(self):
        class Fixture:
            def generate(self,body,emit,cancel):
                emit({'type':'delta','text':'PUBLIC-FIXTURE-327'})
                return {'role':'assistant','content':'PUBLIC-FIXTURE-327'},{'completion_tokens':4}
        previous=studio.setting('selected_provider')
        studio.set_setting('selected_provider','openai-oauth')
        try:
            with patch.object(studio,'openai_client',return_value=Fixture()):
                answer=self.request('/v1/chat/completions',{'model':'fixture','messages':[{'role':'user','content':'public test'}]})
                self.assertEqual(answer['choices'][0]['message']['content'],'PUBLIC-FIXTURE-327')
                req=urllib.request.Request(self.base+'/v1/chat/completions',data=json.dumps({'model':'fixture','messages':[],'stream':True}).encode(),headers={'Authorization':'Bearer '+studio.TOKEN,'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=10) as r:text=r.read().decode()
                self.assertIn('data: [DONE]',text);self.assertIn('PUBLIC-FIXTURE-327',text)
        finally:studio.set_setting('selected_provider',previous)

if __name__=='__main__':unittest.main()
