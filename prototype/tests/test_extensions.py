"""Real MCP stdio interoperability and permission tests; isolated data only.
Requires the official filesystem server in STUDIO_MCP_OFFICIAL_ROOT (default temporary QA install).
"""
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.error
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
studio=core.studio

class ExtensionTests(unittest.TestCase):
    request=core.StudioTests.request
    new_project=core.StudioTests.new_project
    @classmethod
    def setUpClass(cls):
        core.StudioTests.setUpClass.__func__(cls)
        cls.work=Path(os.environ.get('STUDIO_MCP_OFFICIAL_ROOT','/private/tmp/agentic-mcp-qa/work')).resolve()
        cls.script=cls.work/'node_modules/@modelcontextprotocol/server-filesystem/dist/index.js'
        if not cls.script.is_file():raise unittest.SkipTest('Install official MCP filesystem server into isolated QA root first.')
    @classmethod
    def tearDownClass(cls):
        studio.stop_extensions()
        core.StudioTests.tearDownClass.__func__(cls)
    def setUp(self):
        studio.stop_extensions()
        self.pid,self.sid=self.new_project()
        self.request('/api/project-config',{'project':self.pid,'root':str(self.work),'write':'allow','execute':'allow'})
        self.session={'id':self.sid,'project_id':self.pid,'_root':str(self.work)}
        self.cfg={'project':self.pid,'mcp':[{'id':'official','command':'/opt/homebrew/bin/node','args':[str(self.script),str(self.work)],'tools':{'list_allowed_directories':'allow','read_text_file':'review','write_file':'review'}}],'browser':{'origins':['http://127.0.0.1:8421'],'read':'review','act':'review'}}
        self.request('/api/extensions',self.cfg)
    def test_official_handshake_discovery_and_reviewed_write(self):
        discovered=self.request('/api/extensions/discover',{'project':self.pid,'server':'official','approve':True})
        self.assertIn('write_file',[t['name'] for t in discovered['tools']])
        listing=studio.tool_call(self.session,'mcp_list_tools',{'server':'official'})
        self.assertEqual(set(t['name'] for t in listing['tools']),{'list_allowed_directories','read_text_file','write_file'})
        target=self.work/'reviewed-output.txt'
        if target.exists():target.unlink()
        action=studio.tool_call(self.session,'mcp_call',{'server':'official','tool':'write_file','arguments':{'path':str(target),'content':'MCP-VERIFIED-318'}})
        self.assertEqual(action['status'],'pending');self.assertFalse(target.exists())
        result=self.request('/api/extension/resolve',{'id':action['action_id'],'approve':True})
        self.assertEqual(result['status'],'executed',result)
        self.assertFalse(result['result'].get('isError'),result)
        self.assertEqual(target.read_text(),'MCP-VERIFIED-318')
        action=studio.tool_call(self.session,'mcp_call',{'server':'official','tool':'read_text_file','arguments':{'path':str(target)}})
        result=self.request('/api/extension/resolve',{'id':action['action_id'],'approve':True})
        self.assertIn('MCP-VERIFIED-318',json.dumps(result))
        pid=discovered['pid'];studio.stop_extensions()
        with self.assertRaises(ProcessLookupError):os.kill(pid,0)
    def test_permission_denial_scope_revoke_and_reject(self):
        with self.assertRaises(ValueError):studio.tool_call(self.session,'mcp_call',{'server':'official','tool':'delete_file','arguments':{}})
        action=studio.tool_call(self.session,'mcp_call',{'server':'official','tool':'write_file','arguments':{'path':str(self.work/'should-not-exist.txt'),'content':'NO'}})
        self.request('/api/project-config',{'project':self.pid,'root':str(self.work),'write':'deny','execute':'allow'})
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/extension/resolve',{'id':action['action_id'],'approve':True})
        self.assertEqual(self.request('/api/extension/resolve',{'id':action['action_id'],'approve':False})['status'],'rejected')
    def test_browser_policy_and_native_auth_fail_closed(self):
        with self.assertRaises(ValueError):studio.extensions.check_url('file:///etc/passwd',['http://127.0.0.1:8421'])
        with self.assertRaises(ValueError):studio.extensions.check_url('http://127.0.0.1:8422/',['http://127.0.0.1:8421'])
        with self.assertRaises(ValueError):studio.extensions.check_url('http://user:secret@127.0.0.1:8421/',['http://127.0.0.1:8421'])
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/native-browser/poll')
        action=studio.tool_call(self.session,'browser_navigate',{'url':'http://127.0.0.1:8421/'})
        self.assertEqual(action['status'],'pending')
        result=self.request('/api/extension/resolve',{'id':action['action_id'],'approve':True})
        self.assertEqual(result['status'],'failed',result)
        self.assertIn('no disponible',result['result']['error'])
        self.request('/api/project-config',{'project':self.pid,'root':str(self.work),'write':'deny','execute':'allow'})
        with self.assertRaises(ValueError):studio.tool_call(self.session,'browser_type',{'element':1,'text':'NO'})
    def test_official_outside_folder_and_write_deny(self):
        # Independent OS sandbox protects the project even if a tool ignores its roots contract.
        self.cfg['mcp'][0]['tools']['write_file']='allow'
        self.request('/api/extensions',self.cfg)
        self.request('/api/project-config',{'project':self.pid,'root':str(self.work),'write':'deny','execute':'allow'})
        result=studio.tool_call(self.session,'mcp_call',{'server':'official','tool':'write_file','arguments':{'path':str(self.work/'forbidden.txt'),'content':'NO'}})
        self.assertTrue(result.get('isError') or result.get('error'),result)
        self.assertFalse((self.work/'forbidden.txt').exists())
    def test_broker_single_action_timeout_and_revocation(self):
        broker=studio.extensions.BrowserBroker();broker.last_native=time.monotonic()
        result=[]
        thread=threading.Thread(target=lambda:result.append(broker.request(self.pid,'scope','browser_snapshot',{},[])))
        thread.start();job=broker.poll();self.assertEqual(job['project'],self.pid)
        broker.complete(job['id'],{'text':'native response fixture'})
        thread.join(timeout=2);self.assertEqual(result[0]['text'],'native response fixture')

    def test_uncertain_side_effect_requires_review_before_retry(self):
        script=self.work/'disconnect-server.cjs'
        script.write_text("const fs=require('fs'),rl=require('readline').createInterface({input:process.stdin});rl.on('line',line=>{const m=JSON.parse(line);let result={};if(m.method==='initialize')result={protocolVersion:'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'qa',version:'1'}};else if(m.method==='tools/list')result={tools:[{name:'once',inputSchema:{type:'object'}}]};else if(m.method==='tools/call'){fs.appendFileSync('uncertain-count.txt','X');process.exit(0);}else return;console.log(JSON.stringify({jsonrpc:'2.0',id:m.id,result}));});")
        target=self.work/'uncertain-count.txt'
        if target.exists():target.unlink()
        self.cfg['mcp']=[{'id':'disconnect','command':'/opt/homebrew/bin/node','args':[str(script)],'tools':{'once':'allow'}}]
        self.request('/api/extensions',self.cfg)
        args={'server':'disconnect','tool':'once','arguments':{}}
        result=studio.tool_call(self.session,'mcp_call',args)
        self.assertTrue(result.get('uncertain'),result);self.assertEqual(target.read_text(),'X')
        result=studio.tool_call(self.session,'mcp_call',args)
        self.assertEqual(result['status'],'pending');self.assertEqual(target.read_text(),'X')
        self.request('/api/extension/resolve',{'id':result['action_id'],'approve':False})
        self.assertEqual(target.read_text(),'X')

    def test_cancel_stops_mcp_and_restart_uses_new_process(self):
        first=self.request('/api/extensions/discover',{'project':self.pid,'server':'official','approve':True})['pid']
        self.request('/api/cancel',{})
        self.assertFalse(self.request('/api/extensions?project='+self.pid)['mcp_running'])
        with self.assertRaises(ProcessLookupError):os.kill(first,0)
        second=self.request('/api/extensions/discover',{'project':self.pid,'server':'official','approve':True})['pid']
        self.assertNotEqual(first,second)
        self.assertTrue(self.request('/api/extensions?project='+self.pid)['mcp_running'])

if __name__=='__main__':unittest.main(verbosity=2)
