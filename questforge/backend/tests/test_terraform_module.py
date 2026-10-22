import importlib.util
import json
import stat
import sys
from pathlib import Path

import pytest

from app.content import load_module
from app.tp import run_check

MODULE = Path(__file__).resolve().parents[2] / "content" / "modules" / "terraform"
LESSONS = MODULE / "lessons"

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


def check(module, tmp_path, lesson_id, files):
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    lesson = next(l for l in module.lessons if l.id == lesson_id)
    return run_check(lesson.tp, tmp_path, LESSONS)


def variant(lesson_id, **replacements):
    """Solution de référence avec des fichiers remplacés ou ajoutés."""
    files = dict(SOLUTIONS[lesson_id])
    files.update(replacements)
    return files


def edit(text, old, new):
    assert old in text
    return text.replace(old, new)


# --- Structure du module ----------------------------------------------------


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


def test_every_lesson_marks_key_points(module):
    for lesson in module.lessons:
        assert "**" in lesson.body_md
        assert "!!" in lesson.body_md


# --- Solutions de référence --------------------------------------------------


@pytest.mark.parametrize("lesson_id", ["tf1", "tf2", "tf3"])
def test_check_fails_on_empty_workspace(module, tmp_path, lesson_id):
    assert not check(module, tmp_path, lesson_id, {}).passed


@pytest.mark.parametrize("lesson_id", ["tf1", "tf2", "tf3"])
def test_check_passes_on_reference_solution(module, tmp_path, lesson_id):
    result = check(module, tmp_path, lesson_id, SOLUTIONS[lesson_id])
    assert result.passed, result.output


# --- Cas négatifs : une règle = un test --------------------------------------

