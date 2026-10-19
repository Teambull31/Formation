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
    subprocess.run(["bash", str(script)], cwd=cwd, env={**os.environ, "LESSON_DIR": str(lesson_dir)},
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
    if les.body_md.count("**") < 6:
        errs.append(f"{lid}: moins de 3 paires **")
    if les.body_md.count("!!") < 6:
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
    ws = tmp / f"ws-{lid}"
    ws.mkdir()
    d = seed_workspace(tp, tp_dir, ws)
    errs = []
    if run_check(tp, ws, tp_dir).passed:
        errs.append(f"{lid}: check réussit avant la solution")
    try:
        _run_solution(sol, d, tp_dir)
    except (subprocess.SubprocessError, OSError) as e:
        return errs + [f"{lid}: solution.sh en échec ({e})"]
    r = run_check(tp, ws, tp_dir)
    if not r.passed:
        errs.append(f"{lid}: check échoue après la solution\n{r.output}")
    return errs


def check_emails(mod_dir: Path) -> list[str]:
    errs = []
    for f in mod_dir.rglob("*"):
        if f.is_file():
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            errs += [f"{f}: e-mail {m}" for m in EMAIL.findall(text) if not m.endswith("@example.test")]
    return errs


def check_boss(boss_dir: Path, tmp: Path) -> list[str]:
    boss = json.loads((boss_dir / "boss.json").read_text(encoding="utf-8"))
    ws = tmp / f"boss-{boss_dir.name}"
    ws.mkdir()

    def phase_ok(ph) -> bool:
        tp = Tp(ph["pattern_id"], ph["label"], "", ph["check"], [], ph.get("timeout_s", 30), ".")
        return run_check(tp, ws, boss_dir).passed

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

@pytest.mark.xfail(strict=False, reason="lessons added by later tasks")
def test_all_twelve_lessons_present():
    assert _listed(CONTENT / "modules" / "auto1") == EXPECTED_LESSONS


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
