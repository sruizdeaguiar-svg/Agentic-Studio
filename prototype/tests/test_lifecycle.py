"""Lifecycle serialization and fail-closed transitions; no unrelated processes touched."""
import sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
studio=core.studio
class LifecycleTests(unittest.TestCase):
    def test_active_generation_blocks_model_switch(self):
        with studio.CHAT_LOCK,patch.object(studio,'start_engine') as start:
            with self.assertRaisesRegex(ValueError,'generación'):studio.switch_engine({})
            start.assert_not_called()
    def test_global_stop_cancels_queued_start(self):
        with studio.ENGINE_TRANSITION:
            errors=[];entered=threading.Event()
            def run():
                entered.set()
                try:studio.switch_engine({})
                except ValueError as e:errors.append(str(e))
            with patch.object(studio,'start_engine') as start:
                worker=threading.Thread(target=run);worker.start();entered.wait(1)
                # The request has to sample its epoch before waiting on the mutex.
                import time;time.sleep(.05)
                with patch.object(studio,'stop_engine'),patch.object(studio,'stop_commands'):
                    studio.stop_all_engines(False)
            self.assertFalse(start.called)
        worker.join(2);self.assertFalse(worker.is_alive());self.assertIn('parada global',errors[0]);studio.CANCEL.clear()
    def test_global_stop_includes_explicit_lmstudio_shutdown(self):
        with patch.object(studio,'stop_commands'),patch.object(studio,'stop_engine') as own,patch.object(studio,'stop_lmstudio',return_value={'closed':True}) as lm:
            result=studio.stop_all_engines(True)
            own.assert_called_once();lm.assert_called_once();self.assertTrue(result['lmstudio']['closed'])
        studio.CANCEL.clear()
    def test_invalid_selected_model_preserves_current_engine(self):
        with patch.object(studio,'stop_engine') as stop:
            with self.assertRaises(ValueError):studio.switch_engine({'engine':'llama','model':'/missing.gguf','binary':'/missing/llama-server','confirm_load':True})
            stop.assert_not_called()
