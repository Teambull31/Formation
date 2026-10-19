"""A fake Microsoft Graph, read-only like the real scope.

    with mock_graph.serve(port=0, pages=2) as srv:
        OutlookGraphSource("x", base_url=f"http://127.0.0.1:{srv.port}/v1.0", auth=lambda: "t")
        srv.requests  # [(method, path, authorised), ...] every request received
"""
import html
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from _server import Handle, JsonHandler

MAILS = json.loads((Path(__file__).parent / "fixtures" / "mails.json").read_text(encoding="utf-8"))


def graph_message(m, as_html):
    body = {"contentType": "text", "content": m["body"]}
    if as_html:  # hostile-looking HTML on purpose: the connector must strip it
        body = {"contentType": "html", "content": (
            "<html><head><style>p{color:red}</style></head><body><p>"
            + html.escape(m["body"]).replace("\n", "<br>") + "</p><script>alert('x')</script></body></html>")}
    return {"id": m["id"], "subject": m["subject"], "receivedDateTime": m["received"],
            "from": {"emailAddress": {"address": m["sender"]}}, "body": body}


class GraphHandler(JsonHandler):
    def _record(self):
        auth = self.headers.get("Authorization", "")
        ok = auth.startswith("Bearer ") and len(auth) > 7
        self.server.state["requests"].append((self.command, urlparse(self.path).path, ok))
        return ok

    def do_GET(self):
        if not self._record():
            return self.send_json(401, {"error": {"code": "InvalidAuthenticationToken"}})
        url = urlparse(self.path)
        if url.path != "/v1.0/me/messages":
            return self.send_json(404, {"error": {"code": "NotFound"}})
        q = parse_qs(url.query)
        mails = sorted(MAILS, key=lambda m: m["received"], reverse=True)
        size = -(-len(mails) // self.server.state["pages"])  # ceil
        size = min(size, int(q.get("$top", [size])[0]))
        skip = int(q.get("$skip", [0])[0])
        out = {"value": [graph_message(m, (skip + i) % 2 == 1) for i, m in enumerate(mails[skip:skip + size])]}
        if skip + size < len(mails):
            out["@odata.nextLink"] = f"http://{self.headers.get('Host')}/v1.0/me/messages?$skip={skip + size}&$top={size}"
        self.send_json(200, out)

    def _refuse(self):
        self._record()
        self.send_json(405, {"error": {"code": "MethodNotAllowed"}})

    do_POST = do_PUT = do_PATCH = do_DELETE = _refuse


def serve(port=0, pages=2):
    h = Handle(GraphHandler, port, pages=pages, requests=[])
    h.requests = h.state["requests"]
    return h