NEGATIVE = {
    # tf1
    "tf1-no-terraform-block": ("tf1", {"main.tf": MAIN_TF[MAIN_TF.index("resource"):]}, "terraform"),
    "tf1-no-required-version": ("tf1", {"main.tf": edit(MAIN_TF, '  required_version = ">= 1.5.0"\n', "")}, "required_version"),
    "tf1-required-version-outside-block": (
        "tf1",
        {"main.tf": edit(MAIN_TF, '  required_version = ">= 1.5.0"\n', "") + 'locals {\n  required_version = ">= 1.5.0"\n}\n'},
        "required_version",
    ),
    "tf1-no-required-providers": (
        "tf1",
        {"main.tf": 'terraform {\n  required_version = ">= 1.5.0"\n}\n' + MAIN_TF[MAIN_TF.index("resource"):]},
        "required_providers",
    ),
    "tf1-no-provider-version": ("tf1", {"main.tf": edit(MAIN_TF, '      version = "~> 2.5"\n', "")}, "version"),
    "tf1-version-only-in-resource": (
        "tf1",
        {"main.tf": edit(edit(MAIN_TF, '      version = "~> 2.5"\n', ""), '  content  = "Hello IaC"', '  content  = "Hello IaC"\n  version  = "1"')},
        "version",
    ),
    "tf1-wrong-provider-source": ("tf1", {"main.tf": edit(MAIN_TF, "hashicorp/local", "hashicorp/random")}, "hashicorp/local"),
    "tf1-commented-resource": (
        "tf1",
        {"main.tf": MAIN_TF[: MAIN_TF.index("resource")] + '# resource "local_file" "hello" {\n#   filename = "a"\n#   content = "b"\n# }\n'},
        "local_file",
    ),
    "tf1-wrong-resource-name": ("tf1", {"main.tf": edit(MAIN_TF, '"hello"', '"other"')}, "hello"),
    "tf1-no-filename": ("tf1", {"main.tf": edit(MAIN_TF, '  filename = "${path.module}/hello.txt"\n', "")}, "filename"),
    "tf1-no-content": ("tf1", {"main.tf": edit(MAIN_TF, '  content  = "Hello IaC"\n', "")}, "content"),
    "tf1-syntax-error": ("tf1", {"main.tf": MAIN_TF + "\nresource oops\n"}, "syntaxe"),
    "tf1-unclosed-block": ("tf1", {"main.tf": MAIN_TF.rstrip()[:-1]}, "accolade"),
    # tf2
    "tf2-no-variables-file": ("tf2", {"outputs.tf": OUTPUTS_TF}, "variables.tf"),
    "tf2-no-outputs-file": ("tf2", {"variables.tf": VARIABLES_TF}, "outputs.tf"),
    "tf2-no-app-name": ("tf2", variant("tf2", **{"variables.tf": VARIABLES_TF[VARIABLES_TF.index('variable "environment"'):]}), "app_name"),
    "tf2-app-name-untyped": ("tf2", variant("tf2", **{"variables.tf": edit(VARIABLES_TF, "  type        = string\n  description = \"Nom", "  description = \"Nom")}), "type"),
    "tf2-app-name-no-description": ("tf2", variant("tf2", **{"variables.tf": edit(VARIABLES_TF, '  description = "Nom de l\'application."\n', "")}), "description"),
    "tf2-app-name-empty-description": ("tf2", variant("tf2", **{"variables.tf": edit(VARIABLES_TF, "Nom de l'application.", "")}), "description"),
    "tf2-app-name-no-default": ("tf2", variant("tf2", **{"variables.tf": edit(VARIABLES_TF, '  default     = "demo"\n', "")}), "default"),
    "tf2-environment-has-default": ("tf2", variant("tf2", **{"variables.tf": edit(VARIABLES_TF, 'description = "Environnement cible."', 'description = "Environnement cible."\n  default     = "dev"')}), "obligatoire"),
    "tf2-environment-missing": ("tf2", variant("tf2", **{"variables.tf": VARIABLES_TF[: VARIABLES_TF.index('variable "environment"')]}), "environment"),
    "tf2-no-output": ("tf2", variant("tf2", **{"outputs.tf": "# vide\n"}), "config_path"),
    "tf2-output-no-description": ("tf2", variant("tf2", **{"outputs.tf": edit(OUTPUTS_TF, '  description = "Chemin du fichier."\n', "")}), "description"),
    "tf2-output-no-value": ("tf2", variant("tf2", **{"outputs.tf": edit(OUTPUTS_TF, "  value       = local_file.config.filename\n", "")}), "value"),
    "tf2-output-literal-value": ("tf2", variant("tf2", **{"outputs.tf": edit(OUTPUTS_TF, "local_file.config.filename", '"x"')}), "référencer"),
    # tf3
    "tf3-no-secure-file": ("tf3", {".gitignore": GITIGNORE}, "secure.tf"),
    "tf3-no-gitignore": ("tf3", {"secure.tf": SECURE_TF}, ".gitignore"),
    "tf3-not-sensitive": ("tf3", variant("tf3", **{"secure.tf": edit(SECURE_TF, "  sensitive   = true\n", "")}), "sensitive"),
    "tf3-sensitive-false": ("tf3", variant("tf3", **{"secure.tf": edit(SECURE_TF, "sensitive   = true", "sensitive   = false")}), "sensitive"),
    "tf3-password-has-default": ("tf3", variant("tf3", **{"secure.tf": edit(SECURE_TF, "  sensitive   = true", '  sensitive   = true\n  default     = "x"')}), "default"),
    "tf3-no-resource": ("tf3", variant("tf3", **{"secure.tf": SECURE_TF[: SECURE_TF.index("resource")]}), "local_sensitive_file"),
    "tf3-resource-ignores-variable": ("tf3", variant("tf3", **{"secure.tf": edit(SECURE_TF, 'content  = "password=${var.db_password}"', 'content  = "x"')}), "var.db_password"),
    "tf3-variable-only-in-comment": (
        "tf3",
        variant("tf3", **{"secure.tf": edit(SECURE_TF, 'content  = "password=${var.db_password}"', 'content  = "x" # var.db_password')}),
        "var.db_password",
    ),
    "tf3-hardcoded-with-dollar": (
        "tf3",
        variant("tf3", **{"extra.tf": 'locals {\n  db_password = "p$ss"\n}\n'}),
        "secret",
    ),
    "tf3-hardcoded-in-string": (
        "tf3",
        variant("tf3", **{"secure.tf": edit(SECURE_TF, 'content  = "password=${var.db_password}"', 'content  = "password=hunter2 ${var.db_password}"')}),
        "secret",
    ),
    "tf3-hardcoded-in-tfvars": ("tf3", variant("tf3", **{"terraform.tfvars": 'db_password = "hunter2"\n'}), "terraform.tfvars"),
    "tf3-hardcoded-in-tf-json": ("tf3", variant("tf3", **{"extra.tf.json": json.dumps({"locals": {"api_token": "abc123"}})}), "extra.tf.json"),
    "tf3-hardcoded-variable-default": (
        "tf3",
        variant("tf3", **{"extra.tf": 'variable "admin_password" {\n  type    = string\n  default = "root"\n}\n'}),
        "admin_password",
    ),
    "tf3-gitignore-missing-state": ("tf3", variant("tf3", **{".gitignore": ".terraform/\n*.tfvars\n*.tfstate.*\n"}), "state"),
    "tf3-gitignore-missing-backup": ("tf3", variant("tf3", **{".gitignore": "*.tfstate\n.terraform/\n*.tfvars\n"}), "sauvegardes"),
    "tf3-gitignore-missing-cache": ("tf3", variant("tf3", **{".gitignore": "*.tfstate\n*.tfstate.*\n*.tfvars\n"}), ".terraform"),
    "tf3-gitignore-missing-tfvars": ("tf3", variant("tf3", **{".gitignore": "*.tfstate\n*.tfstate.*\n.terraform/\n"}), "tfvars"),
    "tf3-gitignore-negated": ("tf3", variant("tf3", **{".gitignore": GITIGNORE + "!*.tfvars\n"}), "tfvars"),
    "tf3-gitignore-commented-out": ("tf3", variant("tf3", **{".gitignore": GITIGNORE.replace("*.tfvars", "# *.tfvars")}), "tfvars"),
}


