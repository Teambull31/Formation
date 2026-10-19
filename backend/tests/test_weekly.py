import json
import shutil
from pathlib import Path

import pytest

from app.content import ModuleError
from app.progress import Profile
from app.weekly import build_brief, import_module

DEMO = Path(__file__).parent / "fixtures" / "demo_module"


@pytest.fixture
def profile():
    return Profile(300, "Bronze", {"terraform": 200, "k8s": 100}, 0)


def test_brief_contains_topic_format_and_weak_notions(profile):
    b = build_brief(profile, "Terraform", "TP guidé", ["q7"])
    for s in ("Terraform", "TP guidé", "q7", "terraform", "module.json", "check.sh", "!!rouge!!"):
        assert s in b
    assert "données personnelles" in b


def test_import_valid_module_copies_it(tmp_path):
    assert (import_module(DEMO, tmp_path) / "module.json").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["demo"]


def test_import_replaces_existing(tmp_path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "old.txt").touch()
    p = import_module(DEMO, tmp_path)
    assert not (p / "old.txt").exists() and (p / "module.json").exists()
    assert [x.name for x in tmp_path.iterdir()] == ["demo"]


def test_import_broken_module_creates_nothing(tmp_path):
    src = tmp_path / "src"
    shutil.copytree(DEMO, src)
    (src / "lessons" / "l1.md").unlink()
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(ModuleError):
        import_module(src, dest)
    assert list(dest.iterdir()) == []


def test_import_refuses_path_traversal(tmp_path):
    src = tmp_path / "src"
    shutil.copytree(DEMO, src)
    m = json.loads((src / "module.json").read_text())
    m["id"] = "../evil"
    (src / "module.json").write_text(json.dumps(m))
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(ModuleError):
        import_module(src, dest)
    assert not (tmp_path / "evil").exists() and list(dest.iterdir()) == []


def _copy(tmp_path):
    src = tmp_path / "src"
    shutil.copytree(DEMO, src)
    dest = tmp_path / "dest"
    dest.mkdir()
    return src, dest


@pytest.mark.parametrize("target", ["/etc/hostname", "/nonexistent/x"])
def test_import_refuses_symlinks(tmp_path, target):
    src, dest = _copy(tmp_path)
    (src / "lessons" / "link").symlink_to(target)
    with pytest.raises(ModuleError, match="symlink interdit"):
        import_module(src, dest)
    assert list(dest.iterdir()) == []


def test_import_refuses_dir_symlink(tmp_path):
    src, dest = _copy(tmp_path)
    (src / "dirlink").symlink_to(tmp_path)
    with pytest.raises(ModuleError, match="symlink interdit"):
        import_module(src, dest)
    assert list(dest.iterdir()) == []


def test_import_refuses_symlinked_destination(tmp_path):
    src, dest = _copy(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    (dest / "demo").symlink_to(other)
    with pytest.raises(ModuleError):
        import_module(src, dest)
    assert list(other.iterdir()) == []


def test_import_creates_dest_root_only_on_success(tmp_path):
    src, _ = _copy(tmp_path)
    root = tmp_path / "new" / "root"
    assert (import_module(src, root) / "module.json").exists()
    (src / "lessons" / "l1.md").unlink()
    root2 = tmp_path / "other_root"
    with pytest.raises(ModuleError):
        import_module(src, root2)
    assert not root2.exists()
