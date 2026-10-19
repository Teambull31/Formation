import base64
import logging
import os
import stat
import sys
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

import pytest

KIT = Path(__file__).resolve().parents[2] / "content" / "modules" / "auto1" / "kit"
sys.path.insert(0, str(KIT))

import mock_gmail  # noqa: E402
import mock_graph  # noqa: E402
from gmail_api import GmailSource  # noqa: E402
from imap_source import ImapSource  # noqa: E402
from mail_source import ConnectorError, JsonMailSource  # noqa: E402
from outlook_graph import OutlookGraphSource  # noqa: E402

SECRET = "tok-SECRET-123"


def outlook(srv, **kw):
    return OutlookGraphSource("cid", token_path=kw.pop("token_path", "unused.json"),
                              base_url=f"http://127.0.0.1:{srv.port}/v1.0", auth=lambda: SECRET, **kw)


def test_outlook_source_reads_all_pages_from_mock():
    with mock_graph.serve(port=0, pages=3) as srv:
        mails = outlook(srv).fetch()
    assert len(mails) == 12
    assert len(srv.requests) == 3
    assert {m.id for m in mails} == {m.id for m in JsonMailSource(KIT / "fixtures" / "mails.json").fetch()}


def test_outlook_limit_stops_following_pages():
    with mock_graph.serve(port=0, pages=4) as srv:
        assert len(outlook(srv).fetch(limit=5)) == 5


def test_outlook_source_sends_bearer_token_and_only_get():
    with mock_graph.serve(port=0) as srv:
        outlook(srv).fetch()
    assert srv.requests and all(m == "GET" and ok for m, _, ok in srv.requests)
    assert not [n for n in dir(OutlookGraphSource) if n in ("send", "post", "delete", "reply")]


def test_post_is_refused_by_mock():
    with mock_graph.serve(port=0) as srv:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/v1.0/me/messages", data=b"{}", method="POST",
                                     headers={"Authorization": "Bearer x"})
        with pytest.raises(HTTPError) as e:
            urllib.request.urlopen(req)
    assert e.value.code == 405


def test_outlook_html_body_becomes_plain_text():
    with mock_graph.serve(port=0) as srv:
        mails = outlook(srv).fetch()
    assert all("<" not in m.body and "alert" not in m.body and "color:red" not in m.body for m in mails)
    assert any("Horizon" in m.body for m in mails)


def test_nextlink_to_other_host_is_refused(monkeypatch):
    import outlook_graph
    page = {"value": [{"id": "1"}], "@odata.nextLink": "http://evil.example.test/steal"}
    seen = []
    real = outlook_graph.get_json

    def fake(url, token, base):
        seen.append(url)
        return page if len(seen) == 1 else real(url, token, base)

    monkeypatch.setattr(outlook_graph, "get_json", fake)
    with mock_graph.serve(port=0) as srv:
        with pytest.raises(ConnectorError) as e:
            outlook(srv).fetch()
    assert SECRET not in str(e.value) and len(seen) == 2


def test_token_file_is_created_0600(tmp_path):
    from _http import write_private
    p = tmp_path / "tok.json"
    write_private(p, "{}")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    p.chmod(0o644)
    write_private(p, "{}")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


def test_missing_msal_gives_actionable_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "msal", None)
    with pytest.raises(RuntimeError) as e:
        OutlookGraphSource("cid", token_path="x.json").fetch()
    assert "pip install msal" in str(e.value) and "auth=" in str(e.value)


def test_401_raises_clear_error_not_traceback_with_token():
    with mock_graph.serve(port=0) as srv:
        src = OutlookGraphSource("cid", token_path="x", base_url=f"http://127.0.0.1:{srv.port}/v1.0", auth=lambda: "")
        with pytest.raises(ConnectorError) as e:
            src.fetch()
    assert "401" in str(e.value)
    with mock_graph.serve(port=0) as srv:
        src = OutlookGraphSource("cid", token_path="x", base_url=f"http://127.0.0.1:{srv.port}/v1.0/nope", auth=lambda: SECRET)
        with pytest.raises(ConnectorError) as e:
            src.fetch()
    assert SECRET not in str(e.value) and SECRET not in repr(e.value.__cause__)


def test_gmail_source_decodes_base64url_bodies():
    with mock_gmail.serve() as srv:
        src = GmailSource("c.json", "t.json", base_url=f"http://127.0.0.1:{srv.port}/gmail/v1", auth=lambda: SECRET)
        mails = src.fetch()
    ref = {m.id: m for m in JsonMailSource(KIT / "fixtures" / "mails.json").fetch()}
    assert len(mails) == 12
    assert all(m.body == ref[m.id].body for m in mails)  # multipart ones prefer text/plain
    assert all(m.received == ref[m.id].received for m in mails)


