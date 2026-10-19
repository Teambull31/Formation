import json
import re
import sys
from datetime import datetime
from pathlib import Path

KIT = Path(__file__).resolve().parents[2] / "content" / "modules" / "auto1" / "kit"
sys.path.insert(0, str(KIT))

from mail_source import MAX_BODY, JsonMailSource, MboxMailSource, html_to_text  # noqa: E402

FIX = KIT / "fixtures"


def test_json_source_returns_mails_sorted_newest_first():
    mails = JsonMailSource(FIX / "mails.json").fetch()
    assert len(mails) == 12
    assert [m.received for m in mails] == sorted((m.received for m in mails), reverse=True)


def test_since_filters_and_limit_caps():
    src = JsonMailSource(FIX / "mails.json")
    since = datetime.fromisoformat(src.fetch()[4].received.replace("Z", "+00:00"))
    assert len(src.fetch(since=since)) == 5
    assert len(src.fetch(since=since.replace(tzinfo=None))) == 5  # naive = UTC
    assert len(src.fetch(limit=3)) == 3


def test_mbox_source_decodes_headers_and_charsets():
    mails = MboxMailSource(FIX / "inbox.mbox").fetch()
    assert len(mails) == 12
    text = "\n".join(m.subject + m.body for m in mails)
    assert "=?" not in text and "<html" not in text.lower() and "<p>" not in text
    assert any("é" in m.subject for m in mails)  # RFC 2047 subject decoded
    assert any("é" in m.body or "à" in m.body for m in mails)  # latin-1 body decoded


def test_missing_headers_do_not_crash(tmp_path):
    p = tmp_path / "x.mbox"
    p.write_text("From a Mon Jan  1 00:00:00 2024\nSubject: Salut\n\ncorps\n", encoding="utf-8")
    (m,) = MboxMailSource(p).fetch()
    assert (m.id, m.sender, m.subject, m.received) == (
        "mbox-0", "inconnu@example.test", "Salut", "1970-01-01T00:00:00Z")
    assert m.body.strip() == "corps"


def test_empty_mbox_and_empty_json(tmp_path):
    (tmp_path / "e.mbox").write_bytes(b"")
    (tmp_path / "e.json").write_text("[]")
    assert MboxMailSource(tmp_path / "e.mbox").fetch() == []
    assert JsonMailSource(tmp_path / "e.json").fetch() == []


def test_huge_body_is_truncated_to_max_body(tmp_path):
    p = tmp_path / "h.json"
    row = {"id": "x", "sender": "a@example.test", "subject": "s",
           "received": "2024-01-01T00:00:00Z", "body": "a" * (MAX_BODY * 3)}
    p.write_text(json.dumps([row]))
    body = JsonMailSource(p).fetch()[0].body
    assert len(body) <= MAX_BODY and body.endswith("[tronqué]")


def test_html_to_text_strips_tags_scripts_and_entities():
    html = "<style>x{}</style><p>Caf&eacute; &amp; <b>thé</b></p><script>evil()</script>"
    assert html_to_text(html).strip() == "Café & thé"


def test_fixtures_only_use_example_test_addresses():
    found = set()
    for f in FIX.iterdir():
        found |= set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", f.read_text(encoding="utf-8", errors="replace")))
    assert found and all(a.endswith("@example.test") for a in found), found


def test_hostile_fixture_has_four_mails():
    assert len(JsonMailSource(FIX / "hostile.json").fetch()) == 4
