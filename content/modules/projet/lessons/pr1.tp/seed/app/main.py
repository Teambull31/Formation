"""API de commandes minimale, bibliothèque standard seule : GET /healthz et POST /total sur le port 8000."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def total(items: list[dict]) -> float:
    """Montant d'une commande : somme des prix × quantités, arrondie au centime."""
    return round(sum(float(i["price"]) * int(i["qty"]) for i in items), 2)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "version": os.environ.get("APP_VERSION", "dev")})
        else:
            self._send(404, {"error": "introuvable"})

    def do_POST(self):
        if self.path != "/total":
            return self._send(404, {"error": "introuvable"})
        try:
            items = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            self._send(200, {"total": total(items)})
        except (ValueError, KeyError, TypeError):
            self._send(400, {"error": "commande invalide"})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
