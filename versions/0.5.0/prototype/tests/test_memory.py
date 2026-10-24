"""Check page-size conversion and avoid double-counting compression/swap/purgeable."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_studio as core
class MemoryTests(unittest.TestCase):
 def test_macos_page_sizes_and_available(self):
  for size in (4096,16384):
   raw=f'Mach Virtual Memory Statistics: (page size of {size} bytes)\nPages free: 100.\nPages inactive: 200.\nPages speculative: 30.\nPages purgeable: 190.\nPages occupied by compressor: 500.\nPages wired down: 800.\n'
   data=core.studio.memory_snapshot(raw)
   self.assertEqual(data['available_mb'],round(330*size/1024**2,1));self.assertEqual(data['free_mb'],round(100*size/1024**2,1));self.assertTrue(data['available_estimated'])
 def test_missing_stats_do_not_report_zero_available(self):
  with self.assertRaises(ValueError):core.studio.memory_snapshot('Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 10.')