@pytest.mark.parametrize("name", sorted(NEGATIVE))
def test_check_rejects(module, tmp_path, name):
    lesson_id, files, expected = NEGATIVE[name]
    result = check(module, tmp_path, lesson_id, files)
    assert not result.passed, f"{name} aurait dû échouer :\n{result.output}"
    assert expected.lower() in result.output.lower(), result.output


# --- Variantes valides qui ne doivent pas être rejetées ----------------------

POSITIVE = {
    "tf1-comments-and-blank-lines": ("tf1", {"main.tf": "# Ma première config\n\n" + MAIN_TF.replace("resource", "// la ressource\nresource")}),
    "tf1-block-comment": ("tf1", {"main.tf": "/* en-tête\n   multi-ligne { */\n" + MAIN_TF}),
    "tf1-one-line-resource-attrs": (
        "tf1",
        {"main.tf": edit(MAIN_TF, '    local = {\n      source  = "hashicorp/local"\n      version = "~> 2.5"\n    }', '    local = { source = "hashicorp/local", version = "~> 2.5" }')},
    ),
    "tf1-crlf": ("tf1", {"main.tf": MAIN_TF.replace("\n", "\r\n").encode()}),
    "tf2-brace-in-description": ("tf2", variant("tf2", **{"variables.tf": edit(VARIABLES_TF, "Nom de l'application.", "Nom {app} de l'application }")})),
    "tf2-one-line-block": (
        "tf2",
        variant("tf2", **{"outputs.tf": 'output "config_path" {\n  description = "Chemin."\n  value = var.environment\n}\n'}),
    ),
    "tf2-nested-default-and-validation": (
        "tf2",
        variant(
            "tf2",
            **{
                "variables.tf": edit(
                    VARIABLES_TF,
                    'description = "Environnement cible."',
                    'description = "Environnement cible."\n  validation {\n    condition     = contains(["dev", "prod"], var.environment)\n    error_message = "default = dev ou prod"\n  }',
                )
            },
        ),
    ),
    "tf2-output-interpolated-reference": (
        "tf2",
        variant("tf2", **{"outputs.tf": edit(OUTPUTS_TF, "local_file.config.filename", '"${var.app_name}.conf"')}),
    ),
    "tf3-crlf-gitignore": ("tf3", variant("tf3", **{".gitignore": GITIGNORE.replace("\n", "\r\n").encode()})),
    "tf3-trailing-spaces-gitignore": ("tf3", variant("tf3", **{".gitignore": GITIGNORE.replace("\n", "  \n")})),
    "tf3-anchored-and-recursive-patterns": (
        "tf3",
        variant("tf3", **{".gitignore": "**/*.tfstate\n/*.tfstate.*\n/.terraform/\n**/*.tfvars\n"}),
    ),
    "tf3-glob-covers-state-and-backup": ("tf3", variant("tf3", **{".gitignore": "*.tfstate*\n.terraform\n*.tfvars\n"})),
    "tf3-comments-in-gitignore": ("tf3", variant("tf3", **{".gitignore": "# Terraform\n\n" + GITIGNORE})),
    "tf3-secret-name-not-a-secret": (
        "tf3",
        variant("tf3", **{"extra.tf": 'locals {\n  secret_name = "db-credentials"\n  password_length = 24\n}\n'}),
    ),
    "tf3-secret-from-variable-in-other-file": (
        "tf3",
        variant("tf3", **{"extra.tf": 'locals {\n  api_token = var.db_password\n}\n'}),
    ),
    "tf3-state-and-modules-dirs-ignored": (
        "tf3",
        variant("tf3", **{".terraform/modules/leak.tf": 'locals {\n  password = "x"\n}\n'}),
    ),
}


