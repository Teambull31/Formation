import json
from pathlib import Path
import pytest
from app.content import ModuleError
from app.progress import Profile
from app.weekly import build_brief, import_module

DEMO = Path(__file__).parent / "fixtures" / "demo_module"

@pytest.fixture
def profile():
    return Profile(
        total_xp=450,
        rank="Bronze",
        skills={"automation": 120, "docker": 80},
        tokens=3,
    )

def test_brief_contains_topic_format_and_weak_notions(profile):
    b = build_brief(profile, "Terraform", "TP guidé", ["q7"])
    assert "Terraform" in b
    assert "TP guidé" in b
    assert "q7" in b
    assert "Bronze" in b

def test_import_valid_module_copies_it(tmp_path):
    dest_root = tmp_path / "modules"
    res = import_module(DEMO, dest_root)
    assert res.exists()
    assert (res / "module.json").exists()

def test_import_broken_module_creates_nothing(tmp_path):
    broken_src = tmp_path / "broken_src"
    broken_src.mkdir()
    # Missing required module.json
    (broken_src / "other.txt").write_text("hello")

    dest_root = tmp_path / "modules"
    dest_root.mkdir()

    with pytest.raises(ModuleError):
        import_module(broken_src, dest_root)

    assert list(dest_root.iterdir()) == []
