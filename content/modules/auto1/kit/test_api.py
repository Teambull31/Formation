"""A fake REST API to practise HTTP nodes against.

    GET  /tasks   the 3 tasks
    POST /tasks   add one (JSON object required, else 400) -> 201
    GET  /flaky   503, 503, 200, 503, 503, 200... (to learn retries)
"""

from _server import Handle, JsonHandler

TASKS = [
    {"id": 1, "title": "Écrire le rapport", "done": False},
    {"id": 2, "title": "Appeler le client", "done": True},
    {"id": 3, "title": "Envoyer la facture", "done": False},
]


class ApiHandler(JsonHandler):
    def do_GET(self):
        state = self.server.state
        if self.path == "/tasks":
            self.send_json(200, state["tasks"])
        elif self.path == "/flaky":
            with self.server.lock:
                state["calls"] += 1
                ok = state["calls"] % 3 == 0  # every third call works
            self.send_json(200, {"ok": True}) if ok else self.send_json(503, {"error": "try again"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/tasks":
            return self.send_json(404, {"error": "not found"})
        data = self.read_json()
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "JSON object required"})
        with self.server.lock:
            tasks = self.server.state["tasks"]
            task = {"id": len(tasks) + 1, **data}
            tasks.append(task)
        self.send_json(201, task)


def serve(port=0):
    return Handle(ApiHandler, port, tasks=TASKS, calls=0)
