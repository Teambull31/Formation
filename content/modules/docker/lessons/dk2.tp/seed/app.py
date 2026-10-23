"""Mini serveur HTTP de démonstration (port 8000)."""
from http.server import BaseHTTPRequestHandler, HTTPServer


class Hello(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bonjour depuis un conteneur\n")


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), Hello).serve_forever()
