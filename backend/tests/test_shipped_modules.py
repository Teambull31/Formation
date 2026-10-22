"""Validator for shipped modules (content/modules/*) and bosses (content/boss/*).

Checks are plain helpers returning a list of problems, shared by the parametrized
shipped-content tests and by the self-tests on a synthetic module.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from app.content import ModuleError, Tp, load_module
from app.tp import run_check, seed_workspace

CONTENT = Path(__file__).resolve().parents[2] / "content"
EXPECTED_LESSONS = [f"l{i:02d}" for i in range(1, 13)]
# STRICT: all twelve lessons required (flipped by the last lesson task).
# BOSS_STRICT: a boss must exist (to be flipped to True by the boss task).
STRICT = True
BOSS_STRICT = True
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _listed(mod_dir: Path) -> list[str]:
    meta = json.loads((mod_dir / "module.json").read_text(encoding="utf-8"))
    return [r["id"] for r in meta["lessons"]]


def _module_dirs() -> list[Path]:
    return sorted(p for p in (CONTENT / "modules").glob("*") if p.is_dir() and not p.name.startswith("."))


def _boss_dirs() -> list[Path]:
    return sorted(p for p in (CONTENT / "boss").glob("*") if (p / "boss.json").is_file())


def _lesson_cases() -> list:
    return [pytest.param(m, lid, id=f"{m.name}-{lid}") for m in _module_dirs() for lid in _listed(m)]


def _run_solution(script: Path, cwd: Path, lesson_dir: Path) -> None:
    env = {"PATH": os.environ["PATH"], "HOME": str(cwd), "LESSON_DIR": str(lesson_dir)}
    subprocess.run(["bash", str(script)], cwd=cwd, env=env,
                   check=True, capture_output=True, timeout=60)


# ---- checks (return problems) ----

def check_load(mod_dir: Path) -> list[str]:
    try:
        load_module(mod_dir)
    except ModuleError as e:
        return e.errors
    return []


def check_lesson_static(mod_dir: Path, lid: str) -> list[str]:
    mod = load_module(mod_dir)
    ids = [les.id for les in mod.lessons]
    les = next(x for x in mod.lessons if x.id == lid)
    errs = []
    if len(les.qcm) != 5:
        errs.append(f"{lid}: {len(les.qcm)} questions au lieu de 5")
    for q in les.qcm:
        if not q.explain.strip():
            errs.append(f"{lid}/{q.id}: explain vide")
        if q.remedial_lesson_id not in ids:
            errs.append(f"{lid}/{q.id}: remedial_lesson_id {q.remedial_lesson_id!r} hors module")
    body = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", les.body_md, flags=re.S))
    if len(re.findall(r"\*\*[^*\n]+\*\*", body)) < 3:
        errs.append(f"{lid}: moins de 3 paires **")
    if len(re.findall(r"!![^!\n]+!!", body)) < 3:
        errs.append(f"{lid}: moins de 3 paires !!")
    if les.tp is None:
        errs.append(f"{lid}: TP manquant")
    else:
        if len(les.tp.hints) < 3:
            errs.append(f"{lid}: moins de 3 indices")
        if les.tp.timeout_s > 60:
            errs.append(f"{lid}: timeout_s > 60")
    return errs


def check_tp_solution(mod_dir: Path, lid: str, tmp: Path) -> list[str]:
    les = next(x for x in load_module(mod_dir).lessons if x.id == lid)
    tp, tp_dir = les.tp, mod_dir / "lessons" / f"{lid}.tp"
    if tp is None:
        return [f"{lid}: TP manquant"]
    sol = tp_dir / "solution.sh"
    if not sol.is_file():
        return [f"{lid}: solution.sh manquant"]
    before, after = tmp / f"ws-{lid}-before", tmp / f"ws-{lid}-after"
    before.mkdir()
    after.mkdir()
    errs = []
    try:
        seed_workspace(tp, tp_dir, before)
        d = seed_workspace(tp, tp_dir, after)  # fresh copy: the before-check must not leave state
    except (ValueError, OSError) as e:
        return [f"{lid}: seed invalide ({e})"]
    if run_check(tp, before, tp_dir).passed:
        errs.append(f"{lid}: check réussit avant la solution")
    try:
        _run_solution(sol, d, tp_dir)
    except (subprocess.SubprocessError, OSError) as e:
        return errs + [f"{lid}: solution.sh en échec ({e})"]
    r = run_check(tp, after, tp_dir)
    if not r.passed:
        errs.append(f"{lid}: check échoue après la solution\n{r.output}")
    return errs


def check_emails(mod_dir: Path) -> list[str]:
    errs = []
    for f in mod_dir.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:  # bytecode is not shipped content
            text = f.read_text(encoding="utf-8", errors="replace")
            errs += [f"{f}: e-mail {m}" for m in EMAIL.findall(text) if not m.lower().endswith("@example.test")]
    return errs


def check_boss(boss_dir: Path, tmp: Path) -> list[str]:
    boss = json.loads((boss_dir / "boss.json").read_text(encoding="utf-8"))
    ws = tmp / f"boss-{boss_dir.name}"
    ws.mkdir()

    def phase_ok(ph) -> bool:
        tp = Tp(ph["pattern_id"], ph["label"], "", ph["check"], [], ph.get("timeout_s", 30), ".")
        return run_check(tp, ws, boss_dir).passed

    if not boss["phases"]:
        return [f"{boss_dir.name}: aucune phase"]
    errs = []
    for n, ph in enumerate(boss["phases"], 1):
        if phase_ok(ph):
            errs.append(f"{boss_dir.name}: phase {n} réussit sur workspace vide")
    for n, ph in enumerate(boss["phases"], 1):
        sol = boss_dir / f"phase{n}_solution.sh"
        if not sol.is_file():
            return errs + [f"{boss_dir.name}: {sol.name} manquant"]
        try:
            _run_solution(sol, ws, boss_dir)
        except (subprocess.SubprocessError, OSError) as e:
            return errs + [f"{boss_dir.name}: {sol.name} en échec ({e})"]
        if not phase_ok(ph):
            errs.append(f"{boss_dir.name}: phase {n} échoue après sa solution")
    return errs


# ---- shipped content ----

@pytest.mark.skipif(not STRICT, reason="enabled by the last lesson task")
def test_all_twelve_lessons_present():
    assert _listed(CONTENT / "modules" / "auto1") == EXPECTED_LESSONS


@pytest.mark.skipif(not BOSS_STRICT, reason="enabled by the boss task")
def test_boss_exists():
    assert _boss_dirs()


@pytest.mark.parametrize("mod_dir", _module_dirs(), ids=lambda p: p.name)
def test_module_loads(mod_dir):
    if not _listed(mod_dir):
        pytest.skip("no lessons yet")
    assert check_load(mod_dir) == []


@pytest.mark.parametrize("mod_dir,lid", _lesson_cases())
def test_lesson_static(mod_dir, lid):
    assert check_lesson_static(mod_dir, lid) == []


@pytest.mark.parametrize("mod_dir,lid", _lesson_cases())
def test_lesson_tp_solution(mod_dir, lid, tmp_path):
    assert check_tp_solution(mod_dir, lid, tmp_path) == []


@pytest.mark.parametrize("mod_dir", _module_dirs(), ids=lambda p: p.name)
def test_no_foreign_emails(mod_dir):
    assert check_emails(mod_dir) == []


@pytest.mark.parametrize("boss_dir", _boss_dirs(), ids=lambda p: p.name)
def test_boss(boss_dir, tmp_path):
    assert check_boss(boss_dir, tmp_path) == []


# ---- fiche assertions (added by task 5) ----

KIT = CONTENT / "modules" / "auto1" / "kit"
FICHES = ["FICHE_perso_vers_pro.md", "FICHE_ecrire_un_connecteur.md"]
RUBRIQUES = [
    "enregistrement de l'application dans l'annuaire de l'entreprise",
    "consentement administrateur",
    "droits d'accès aux mails",
    "règles d'accès conditionnel",
    "accord du service informatique",
]
# inline `code` that is a kit identifier: CamelCase class or snake_case name
IDENT = re.compile(r"^(?:[A-Z][a-z]+(?:[A-Z][a-z]+)+|[a-z]+(?:_[a-z]+)+)$")
NOT_KIT = {"mock_graph", "mock_gmail"}  # simulators: files, checked as modules below


def _fiche(name: str) -> str:
    return (KIT / name).read_text(encoding="utf-8")


def _prose(text: str) -> str:
    return re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", text, flags=re.S))


@pytest.mark.parametrize("name", FICHES)
def test_fiche_markers(name):
    body = _prose(_fiche(name))
    assert len(re.findall(r"\*\*[^*\n]+\*\*", body)) >= 3
    assert len(re.findall(r"!![^!\n]+!!", body)) >= 3


def test_fiche_perso_vers_pro_content():
    text = _fiche(FICHES[0])
    heads = [h.lower() for h in re.findall(r"^#+\s*(.+)$", text, flags=re.M)]
    for r in RUBRIQUES:
        assert any(r in h for h in heads), r
    assert "la connexion au compte professionnel se fait au travail, jamais depuis l'appli d'entraînement" in text
    assert "aucun mail réel ne va à Claude ou à un service externe" in text
    for needle in ("consumers", "organizations", "Mail.Read", "device code", "0600", ".mbox", "MboxMailSource"):
        assert needle in text, needle


def test_fiche_connecteur_content():
    text = _fiche(FICHES[1])
    for needle in ("MailSource", "fetch", "ImapSource", "readonly=True", "password_env", "connection_factory"):
        assert needle in text, needle


def test_fiches_identifiers_exist_in_kit():
    src = "\n".join(p.read_text(encoding="utf-8") for p in KIT.glob("*.py"))
    missing = []
    for name in FICHES:
        for tok in re.findall(r"`([^`\n]+)`", _fiche(name)):
            tok = tok.split("(")[0].strip()
            if IDENT.match(tok) and tok not in NOT_KIT and not re.search(rf"\b{tok}\b", src):
                missing.append(f"{name}: {tok}")
    assert missing == []
    for m in NOT_KIT:
        assert (KIT / f"{m}.py").is_file()


def test_fiches_constructor_signatures():
    import inspect
    import sys
    sys.path.insert(0, str(KIT))
    from gmail_api import GmailSource
    from imap_source import ImapSource
    from outlook_graph import OutlookGraphSource
    imap = inspect.signature(ImapSource.__init__).parameters
    assert list(imap)[1:] == ["host", "user", "password_env", "folder", "port", "connection_factory"]
    assert (imap["folder"].default, imap["port"].default, imap["connection_factory"].default) == ("INBOX", 993, None)
    out = inspect.signature(OutlookGraphSource.__init__).parameters
    assert out["tenant"].default == "consumers" and out["token_path"].default is None
    assert inspect.signature(GmailSource.__init__).parameters["token_path"].default is None
    text = _fiche(FICHES[1])
    assert 'ImapSource(host, user, password_env, folder="INBOX", port=993, connection_factory=None)' in text
    assert 'OutlookGraphSource(client_id, tenant="consumers")' in _fiche(FICHES[0])



# ---- self-test of the validator on a synthetic module ----

def _make_module(root: Path, *, questions=5, check="[ -f ok.txt ]") -> Path:
    m = root / "mod"
    les = m / "lessons"
    (les / "l01.tp").mkdir(parents=True)
    (m / "module.json").write_text(json.dumps(
        {"id": "m", "title": "M", "skill": "s", "lessons": [{"id": "l01", "title": "L", "minutes": 5}]}))
    (les / "l01.md").write_text("**a** **b** **c** !!x!! !!y!! !!z!!\n")
    (les / "l01.qcm.json").write_text(json.dumps([
        {"id": f"q{i}", "text": "?", "options": ["a", "b"], "answer": 0, "explain": "parce que",
         "remedial_lesson_id": "l01"} for i in range(questions)]))
    (les / "l01.tp" / "tp.json").write_text(json.dumps(
        {"id": "t", "title": "T", "instructions_md": "x", "check": check, "hints": ["1", "2", "3"],
         "timeout_s": 10, "workspace": "."}))
    (les / "l01.tp" / "solution.sh").write_text("touch ok.txt\n")
    return m


def test_selftest_valid_module_passes(tmp_path):
    m = _make_module(tmp_path)
    assert check_load(m) == []
    assert check_lesson_static(m, "l01") == []
    assert check_tp_solution(m, "l01", tmp_path) == []
    assert check_emails(m) == []


def test_selftest_detects_check_passing_on_empty(tmp_path):
    m = _make_module(tmp_path, check="true")
    assert any("avant la solution" in e for e in check_tp_solution(m, "l01", tmp_path))


def test_selftest_detects_four_questions(tmp_path):
    m = _make_module(tmp_path, questions=4)
    assert any("4 questions" in e for e in check_lesson_static(m, "l01"))


def test_selftest_detects_foreign_email(tmp_path):
    m = _make_module(tmp_path)
    (m / "lessons" / "l01.md").write_text("ok a@example.test mais bob@gmail.com\n")
    errs = check_emails(m)
    assert len(errs) == 1 and "bob@gmail.com" in errs[0]


def test_selftest_boss(tmp_path):
    b = tmp_path / "boss"
    b.mkdir()
    (b / "boss.json").write_text(json.dumps({"id": "b", "phases": [
        {"pattern_id": "p", "label": "L", "check": "test -f a.txt"},
        {"pattern_id": "q", "label": "L", "check": "test -f b.txt"}]}))
    (b / "phase1_solution.sh").write_text("touch a.txt\n")
    (b / "phase2_solution.sh").write_text("touch b.txt\n")
    assert check_boss(b, tmp_path) == []


def test_selftest_marker_counting(tmp_path):
    def errs(body):
        m = _make_module(tmp_path / str(abs(hash(body))))
        (m / "lessons" / "l01.md").write_text(body)
        return check_lesson_static(m, "l01")
    ok = "**a** **b** **c** !!x!! !!y!! !!z!!"
    assert errs(ok) == []
    assert errs("**** **** **** !!x!! !!y!! !!z!!")
    assert errs("```\n**a** **b** **c**\n```\n!!x!! !!y!! !!z!!")
    assert errs("`**a** **b** **c**` !!x!! !!y!! !!z!!")
    assert errs("**a** **b** **c** !!x!! !!y!! !!z")  # 7 markers, one unpaired


def test_selftest_check_with_own_state_detected(tmp_path):
    m = _make_module(tmp_path, check="touch ok; test -f ok")
    assert any("avant la solution" in e for e in check_tp_solution(m, "l01", tmp_path))


def test_selftest_missing_seed(tmp_path):
    m = _make_module(tmp_path)
    tpj = m / "lessons" / "l01.tp" / "tp.json"
    d = json.loads(tpj.read_text())
    d["seed"] = ["nope"]
    tpj.write_text(json.dumps(d))
    assert check_load(m)


def test_selftest_solution_missing_or_failing(tmp_path):
    m = _make_module(tmp_path / "a")
    sol = m / "lessons" / "l01.tp" / "solution.sh"
    sol.write_text("exit 1\n")
    assert any("en échec" in e for e in check_tp_solution(m, "l01", tmp_path))
    sol.unlink()
    assert any("manquant" in e for e in check_tp_solution(m, "l01", tmp_path))


def test_selftest_check_never_passes(tmp_path):
    m = _make_module(tmp_path, check="false")
    assert any("après la solution" in e for e in check_tp_solution(m, "l01", tmp_path))


def test_selftest_bad_remedial_id(tmp_path):
    m = _make_module(tmp_path)
    qf = m / "lessons" / "l01.qcm.json"
    qs = json.loads(qf.read_text())
    qs[0]["remedial_lesson_id"] = None
    qf.write_text(json.dumps(qs))
    assert check_lesson_static(m, "l01")
    qs[0]["remedial_lesson_id"] = "zz"
    qf.write_text(json.dumps(qs))
    assert check_load(m)


def test_selftest_email_case_and_binary(tmp_path):
    m = _make_module(tmp_path)
    (m / "x.txt").write_text("a@EXAMPLE.TEST")
    assert check_emails(m) == []
    (m / "b.bin").write_bytes(b"\xff\xfe bob@gmail.com \xff")
    assert len(check_emails(m)) == 1


def test_selftest_boss_failures(tmp_path):
    b = tmp_path / "boss"
    b.mkdir()
    (b / "boss.json").write_text(json.dumps({"id": "b", "phases": []}))
    assert check_boss(b, tmp_path)
    (tmp_path / "w2").mkdir()
    (b / "boss.json").write_text(json.dumps({"id": "b", "phases": [
        {"pattern_id": "p", "label": "L", "check": "test -f a.txt"}]}))
    (b / "phase1_solution.sh").write_text("true\n")  # does not satisfy the check
    assert any("après sa solution" in e for e in check_boss(b, tmp_path / 'w2'))


@pytest.mark.parametrize("lid,target", [("l03", "client.py"), ("l08", "digest.py"), ("l12", "quotidien.py")])
def test_check_immune_to_shadowed_stdlib(lid, target, tmp_path):
    """A learner-dropped subprocess.py must not make a check pass (python -I)."""
    lesson = CONTENT / "modules" / "auto1" / "lessons" / f"{lid}.tp"
    for n in (target, "digest.py"):
        (tmp_path / n).write_text("")
    (tmp_path / "subprocess.py").write_text("raise SystemExit(0)\n")
    subprocess.run(["cp", "-r", str(KIT), str(tmp_path / "kit")], check=True)
    p = subprocess.run(["bash", str(lesson / "check.sh")], cwd=tmp_path, env={**os.environ, "LESSON_DIR": str(lesson)},
                       capture_output=True, text=True, timeout=60)
    assert p.returncode != 0 and "ECHEC" in p.stdout
