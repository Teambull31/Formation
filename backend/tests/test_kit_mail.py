import json
import re
import sys
import time
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


# --- fix round 1: robustness ---
def test_mbox_decoding_matches_json_exactly():
    ref = {f"{m.id}@example.test": m for m in JsonMailSource(FIX / "mails.json").fetch()}
    got = {m.id: m for m in MboxMailSource(FIX / "inbox.mbox").fetch()}
    assert len(got) == 12
    for mid, m in ref.items():
        if mid in got:
            assert got[mid].subject == m.subject and got[mid].body.strip() == m.body.strip()
    assert got["m002@example.test"].subject == "Facture n° 2026-0412 à régler avant le 15"
    assert got["m002@example.test"].body.startswith("Bonjour,\n\nVeuillez")


def test_bad_charsets_never_raise(tmp_path):
    p = tmp_path / "b.mbox"
    p.write_bytes(b"From a Mon Jan  1 00:00:00 2024\nSubject: =?bogus?q?a?= b\n"
                  b"Content-Type: text/plain; charset=bogus\nContent-Transfer-Encoding: 8bit\n\ncaf\xc3\xa9\n")
    (m,) = MboxMailSource(p).fetch()
    assert "b" in m.subject and "café" in m.body


def test_bad_charset_in_multipart_part(tmp_path):
    p = tmp_path / "c.mbox"
    p.write_bytes(b"From a Mon Jan  1 00:00:00 2024\nSubject: x\nContent-Type: multipart/mixed; boundary=B\n\n"
                  b"--B\nContent-Type: text/plain; charset=bogus\n\nsalut\n--B--\n")
    assert "salut" in MboxMailSource(p).fetch()[0].body


def test_json_missing_or_garbage_file_is_empty(tmp_path):
    assert JsonMailSource(tmp_path / "nope.json").fetch() == []
    for text in ("", "{not json", '{"a": 1}', "[1, 2]"):
        (tmp_path / "g.json").write_text(text)
        assert JsonMailSource(tmp_path / "g.json").fetch() == []


def test_json_rows_use_fallbacks(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([{"id": "a"}, {"id": "b", "body": None, "sender": 3, "received": "pas une date"}]))
    mails = JsonMailSource(p).fetch()
    assert len(mails) == 2
    for m in mails:
        assert (m.sender, m.subject, m.received, m.body) == (
            "inconnu@example.test", "(sans objet)", "1970-01-01T00:00:00Z", "")


def test_json_received_offsets_are_converted_to_utc(tmp_path):
    p = tmp_path / "o.json"
    rows = [{"id": "late", "received": "2026-03-01T10:00:00+02:00"},  # 08:00Z
            {"id": "early", "received": "2026-03-01T09:00:00Z"},
            {"id": "naive", "received": "2026-03-01T07:00:00"}]
    p.write_text(json.dumps(rows))
    src = JsonMailSource(p)
    assert [(m.id, m.received) for m in src.fetch()] == [
        ("early", "2026-03-01T09:00:00Z"), ("late", "2026-03-01T08:00:00Z"), ("naive", "2026-03-01T07:00:00Z")]
    since = datetime.fromisoformat("2026-03-01T08:00:00+00:00")
    assert [m.id for m in src.fetch(since=since)] == ["early", "late"]


def test_missing_mbox_is_empty_and_not_created(tmp_path):
    p = tmp_path / "absent.mbox"
    assert MboxMailSource(p).fetch() == []
    assert not p.exists()


def test_hostile_ids():
    ids = [m.id for m in JsonMailSource(FIX / "hostile.json").fetch()]
    assert sorted(ids) == ["h001", "h002", "h003", "h004"]


def test_html_to_text_is_fast_on_unclosed_script():
    start = time.perf_counter()
    out = html_to_text("<script" * 300_000)  # 2.1 MB
    assert time.perf_counter() - start < 2 and len(out) <= MAX_BODY * 4


def test_html_to_text_script_content_never_survives():
    assert html_to_text("<script>alert(1)</script>ok") == "ok"
    out = html_to_text("a<scr<script>x</script>ipt>alert(1)</script>b")
    assert "<script" not in out.lower()
