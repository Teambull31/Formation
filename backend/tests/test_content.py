import json
import shutil
from pathlib import Path

import pytest

from app.content import ModuleError, load_module

DEMO = Path(__file__).parent / "fixtures" / "demo_module"


def broken(tmp_path):
    dst = tmp_path / "m"
    shutil.copytree(DEMO, dst)
    return dst


def edit(path, fn):
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def test_load_demo_module():
    m = load_module(DEMO)
    assert m.id == "demo" and len(m.lessons) == 2
    l1 = m.lessons[0]
    assert l1.qcm[0].remedial_lesson_id == "l2" and l1.qcm[0].answer == 1
    assert l1.tp.id == "t1" and len(l1.tp.hints) == 3 and "**" in l1.body_md and "!!" in l1.body_md


def test_qcm_answer_must_be_in_options(tmp_path):
    d = broken(tmp_path)
    edit(d / "lessons/l1.qcm.json", lambda q: q[0].update(answer=5))
    with pytest.raises(ModuleError) as e:
        load_module(d)
    assert "answer" in e.value.errors[0]


def test_all_errors_reported_not_just_first(tmp_path):
    d = broken(tmp_path)
    edit(d / "lessons/l1.qcm.json", lambda q: q[0].update(answer=5))
    edit(d / "lessons/l2.qcm.json", lambda q: q[0].update(answer=-1))
    with pytest.raises(ModuleError) as e:
        load_module(d)
    assert len(e.value.errors) == 2


def test_missing_lesson_file_reported(tmp_path):
    d = broken(tmp_path)
    (d / "lessons/l2.md").unlink()
    with pytest.raises(ModuleError) as e:
        load_module(d)
    assert any("l2.md" in x for x in e.value.errors)


def test_tp_requires_at_least_one_hint(tmp_path):
    d = broken(tmp_path)
    edit(d / "lessons/l1.tp/tp.json", lambda t: t.update(hints=[]))
    with pytest.raises(ModuleError) as e:
        load_module(d)
    assert any("hints" in x for x in e.value.errors)
