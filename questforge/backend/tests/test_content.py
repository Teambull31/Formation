import json
from pathlib import Path
import pytest
from app.content import load_module, ModuleError

DEMO = Path(__file__).parent / "fixtures" / "demo_module"

def test_load_demo_module():
    m = load_module(DEMO)
    assert m.id == "demo"
    assert len(m.lessons) == 2
    assert m.lessons[0].id == "l1"
    assert len(m.lessons[0].qcm) == 1
    assert m.lessons[0].tp is not None
    assert len(m.lessons[0].tp.hints) >= 1

def test_qcm_answer_must_be_in_options(tmp_path):
    # Setup a broken module where answer is 5 for 3 options
    mod_dir = tmp_path / "broken"
    lessons_dir = mod_dir / "lessons"
    lessons_dir.mkdir(parents=True)
    
    (mod_dir / "module.json").write_text(json.dumps({
        "id": "broken",
        "title": "Broken",
        "skill": "dev",
        "lessons": [{"id": "b1", "title": "B1", "minutes": 10}]
    }))
    (lessons_dir / "b1.md").write_text("# B1")
    (lessons_dir / "b1.qcm.json").write_text(json.dumps([
        {
            "id": "qb1",
            "text": "Question ?",
            "options": ["A", "B", "C"],
            "answer": 5,
            "explain": "Exp"
        }
    ]))
    
    with pytest.raises(ModuleError) as exc_info:
        load_module(mod_dir)
    assert any("answer" in err.lower() for err in exc_info.value.errors)

def test_all_errors_reported_not_just_first(tmp_path):
    mod_dir = tmp_path / "two_errors"
    lessons_dir = mod_dir / "lessons"
    lessons_dir.mkdir(parents=True)
    
    (mod_dir / "module.json").write_text(json.dumps({
        "id": "errs",
        "title": "Errors",
        "skill": "dev",
        "lessons": [
            {"id": "e1", "title": "E1", "minutes": 10},
            {"id": "e2", "title": "E2", "minutes": 10}
        ]
    }))
    # e1 missing markdown, e2 has invalid answer
    (lessons_dir / "e2.md").write_text("# E2")
    (lessons_dir / "e2.qcm.json").write_text(json.dumps([
        {"id": "qe2", "text": "Q?", "options": ["A"], "answer": 3, "explain": "E"}
    ]))
    
    with pytest.raises(ModuleError) as exc_info:
        load_module(mod_dir)
    assert len(exc_info.value.errors) == 2

def test_missing_lesson_file_reported(tmp_path):
    mod_dir = tmp_path / "missing_md"
    lessons_dir = mod_dir / "lessons"
    lessons_dir.mkdir(parents=True)
    
    (mod_dir / "module.json").write_text(json.dumps({
        "id": "miss",
        "title": "Missing",
        "skill": "dev",
        "lessons": [{"id": "m1", "title": "M1", "minutes": 10}]
    }))
    with pytest.raises(ModuleError) as exc_info:
        load_module(mod_dir)
    assert any("m1.md" in err or "missing" in err.lower() for err in exc_info.value.errors)

def test_tp_requires_at_least_one_hint(tmp_path):
    mod_dir = tmp_path / "no_hints"
    lessons_dir = mod_dir / "lessons"
    tp_dir = lessons_dir / "t1.tp"
    tp_dir.mkdir(parents=True)
    
    (mod_dir / "module.json").write_text(json.dumps({
        "id": "nohints",
        "title": "No hints",
        "skill": "dev",
        "lessons": [{"id": "t1", "title": "T1", "minutes": 10}]
    }))
    (lessons_dir / "t1.md").write_text("# T1")
    (lessons_dir / "t1.qcm.json").write_text(json.dumps([]))
    (tp_dir / "tp.json").write_text(json.dumps({
        "id": "tp_nohints",
        "title": "TP",
        "instructions_md": "Do it",
        "check": "echo ok",
        "hints": []
    }))
    
    with pytest.raises(ModuleError) as exc_info:
        load_module(mod_dir)
    assert any("hint" in err.lower() for err in exc_info.value.errors)
