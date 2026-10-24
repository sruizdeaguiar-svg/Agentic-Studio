"""Bound connection count and slow clients, including TLS handshakes before HTTP."""
import threading
from http.server import ThreadingHTTPServer

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, *args, tls=None, **kwargs):
        self.tls = tls
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request); return
        try: super().process_request(request, address)
        except BaseException:
            self.slots.release(); raise

    def process_request_thread(self, request, address):
        try:
            request.settimeout(15)
            if self.tls:
                # The accept loop remains responsive while a client stalls TLS.
                request = self.tls.wrap_socket(request, server_side=True)
            super().process_request_thread(request, address)
        except (OSError, ValueError):
            self.shutdown_request(request)
        finally: self.slots.release()