def test_gmail_html_only_is_converted():
    from gmail_api import _body
    data = base64.urlsafe_b64encode(b"<p>Salut</p><script>x()</script>").decode().rstrip("=")
    assert _body({"mimeType": "text/html", "body": {"data": data}}) == "Salut"


def test_gmail_missing_google_libs_gives_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib", None)
    with pytest.raises(RuntimeError) as e:
        GmailSource("c.json", "t.json").fetch()
    assert "pip install" in str(e.value) and "auth=" in str(e.value)


def test_gmail_requires_bearer():
    with mock_gmail.serve() as srv:
        src = GmailSource("c", "t", base_url=f"http://127.0.0.1:{srv.port}/gmail/v1", auth=lambda: "")
        with pytest.raises(ConnectorError, match="401"):
            src.fetch()


class FakeImap:
    def __init__(self, host, port):
        self.calls = []

    def login(self, user, pw):
        self.calls.append(("login", pw))

    def select(self, folder, readonly=False):
        assert readonly
        return "OK", [b"2"]

    def search(self, charset, crit):
        return "OK", [b"1 2"]

    def fetch(self, n, what):
        raw = (b"From: a@example.test\r\nSubject: Sujet " + n + b"\r\nDate: Mon, 02 Mar 2026 08:15:00 +0000\r\n"
               b"Message-ID: <i" + n + b"@example.test>\r\n\r\nCorps " + n + b"\r\n")
        return "OK", [(b"1 (RFC822 {10}", raw), b")"]

    def logout(self):
        pass


def test_imap_via_fake_connection(monkeypatch):
    monkeypatch.setenv("IMAP_PW", "pw")
    mails = ImapSource("h.example.test", "u@example.test", "IMAP_PW", connection_factory=FakeImap).fetch(limit=5)
    assert [m.subject for m in mails] == ["Sujet 1", "Sujet 2"] or {m.subject for m in mails} == {"Sujet 1", "Sujet 2"}
    assert mails[0].sender == "a@example.test" and mails[0].body.startswith("Corps")


def test_imap_password_env_missing_is_clear(monkeypatch):
    monkeypatch.delenv("IMAP_PW", raising=False)
    with pytest.raises(ConnectorError, match="IMAP_PW"):
        ImapSource("h", "u@example.test", "IMAP_PW", connection_factory=FakeImap).fetch()


def test_connectors_never_log_mail_bodies(caplog):
    caplog.set_level(logging.DEBUG)
    with mock_graph.serve(port=0) as srv, mock_gmail.serve() as gsrv:
        outlook(srv).fetch()
        GmailSource("c", "t", base_url=f"http://127.0.0.1:{gsrv.port}/gmail/v1", auth=lambda: SECRET).fetch()
    text = caplog.text
    assert SECRET not in text and "Horizon" not in text and "Facture" not in text


# ---- fix round 1 ----
import imaplib  # noqa: E402

import _http  # noqa: E402
import gmail_api  # noqa: E402
import outlook_graph  # noqa: E402


def test_imap_default_connection_verifies_certs(monkeypatch):
    seen = {}

    class Spy(FakeImap):
        def __init__(self, host, port, **kw):
            seen.update(kw)
            super().__init__(host, port)

    monkeypatch.setenv("IMAP_PW", "pw")
    monkeypatch.setattr(imaplib, "IMAP4_SSL", Spy)
    ImapSource("h", "u@example.test", "IMAP_PW").fetch()
    import ssl
    assert seen["ssl_context"].verify_mode == ssl.CERT_REQUIRED and seen["timeout"] == 30


def test_imap_logout_on_error_and_limit_zero_and_bad_search(monkeypatch):
    monkeypatch.setenv("IMAP_PW", "pw")
    state = {"logout": 0, "fetch": 0}

    class Bad(FakeImap):
        def search(self, charset, crit):
            return "NO", [None]

        def logout(self):
            state["logout"] += 1

    with pytest.raises(ConnectorError):
        ImapSource("h", "u@example.test", "IMAP_PW", connection_factory=Bad).fetch()
    assert state["logout"] == 1

    class Count(FakeImap):
        def fetch(self, n, what):
            state["fetch"] += 1
            return super().fetch(n, what)

    assert ImapSource("h", "u@example.test", "IMAP_PW", connection_factory=Count).fetch(limit=0) == []
    assert state["fetch"] == 0

    class NoneData(FakeImap):
        def search(self, charset, crit):
            return "OK", [None]

    with pytest.raises(ConnectorError):
        ImapSource("h", "u@example.test", "IMAP_PW", connection_factory=NoneData).fetch()