@pytest.mark.parametrize("name", sorted(POSITIVE))
def test_check_accepts(module, tmp_path, name):
    lesson_id, files = POSITIVE[name]
    result = check(module, tmp_path, lesson_id, files)
    assert result.passed, f"{name} aurait dû passer :\n{result.output}"


# --- Formatage : conseil non bloquant, indépendant du binaire ----------------


def fake_terraform(tmp_path, monkeypatch, exit_code):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "terraform"
    script.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")


@pytest.mark.parametrize("lesson_id", ["tf1", "tf2", "tf3"])
def test_unformatted_code_is_advice_not_failure(module, tmp_path, monkeypatch, lesson_id):
    fake_terraform(tmp_path, monkeypatch, 3)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = check(module, workspace, lesson_id, SOLUTIONS[lesson_id])
    assert result.passed, result.output
    assert "terraform fmt" in result.output


def test_formatted_code_gets_no_advice(module, tmp_path, monkeypatch):
    fake_terraform(tmp_path, monkeypatch, 0)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = check(module, workspace, "tf1", SOLUTIONS["tf1"])
    assert result.passed
    assert "Conseil" not in result.output


# --- Analyseur HCL -----------------------------------------------------------


@pytest.fixture(scope="module")
def hcl():
    spec = importlib.util.spec_from_file_location("hcl_check", LESSONS / "_hcl_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parser_handles_strings_with_braces_and_comments(hcl):
    root = hcl.parse_text('variable "x" {\n  description = "a } b { # pas un commentaire"\n  type = string # vrai commentaire\n}\n')
    var = root.blocks[0]
    assert var.labels == ["x"]
    assert var.attrs["type"] == "string"
    assert hcl.literal(var.attrs["description"]) == "a } b { # pas un commentaire"


def test_parser_handles_heredocs_and_interpolation(hcl):
    root = hcl.parse_text('locals {\n  a = <<EOT\nligne # 1 }\nEOT\n  b = "${var.x}-${format("%s", "y")}"\n}\n')
    attrs = root.blocks[0].attrs
    assert "ligne # 1 }" in attrs["a"]
    assert hcl.literal(attrs["b"]) is None


def test_gitignore_matcher(hcl):
    rules = [("*.tfstate", False), (".terraform/", False), ("keep.tfstate", True)]
    assert hcl.is_ignored(rules, "a/b/c.tfstate")
    assert hcl.is_ignored(rules, ".terraform/providers/x")
    assert not hcl.is_ignored(rules, "keep.tfstate")
    assert not hcl.is_ignored(rules, "main.tf")
