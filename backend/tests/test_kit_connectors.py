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
    page = {"value": [], "@odata.nextLink": "http://evil.example.test/steal"}
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
