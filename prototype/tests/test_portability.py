"""Portable paths and optional-engine discovery, without requiring installed engines."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_studio as core

class PortabilityTests(unittest.TestCase):
    def test_missing_or_inaccessible_runtime_is_not_installed(self):
        runtime=core.studio.runtimes
        with patch.object(Path,'is_file',side_effect=PermissionError):
            self.assertFalse(runtime.executable('/unavailable/python'))
            self.assertIsNone(runtime.find_executable(['/unavailable/python']))

    def test_explicit_runtime_paths_do_not_depend_on_homebrew(self):
        runtime=core.studio.runtimes
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);python=root/'custom-env/bin/python3';python.parent.mkdir(parents=True);python.write_text('#!/bin/sh\nexit 0\n');python.chmod(0o755)
            omlx=root/'Custom Engine.app/Contents/Resources';cli=omlx.parent/'MacOS/omlx-cli';cli.parent.mkdir(parents=True);cli.write_text('#!/bin/sh\nexit 0\n');cli.chmod(0o755)
            with patch.dict(os.environ,{'AGENTIC_VLLM_PYTHON':str(python),'AGENTIC_OMLX_ROOT':str(omlx)}):
                actual,resources=runtime.resolve_runtime_paths()
            self.assertEqual(actual,python);self.assertEqual(resources,omlx)

    def test_bundled_codex_is_preferred_over_host_installation(self):
        module=core.studio.openai_oauth
        spec=importlib.util.spec_from_file_location('portable_codex_fixture',module.__file__);fresh=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,{},clear=True),patch.object(Path,'is_file',return_value=True):spec.loader.exec_module(fresh)
        self.assertEqual(fresh.BINARY,fresh._bundled)

    def test_explicit_codex_override_is_preserved(self):
        module=core.studio.openai_oauth
        spec=importlib.util.spec_from_file_location('portable_codex_override',module.__file__);fresh=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,{'AGENTIC_STUDIO_CODEX_BINARY':'/custom/official-codex'}):spec.loader.exec_module(fresh)
        self.assertEqual(fresh.BINARY,Path('/custom/official-codex'))