def test_outlook_hostile_nextlink_loops_end_quickly(monkeypatch):
    calls = []
    row = {"id": "x", "subject": "s", "body": {"contentType": "text", "content": "b"}}
    src = OutlookGraphSource("c", base_url="http://h.example.test/v1.0", auth=lambda: "t")

    def same(url, token, base):
        calls.append(url)
        return {"value": [row], "@odata.nextLink": "http://h.example.test/v1.0/same"}

    monkeypatch.setattr(outlook_graph, "get_json", same)
    src.fetch(limit=200)
    assert len(calls) <= 2

    calls.clear()

    def endless(url, token, base):
        calls.append(url)
        return {"value": [], "@odata.nextLink": f"http://h.example.test/v1.0/p{len(calls)}"}

    monkeypatch.setattr(outlook_graph, "get_json", endless)
    src.fetch(limit=200)
    assert len(calls) <= 2

    calls.clear()

    def distinct(url, token, base):
        calls.append(url)
        return {"value": [dict(row, id=str(len(calls)))], "@odata.nextLink": f"http://h.example.test/v1.0/p{len(calls)}"}

    monkeypatch.setattr(outlook_graph, "get_json", distinct)
    src.fetch(limit=200)
    assert len(calls) <= 200 // 50 + 2


def test_default_token_path_is_under_home_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = OutlookGraphSource("c").token_path
    assert p == tmp_path / ".config" / "formation-auto1" / "graph_token.json"
    assert GmailSource("cred.json").token_path == tmp_path / ".config" / "formation-auto1" / "gmail_token.json"
    _http.write_private(p, "{}")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(p.parent).st_mode) == 0o700


def test_write_private_refuses_symlink(tmp_path):
    target = tmp_path / "t"
    target.write_text("keep")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ConnectorError):
        _http.write_private(link, "{}")
    assert target.read_text() == "keep"


def test_gitignore_covers_tokens():
    text = (Path(__file__).resolve().parents[2] / ".gitignore").read_text()
    assert "*token*.json" in text and "credentials*.json" in text


def test_outlook_malformed_json_never_tracebacks(monkeypatch):
    src = OutlookGraphSource("c", base_url="http://h.example.test/v1.0", auth=lambda: "t")
    monkeypatch.setattr(outlook_graph, "get_json", lambda *a: ["not", "a", "dict"])
    with pytest.raises(ConnectorError, match="réponse invalide"):
        src.fetch()
    odd = {"value": [{"id": "1", "subject": None, "from": "x", "body": "str", "receivedDateTime": 5},
                     {"id": "2", "from": {"emailAddress": "x"}, "body": None}, "junk"]}
    monkeypatch.setattr(outlook_graph, "get_json", lambda *a: odd)
    mails = src.fetch()
    assert len(mails) == 2 and mails[0].sender.endswith("@example.test")


def test_get_json_non_object_is_invalid(monkeypatch):
    monkeypatch.setattr(_http._OPENER, "open", lambda *a, **k: __import__("io").BytesIO(b"[1]"))
    with pytest.raises(ConnectorError, match="réponse invalide"):
        _http.get_json("http://h.example.test/x", "t", "http://h.example.test")


def test_gmail_malformed_responses(monkeypatch):
    src = GmailSource("c", "t", base_url="http://h.example.test/g", auth=lambda: "t")
    answers = iter([{"messages": [{}, "junk", {"id": 5}, {"id": "a"}]},
                    {"id": "a", "internalDate": "9" * 40, "payload": {"headers": ["x", {"name": "From"}]}}])
    monkeypatch.setattr(gmail_api, "get_json", lambda *a: next(answers))
    mails = src.fetch()
    assert len(mails) == 1 and mails[0].received.startswith("1970")
    monkeypatch.setattr(gmail_api, "get_json", lambda *a: {"messages": "x"})
    assert src.fetch() == []


def test_gmail_quotes_message_ids(monkeypatch):
    urls = []
    answers = iter([{"messages": [{"id": "../x?y"}]}, {"id": "../x?y", "internalDate": "0", "payload": {}}])

    def fake(url, token, base):
        urls.append(url)
        return next(answers)

    monkeypatch.setattr(gmail_api, "get_json", fake)
    GmailSource("c", "t", base_url="http://h.example.test/g", auth=lambda: "t").fetch()
    assert urls[1] == "http://h.example.test/g/users/me/messages/..%2Fx%3Fy?format=full"


def test_gmail_follows_next_page_token_with_bound():
    with mock_gmail.serve(page_size=5) as srv:
        src = GmailSource("c", "t", base_url=f"http://127.0.0.1:{srv.port}/gmail/v1", auth=lambda: SECRET)
        assert len(src.fetch(limit=12)) == 12
        assert len(src.fetch(limit=7)) == 7


def test_gmail_endless_page_token_is_bounded(monkeypatch):
    calls = []

    def fake(url, token, base):
        calls.append(url)
        return {"messages": [{"id": "a"}], "nextPageToken": "same"} if "/messages?" in url else {"id": "a", "payload": {}}

    monkeypatch.setattr(gmail_api, "get_json", fake)
    GmailSource("c", "t", base_url="http://h.example.test/g", auth=lambda: "t").fetch(limit=200)
    assert len([u for u in calls if "/messages?" in u]) <= 200 // 50 + 2
