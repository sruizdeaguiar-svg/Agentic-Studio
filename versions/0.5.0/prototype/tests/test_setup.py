import sys,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
class SetupTests(core.StudioTests):
 def test_detect_and_save_without_loading_models(self):
  with tempfile.TemporaryDirectory(prefix='agentic-model-discovery-') as folder:
   with patch.object(core.studio,'discover_model_roots',return_value=[folder]),patch.object(core.studio,'start_engine') as load:
    data=self.request('/api/setup');self.assertEqual(data['detected'],[folder]);load.assert_not_called()
   self.request('/api/setup',{'roots':[folder,folder],'complete':True});self.assertEqual(core.studio.setting('model_roots'),[str(Path(folder).resolve())]);self.assertTrue(self.request('/api/setup')['complete'])
 def test_bad_model_root_preserves_configuration(self):
  before=self.request('/api/setup')['roots']
  with self.assertRaises(urllib.error.HTTPError):self.request('/api/setup',{'roots':['/missing/agentic/models'],'complete':True})
  self.assertEqual(self.request('/api/setup')['roots'],before)
for name in dir(core.StudioTests):
 if name.startswith('test_') and name not in SetupTests.__dict__:setattr(SetupTests,name,None)
