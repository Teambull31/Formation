"""A fake Ollama server, so lessons run without a GPU (and can fail on purpose).

    with mock_ollama.serve(port=0, mode="ok") as srv:   # port 0 = any free port
        srv.port  # where to point OLLAMA_URL
        srv.set_mode("slow")  # switch behaviour while running

Modes:
  ok    short deterministic French summary
  slow  answers after 5 s (longer than any sane client timeout)
  down  accepts the connection, then closes it without answering
  obey  returns the last mail of the prompt verbatim: a model that obeys
        whatever order is hidden in the mail (prompt injection demo)
"""

import time

from _server import Handle, JsonHandler

MARKER = "--- MAIL ---"
SLOW_SECONDS = 5


def fake_answer(prompt, mode):
    if mode == "obey":
        if MARKER in prompt:
            return prompt.rsplit(MARKER, 1)[1].strip()
        return prompt.strip().split("\n\n")[-1]
    start = " ".join(prompt.split()[:3])
    return f"Résumé : mail de {len(prompt)} caractères commençant par « {start} »."


class OllamaHandler(JsonHandler):
    def do_POST(self):
        mode = self.server.state["mode"]
        if mode == "down":
            self.close_connection = True  # no response at all
            return
        data = self.read_json()
        if self.path != "/api/generate" or not isinstance(data, dict) or not isinstance(data.get("prompt"), str):
            return self.send_json(400, {"error": "bad request"})
        if mode == "slow":
            time.sleep(SLOW_SECONDS)
        self.send_json(200, {"model": data.get("model"), "response": fake_answer(data["prompt"], mode), "done": True})


def serve(port=11500, mode="ok"):
    return Handle(OllamaHandler, port, mode=mode)
