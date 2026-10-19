"""A fake Gmail API (GET only, bearer required), for tests and lessons."""
import base64
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from _server import Handle, JsonHandler

MAILS = sorted(json.loads((Path(__file__).parent / "fixtures" / "mails.json").read_text(encoding="utf-8")),
               key=lambda m: m["received"], reverse=True)


def _enc(text):
    return {"data": base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")}


def gmail_message(m, i):
    if i % 2:  # multipart: html first, plain second; the connector must prefer plain
        payload = {"mimeType": "multipart/alternative", "parts": [
            {"mimeType": "text/html", "body": _enc(f"<p>HTML {m['id']}</p><script>x()</script>")},
            {"mimeType": "text/plain", "body": _enc(m["body"])}]}
    else:
        payload = {"mimeType": "text/plain", "body": _enc(m["body"])}
    ms = int(datetime.fromisoformat(m["received"].replace("Z", "+00:00")).timestamp() * 1000)
    payload["headers"] = [{"name": "From", "value": m["sender"]}, {"name": "Subject", "value": m["subject"]}]
    return {"id": m["id"], "internalDate": str(ms), "payload": payload}


class GmailHandler(JsonHandler):
    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if not (auth.startswith("Bearer ") and len(auth) > 7):
            return self.send_json(401, {"error": "unauthenticated"})
        path = urlparse(self.path).path
        if path == "/gmail/v1/users/me/messages":
            return self.send_json(200, {"messages": [{"id": m["id"]} for m in MAILS]})
        for i, m in enumerate(MAILS):
            if path == f"/gmail/v1/users/me/messages/{m['id']}":
                return self.send_json(200, gmail_message(m, i))
        self.send_json(404, {"error": "not found"})

    def _refuse(self):
        self.send_json(405, {"error": "read-only"})

    do_POST = do_PUT = do_PATCH = do_DELETE = _refuse


def serve(port=0):
    return Handle(GmailHandler, port)
