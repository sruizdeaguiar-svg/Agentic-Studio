"""Loopback HTTP OAuth/PKCE + MCP integration; fictitious credentials and data only."""
import base64,hashlib,json,secrets,sys,threading,time,unittest
from pathlib import Path
from urllib.parse import parse_qs,urlsplit,urlencode
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import remote_mcp as remote
import test_studio as core

class Provider(BaseHTTPRequestHandler):
    origin='';codes={};refreshes=0;calls=0;requests=[];sse=False;redirect=False;expand=False;fail_call=False
    def log_message(self,*a):pass
    def reply(self,obj,status=200,headers=None):
        raw=json.dumps(obj).encode();self.send_response(status)
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_DELETE(self):self.reply({},200)
    def do_GET(self):
        p=urlsplit(self.path)
        if p.path=='/.well-known/oauth-protected-resource/mcp':return self.reply({'resource':self.origin+'/mcp','authorization_servers':[self.origin],'scopes_supported':['read','write']})
        if p.path=='/.well-known/oauth-authorization-server':return self.reply({'issuer':self.origin,'authorization_endpoint':self.origin+'/authorize','token_endpoint':self.origin+'/token','registration_endpoint':self.origin+'/register','code_challenge_methods_supported':['S256'],'token_endpoint_auth_methods_supported':['none']})
        if p.path=='/authorize':
            q=parse_qs(p.query)
            if q['code_challenge_method']!=['S256'] or q['resource']!=[self.origin+'/mcp']:return self.reply({},400)
            code=secrets.token_urlsafe(20);self.codes[code]=q
            return self.reply({'callback':q['redirect_uri'][0]+'?'+urlencode({'state':q['state'][0],'code':code})})
        self.reply({},404)
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
        if self.path=='/register':
            q=json.loads(raw)
            assert q['token_endpoint_auth_method']=='none'
            return self.reply({'client_id':'qa-public','token_endpoint_auth_method':'none'},201)
        if self.path=='/token':
            q=parse_qs(raw.decode());assert q['resource']==[self.origin+'/mcp']
            if q['grant_type']==['authorization_code']:
                original=self.codes.pop(q['code'][0],None)
                if not original:return self.reply({},400)
                challenge=base64.urlsafe_b64encode(hashlib.sha256(q['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
                if original['code_challenge']!=[challenge] or original['redirect_uri']!=q['redirect_uri']:return self.reply({},400)
            else:
                if q.get('refresh_token')!=['qa-refresh']:return self.reply({},400)
                type(self).refreshes+=1
            return self.reply({'token_type':'Bearer','access_token':'qa-access','refresh_token':'qa-refresh','expires_in':120,'scope':'read write' if self.expand else 'read'})
        if self.path=='/redirect':
            self.send_response(302);self.send_header('Location',self.origin+'/mcp');self.end_headers();return
        if self.path!='/mcp':return self.reply({},404)
        if self.headers.get('Authorization')!='Bearer qa-access':return self.reply({},401,{'WWW-Authenticate':'Bearer resource_metadata="'+self.origin+'/.well-known/oauth-protected-resource/mcp", scope="read"'})
        body=json.loads(raw);type(self).requests.append(body)
        method=body['method']
        if method=='notifications/initialized':return self.reply({},202)
        if method=='initialize':result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'QA','version':'1'}}
        elif method=='tools/list':result={'tools':[{'name':'read','inputSchema':{'type':'object'}},{'name':'write','inputSchema':{'type':'object'}}]}
        elif method=='tools/call':
            type(self).calls+=1
            if self.fail_call:return self.reply({'error':'uncertain fixture'},500)
            result={'content':[{'type':'text','text':'FICTITIOUS-REMOTE-937'}]}
        else:return self.reply({},400)
        message={'jsonrpc':'2.0','id':body['id'],'result':result}
        if self.sse:
            data=('event: message\ndata: '+json.dumps(message)+'\n\n').encode();self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(data)));self.send_header('Mcp-Session-Id','qa-session');self.end_headers();self.wfile.write(data)
        else:self.reply(message,headers={'Mcp-Session-Id':'qa-session'})

class RemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Provider);cls.origin='http://127.0.0.1:'+str(cls.server.server_port);Provider.origin=cls.origin
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.scope='root-and-project-permissions';self.store={};self.opened=[];Provider.sse=False;Provider.expand=False;Provider.fail_call=False
        self.spec={'id':'remote','transport':'http','url':self.origin+'/mcp','tools':{'read':'allow','write':'allow'},'read_only_tools':['read']}
        self.oauth=remote.OAuth(lambda p,s:self.spec,lambda p:self.scope,self.native)
    def native(self,p,op,args):
        if op=='vault_get':return {'value':self.store.get(args['account'],'')}
        if op=='vault_put':self.store[args['account']]=args['value'];return {'ok':True}
        if op=='vault_delete':self.store.pop(args['account'],None);return {'ok':True}
        if op=='oauth_open':self.opened.append(args['url']);return {'opened':True}
        raise AssertionError(op)
    def begin(self):
        p=self.oauth.prepare('p','remote');self.assertEqual(p['scopes'],['read']);self.oauth.metadata('p','remote',p['id'],self.origin)
        self.oauth.start('p','remote',p['id'],'',['read'],'http://127.0.0.1:12345/oauth/callback')
        callback=remote.ok_json(self.opened[-1])['callback'];return parse_qs(urlsplit(callback).query)
    def login(self):self.oauth.callback(self.begin())
    def test_oauth_pkce_refresh_and_forget(self):
        self.login();self.assertTrue(self.oauth.status('p','remote')['connected']);self.assertFalse(self.oauth.status('other-project','remote')['connected'])
        for key in self.store:
            record=json.loads(self.store[key]);record['expires_at']=0;self.store[key]=json.dumps(record)
        previous=Provider.refreshes;self.assertEqual(self.oauth.token('p','remote'),'qa-access');self.assertEqual(Provider.refreshes,previous+1)
        self.oauth.forget('p','remote');self.assertFalse(self.store)
    def test_state_replay_and_permission_change(self):
        callback=self.begin()
        with self.assertRaises(ValueError):self.oauth.callback({**callback,'state':['bad-state']})
        self.scope='different-root'
        with self.assertRaises(ValueError):self.oauth.callback(callback)
        self.assertFalse(self.store)
        self.scope='root-and-project-permissions';callback=self.begin();self.oauth.callback(callback)
        with self.assertRaises(ValueError):self.oauth.callback(callback)
    def test_provider_scope_escalation_rejected(self):
        callback=self.begin();Provider.expand=True
        with self.assertRaises(ValueError):self.oauth.callback(callback)
        self.assertFalse(self.store)
    def test_http_json_sse_and_no_local_roots(self):
        self.login()
        for sse in (False,True):
            Provider.sse=sse;c=remote.HTTPClient(self.spec,lambda:self.oauth.token('p','remote'))
            self.assertEqual(len(c.tools),2);self.assertIn('937',c.call('read',{})['content'][0]['text']);self.assertIsNone(c.proc);c.close();self.assertTrue(c.closed)
        for request in Provider.requests:
            if request['method']=='initialize':self.assertEqual(request['params']['capabilities'],{})
    def test_401_and_redirect_not_replayed(self):
        before=Provider.calls
        with self.assertRaises(ValueError):remote.HTTPClient(self.spec,lambda:'bad-token')
        self.assertEqual(before,Provider.calls)
        with self.assertRaises(ValueError):remote.request(self.origin+'/redirect','POST',b'{}')
        for bad in ('http://example.com/mcp','https://user:password@example.com/mcp','file:///tmp/private'):
            with self.assertRaises(ValueError):remote.endpoint(bad)
    def test_uncertain_remote_tool_runs_once(self):
        self.login();c=remote.HTTPClient(self.spec,lambda:self.oauth.token('p','remote'))
        previous=Provider.calls;Provider.fail_call=True
        with self.assertRaises(ValueError):c.call('write',{})
        self.assertEqual(Provider.calls,previous+1);self.assertTrue(c.closed)
        self.assertEqual(c.last_token,'')
    def test_unapproved_issuer_duplicate_callback_and_extra_scopes(self):
        prepared=self.oauth.prepare('p','remote')
        with self.assertRaises(ValueError):self.oauth.metadata('p','remote',prepared['id'],'https://unapproved.invalid')
        self.oauth.metadata('p','remote',prepared['id'],self.origin)
        with self.assertRaises(ValueError):self.oauth.start('p','remote',prepared['id'],'qa',['read','write'],'http://127.0.0.1:12345/oauth/callback')
        callback=self.begin()
        with self.assertRaises(ValueError):self.oauth.callback({**callback,'state':callback['state']*2})
        self.assertFalse(self.store)
    def test_project_write_deny_and_tool_review(self):
        studio=core.studio
        with patch.object(studio,'extension_config',return_value={'mcp':[self.spec]}),patch.object(studio,'project_config',return_value={'write':'deny','execute':'allow'}):
            self.assertEqual(studio.extension_policy('p','mcp_call',{'server':'remote','tool':'write'}),'deny')
            self.assertEqual(studio.extension_policy('p','mcp_call',{'server':'remote','tool':'read'}),'allow')
        with patch.object(studio,'extension_config',return_value={'mcp':[self.spec]}),patch.object(studio,'project_config',return_value={'write':'review','execute':'allow'}):
            self.assertEqual(studio.extension_policy('p','mcp_call',{'server':'remote','tool':'write'}),'review')

if __name__=='__main__':unittest.main()
