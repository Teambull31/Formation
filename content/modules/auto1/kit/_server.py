"""Tiny helper shared by the two simulators: run an http.server in a thread."""

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 1_000_000  # never read more than 1 MB from a client


class Handle:
    """What `serve()` returns: `.port`, `.address`, `.shutdown()`, usable in a `with`."""

    def __init__(self, handler_class, port, **state):
        # 127.0.0.1 only: these fake servers must never be reachable from the network.
        self._server = ThreadingHTTPServer(("127.0.0.1", port), handler_class)
        self._server.daemon_threads = True
        self._initial = copy.deepcopy(state)
        self.state = self._server.state = copy.deepcopy(state)  # shared with the handlers
        self.lock = self._server.lock = threading.Lock()
        self.address = self._server.server_address
        self.port = self.address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def set_mode(self, mode):
        self.state["mode"] = mode

    def reset(self):
        """Back to the initial state (counters, task list...)."""
        with self.lock:
            self.state.clear()
            self.state.update(copy.deepcopy(self._initial))

    def shutdown(self):
        self._server.shutdown()
        self._server.server_close()  # releases the port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.shutdown()


class JsonHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test/lesson output quiet
        pass

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        """The request body parsed as JSON, or None if it is missing/too big/invalid."""
        try:
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= MAX_BODY:
                return None
            return json.loads(self.rfile.read(n))
        except (ValueError, UnicodeDecodeError):
            return None
