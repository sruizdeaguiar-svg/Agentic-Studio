"""Adversarial regression tests using isolated, fictitious project files."""
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import test_studio as core
import secure_files
from bounded_http import Server

class FileSecurityTests(unittest.TestCase):
    def test_links_special_files_and_parent_traversal_fail_closed(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as outside:
            root=Path(work);secret=Path(outside)/'secret';secret.write_text('OUTSIDE')
            (root/'symlink').symlink_to(secret)
            os.link(secret,root/'hardlink');os.mkfifo(root/'fifo')
            for name in ('symlink','hardlink','fifo','../secret'):
                with self.assertRaises(ValueError):secure_files.read(root,name)
                with self.assertRaises(ValueError):secure_files.write(root,name,b'BAD',lambda _:None)
            self.assertEqual(secret.read_text(),'OUTSIDE')

    def test_parent_swap_after_validation_cannot_escape(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as outside:
            root=Path(work);(root/'child').mkdir();(Path(outside)/'secret').write_text('OUTSIDE')
            (root/'child').rename(root/'old-child');(root/'child').symlink_to(outside)
            for operation in (lambda:secure_files.read(root,'child/secret'),lambda:secure_files.write(root,'child/secret',b'BAD',lambda _:None)):
                with self.assertRaises(ValueError):operation()
            self.assertEqual((Path(outside)/'secret').read_text(),'OUTSIDE')

    def test_late_leaf_swap_does_not_modify_link_target(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as outside:
            root=Path(work);leaf=root/'note';leaf.write_text('BEFORE')
            secret=Path(outside)/'secret';secret.write_text('OUTSIDE')
            def swap(_):leaf.unlink();leaf.symlink_to(secret)
            secure_files.write(root,'note',b'AFTER',swap)
            self.assertEqual(secret.read_text(),'OUTSIDE')
            self.assertFalse(leaf.is_symlink());self.assertEqual(leaf.read_text(),'AFTER')

    def test_bounded_read_and_missing_target_have_no_side_effects(self):
        with tempfile.TemporaryDirectory() as work:
            root=Path(work)
            self.assertIsNone(secure_files.read(root,'new/note',missing=True))
            self.assertFalse((root/'new').exists())
            with (root/'huge').open('wb') as f:f.truncate(secure_files.LIMIT+1)
            with self.assertRaises(ValueError):secure_files.read(root,'huge')

class DatabaseSecurityTests(unittest.TestCase):
    def test_private_database_permissions_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as outside:
            root=Path(work);secret=Path(outside)/'secret';secret.write_text('OUTSIDE')
            with patch.object(core.studio,'DATA',root):
                with core.studio.connect() as connection:connection.execute('CREATE TABLE fixture(value TEXT)')
                self.assertEqual((root/'studio.sqlite3').stat().st_mode & 0o777,0o600)
                (root/'studio.sqlite3').unlink();(root/'studio.sqlite3').symlink_to(secret)
                with self.assertRaises((ValueError,OSError)):
                    with core.studio.connect():pass
            self.assertEqual(secret.read_text(),'OUTSIDE')

class HTTPBoundaryTests(core.StudioTests):
    # Run the normal backend checks as well, with security-specific requests below.
    def test_bootstrap_rejects_foreign_host_and_origin(self):
        for headers in ({'Host':'evil.example'},{'Origin':'https://evil.example'}):
            request=urllib.request.Request(self.base+'/?token='+core.studio.TOKEN,headers=headers)
            with urllib.request.urlopen(request,timeout=5) as response:
                self.assertNotIn('studio_auth=',response.headers.get('Set-Cookie',''))

class BoundedServerTests(unittest.TestCase):
    def test_tls_handshake_runs_in_worker_and_does_not_block_accept(self):
        import threading
        class SlowTLS:
            entered=threading.Event();release=threading.Event()
            def wrap_socket(self,sock,server_side):
                self.entered.set();self.release.wait(3)
                raise OSError('Fictitious stalled TLS handshake')
        tls=SlowTLS();server=Server(('127.0.0.1',0),core.FixtureEngine,tls=tls)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        clients=[]
        try:
            clients.append(socket.create_connection(server.server_address,timeout=2))
            self.assertTrue(tls.entered.wait(2))
            clients.append(socket.create_connection(server.server_address,timeout=2))
            # Shutdown must complete even though both worker handshakes are stalled.
            before=time.monotonic();server.shutdown()
            self.assertLess(time.monotonic()-before,1.5)
        finally:
            tls.release.set()
            for client in clients:client.close()
            server.server_close()

    def test_connection_capacity_is_bounded(self):
        server=Server(('127.0.0.1',0),core.FixtureEngine)
        try:
            for _ in range(32):self.assertTrue(server.slots.acquire(blocking=False))
            self.assertFalse(server.slots.acquire(blocking=False))
            for _ in range(32):server.slots.release()
        finally:server.server_close()

for name in dir(core.StudioTests):
    if name.startswith("test_") and name not in HTTPBoundaryTests.__dict__:setattr(HTTPBoundaryTests,name,None)
