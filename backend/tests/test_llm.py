from pathlib import Path

import httpx
import pytest

from app.content import load_module
from app.llm import explain_error, hint

DEMO = Path(__file__).parent / "fixtures" / "demo_module"


@pytest.fixture
def lesson_items():
    m = load_module(DEMO)
    tp = next(l.tp for l in m.lessons if l.tp and l.tp.id == "t1")
    q = next(q for l in m.lessons for q in l.qcm if q.id == "q1")
    return tp, q


@pytest.fixture
def tp(lesson_items):
    return lesson_items[0]


@pytest.fixture
def q(lesson_items):
    return lesson_items[1]


def fake(content):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": content}}

    return lambda *a, **k: R()


def raises(exc):
    def post(*a, **k):
        raise exc("boom")

    return post


def test_hint_uses_ollama_answer(tp):
    assert hint(tp, 1, "err", post=fake("Pense au daemon")) == "Pense au daemon"


def test_hint_strips_think_block(tp):
    assert hint(tp, 1, "err", post=fake("<think>hmm\n</think>\n Pense au daemon ")) == "Pense au daemon"


def test_hint_request_shape(tp):
    seen = {}

    def post(url, **kw):
        seen.update(url=url, **kw)
        return fake("ok")()

    hint(tp, 1, "x" * 5000, post=post)
    content = seen["json"]["messages"][-1]["content"]
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["timeout"] == 8
    assert seen["json"]["model"] == "qwen3:14b"
    assert seen["json"]["stream"] is False and seen["json"]["think"] is False
    assert "x" * 2000 in content and "x" * 2001 not in content
    assert tp.instructions_md in content


@pytest.mark.parametrize("exc", [httpx.ConnectError, httpx.ReadTimeout])
def test_hint_falls_back_on_error(tp, exc):
    assert hint(tp, 1, "err", post=raises(exc)) == tp.hints[0]


def test_hint_falls_back_on_http_error(tp):
    class R:
        def raise_for_status(self):
            raise httpx.HTTPStatusError("x", request=None, response=None)

    assert hint(tp, 2, "", post=lambda *a, **k: R()) == tp.hints[1]


def test_hint_falls_back_on_empty_reply(tp):
    assert hint(tp, 1, "err", post=fake("   ")) == tp.hints[0]
    assert hint(tp, 1, "err", post=fake("<think>x</think>")) == tp.hints[0]


def test_hint_falls_back_on_bad_json(tp):
    assert hint(tp, 1, "", post=lambda *a, **k: object()) == tp.hints[0]


def test_level_beyond_hints_returns_last(tp):
    assert hint(tp, 99, "", post=raises(httpx.ConnectError)) == tp.hints[-1]


def test_level_below_one_is_one(tp):
    assert hint(tp, 0, "", post=raises(httpx.ConnectError)) == tp.hints[0]


def test_explain_error_uses_ollama(q):
    assert explain_error(q, 0, post=fake("Parce que.")) == "Parce que."


def test_explain_error_fallback(q):
    assert explain_error(q, 0, post=raises(httpx.ConnectError)) == q.explain
