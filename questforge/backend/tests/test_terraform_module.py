from pathlib import Path

import pytest

from app.content import load_module
from app.tp import run_check

MODULE = Path(__file__).resolve().parents[2] / "content" / "modules" / "terraform"

MAIN_TF = '''terraform {
  required_version = ">= 1.5.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

resource "local_file" "hello" {
  filename = "${path.module}/hello.txt"
  content  = "Hello IaC"
}
'''

VARIABLES_TF = '''variable "app_name" {
  type        = string
  description = "Nom de l'application."
  default     = "demo"
}

variable "environment" {
  type        = string
  description = "Environnement cible."
}
'''

OUTPUTS_TF = '''output "config_path" {
  description = "Chemin du fichier."
  value       = local_file.config.filename
}
'''

SECURE_TF = '''variable "db_password" {
  type        = string
  description = "Mot de passe injecté à l'exécution."
  sensitive   = true
}

resource "local_sensitive_file" "db" {
  filename = "${path.module}/db.conf"
  content  = "password=${var.db_password}"
}
'''

GITIGNORE = "*.tfstate\n*.tfstate.*\n.terraform/\n*.tfvars\n"

SOLUTIONS = {
    "tf1": {"main.tf": MAIN_TF},
    "tf2": {"variables.tf": VARIABLES_TF, "outputs.tf": OUTPUTS_TF},
    "tf3": {"secure.tf": SECURE_TF, ".gitignore": GITIGNORE},
}


@pytest.fixture(scope="module")
def module():
    return load_module(MODULE)


def test_module_is_valid(module):
    assert module.id == "terraform"
    assert [lesson.id for lesson in module.lessons] == ["tf1", "tf2", "tf3"]
    for lesson in module.lessons:
        assert lesson.body_md
        assert lesson.qcm
        assert lesson.tp is not None


def test_question_ids_are_unique(module):
    ids = [q.id for lesson in module.lessons for q in lesson.qcm]
    assert len(ids) == len(set(ids))


def test_remedial_lessons_exist(module):
    lesson_ids = {lesson.id for lesson in module.lessons}
    for lesson in module.lessons:
        for q in lesson.qcm:
            assert q.remedial_lesson_id in lesson_ids


@pytest.mark.parametrize("lesson_id", ["tf1", "tf2", "tf3"])
def test_check_fails_on_empty_workspace(module, tmp_path, lesson_id):
    lesson = next(l for l in module.lessons if l.id == lesson_id)
    result = run_check(lesson.tp, tmp_path, MODULE / "lessons")
    assert not result.passed


@pytest.mark.parametrize("lesson_id", ["tf1", "tf2", "tf3"])
def test_check_passes_on_reference_solution(module, tmp_path, lesson_id):
    for name, content in SOLUTIONS[lesson_id].items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    lesson = next(l for l in module.lessons if l.id == lesson_id)
    result = run_check(lesson.tp, tmp_path, MODULE / "lessons")
    assert result.passed, result.output


def test_tf2_rejects_default_on_required_variable(module, tmp_path):
    (tmp_path / "variables.tf").write_text(
        VARIABLES_TF.replace(
            'description = "Environnement cible."',
            'description = "Environnement cible."\n  default     = "dev"',
        ),
        encoding="utf-8",
    )
    (tmp_path / "outputs.tf").write_text(OUTPUTS_TF, encoding="utf-8")
    lesson = next(l for l in module.lessons if l.id == "tf2")
    result = run_check(lesson.tp, tmp_path, MODULE / "lessons")
    assert not result.passed
    assert "environment" in result.output


def test_tf3_rejects_hardcoded_secret(module, tmp_path):
    (tmp_path / "secure.tf").write_text(SECURE_TF, encoding="utf-8")
    (tmp_path / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (tmp_path / "extra.tf").write_text('locals {\n  db_password = "hunter2"\n}\n', encoding="utf-8")
    lesson = next(l for l in module.lessons if l.id == "tf3")
    result = run_check(lesson.tp, tmp_path, MODULE / "lessons")
    assert not result.passed
    assert "en dur" in result.output
