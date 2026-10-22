import httpx
import pytest
from app.content import Question, Tp
from app.llm import hint, explain_error


class FakeResponse:
    def __init__(self, content: str, status_code: int = 200):
        self._content = content
        self.status_code = status_code

    def json(self):
        return {
            "message": {
                "role": "assistant",
                "content": self._content,
            }
        }


def fake(content: str):
    def _post(*args, **kwargs):
        return FakeResponse(content)
    return _post


def raises(exc_cls):
    def _post(*args, **kwargs):
        raise exc_cls("Simulated error")
    return _post


@pytest.fixture
def sample_tp():
    return Tp(
        id="tp1",
        title="Configuration",
        instructions_md="Créez config.json",
        check="check.sh",
        hints=["Vérifiez le nom du fichier", "Regardez le contenu JSON"],
    )


@pytest.fixture
def sample_question():
    return Question(
        id="q1",
        text="Quelle commande liste les conteneurs ?",
        options=["docker run", "docker ps", "docker build"],
        answer=1,
        explain="docker ps affiche les conteneurs en cours d'exécution.",
    )


def test_hint_uses_ollama_answer(sample_tp):
    res = hint(sample_tp, 1, "err", post=fake("Pense au daemon"))
    assert res == "Pense au daemon"


def test_hint_falls_back_when_ollama_down(sample_tp):
    res = hint(sample_tp, 1, "err", post=raises(httpx.ConnectError))
    assert res == sample_tp.hints[0]


def test_hint_falls_back_on_timeout(sample_tp):
    res = hint(sample_tp, 1, "err", post=raises(httpx.ReadTimeout))
    assert res == sample_tp.hints[0]


def test_hint_falls_back_on_empty_reply(sample_tp):
    res = hint(sample_tp, 1, "err", post=fake("   "))
    assert res == sample_tp.hints[0]


def test_level_beyond_hints_returns_last(sample_tp):
    res = hint(sample_tp, 99, "", post=raises(httpx.ConnectError))
    assert res == sample_tp.hints[-1]


def test_explain_error_fallback(sample_question):
    res = explain_error(sample_question, 0, post=raises(httpx.ConnectError))
    assert res == sample_question.explain


def test_explain_error_uses_ollama_reply(sample_question):
    res = explain_error(sample_question, 0, post=fake("Attention, docker run sert à démarrer."))
    assert res == "Attention, docker run sert à démarrer."
