"""CRUD is recoverable; external files and per-project permissions survive."""
import sys,tempfile,unittest,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
studio=core.studio
class ProjectTests(core.StudioTests):
 # Reuse only the fixture setup and API helper, not the inherited test cases.
 def test_project_create_modify_delete_restore(self):
  with tempfile.TemporaryDirectory(prefix='agentic-project-crud-') as root:
   f=Path(root)/'keep.txt';f.write_text('FICTITIOUS-PRESERVE-42')
   pid=self.request('/api/projects',{'name':'QA CRUD','instructions':'Ficticio','config':{'root':root,'write':'deny','execute':'review'}})['id']
   sid=self.request('/api/sessions',{'project_id':pid})['id'];studio.add_message(sid,'user','FICTITIOUS-CHAT')
   self.assertEqual(studio.project_config(pid)['write'],'deny');self.assertEqual(studio.project_root(pid),Path(root).resolve())
   self.request('/api/projects',{'id':pid,'name':'QA renamed','instructions':'Updated','config':{'root':root,'write':'review','execute':'deny'}})
   self.assertEqual(studio.project(pid)['name'],'QA renamed');self.assertEqual(studio.project_config(pid)['execute'],'deny');scope=studio.extension_scope(pid)
   result=self.request('/api/projects/delete',{'id':pid});self.assertTrue(result['files_preserved']);self.assertEqual(f.read_text(),'FICTITIOUS-PRESERVE-42')
   data=self.request('/api/state');self.assertNotIn(pid,[p['id'] for p in data['projects']]);self.assertNotIn(sid,[s['id'] for s in data['sessions']]);self.assertIn(pid,[p['id'] for p in data['archived_projects']])
   with self.assertRaises(ValueError):studio.project_root(pid)
   self.request('/api/projects/restore',{'id':pid});self.assertEqual(studio.project_config(pid)['execute'],'deny');self.assertEqual(len(self.request('/api/messages?session='+sid)),1);self.assertNotEqual(studio.extension_scope(pid),scope)
 def test_invalid_folder_is_atomic_and_permissions_independent(self):
  before=len(self.request('/api/state')['projects'])
  with self.assertRaises(urllib.error.HTTPError):self.request('/api/projects',{'name':'Invalid','config':{'root':'/missing/agentic-qa','write':'allow','execute':'deny'}})
  self.assertEqual(len(self.request('/api/state')['projects']),before)
  a=self.request('/api/projects',{'name':'A','config':{'write':'deny','execute':'deny'}})['id'];b=self.request('/api/projects',{'name':'B','config':{'write':'review','execute':'review'}})['id']
  self.assertNotEqual(studio.project_root(a),studio.project_root(b));self.assertEqual(studio.project_config(a)['write'],'deny');self.assertEqual(studio.project_config(b)['write'],'review')
# Do not duplicate the inherited core suite.
for name in dir(core.StudioTests):
 if name.startswith('test_') and name not in ProjectTests.__dict__:setattr(ProjectTests,name,None)
