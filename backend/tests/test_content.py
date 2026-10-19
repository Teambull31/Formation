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


@pytest.mark.parametrize("bad", ["../x", "a/b", "", "a b"])
def test_lesson_id_must_be_safe(tmp_path, bad):
    d = broken(tmp_path)
    edit(d / "module.json", lambda m: m["lessons"][0].update(id=bad))
    with pytest.raises(ModuleError) as e:
        load_module(d)
    assert any("id invalide" in x for x in e.value.errors)


def test_module_id_must_be_safe(tmp_path):
    d = broken(tmp_path)
    edit(d / "module.json", lambda m: m.update(id="../x"))
    with pytest.raises(ModuleError) as e:
        load_module(d)
    assert any("id invalide" in x for x in e.value.errors)


def _tp_edit(d, **kw):
    edit(d / "lessons/l1.tp/tp.json", lambda t: t.update(kw))


def test_seed_inside_module_ok_and_default_empty(tmp_path):
    assert load_module(DEMO).lessons[0].tp.seed == []
    d = broken(tmp_path)
    (d / "kit").mkdir()
    _tp_edit(d, seed=["../../kit"], workspace="tp1")
    assert load_module(d).lessons[0].tp.seed == ["../../kit"]


@pytest.mark.parametrize("seed", [["../../../etc"], ["/etc"], ["../../nope"], ["../../../../.."], "kit", [3]])
def test_start_rejects_seed_outside_module(tmp_path, seed):
    d = broken(tmp_path)
    _tp_edit(d, seed=seed)
    with pytest.raises(ModuleError):
        load_module(d)


def test_seed_symlink_rejected(tmp_path):
    d = broken(tmp_path)
    (d / "kit").symlink_to(tmp_path)
    _tp_edit(d, seed=["../../kit"])
    with pytest.raises(ModuleError):
        load_module(d)


@pytest.mark.parametrize("ws", ["..", "/tmp", "a/../..", "", 3])
def test_workspace_must_be_relative_and_safe(tmp_path, ws):
    d = broken(tmp_path)
    _tp_edit(d, workspace=ws)
    with pytest.raises(ModuleError):
        load_module(d)
