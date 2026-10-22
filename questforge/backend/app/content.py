from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Question:
    id: str
    text: str
    options: list[str]
    answer: int
    explain: str
    remedial_lesson_id: str | None = None


@dataclass
class Tp:
    id: str
    title: str
    instructions_md: str
    check: str
    hints: list[str]
    timeout_s: int = 10
    workspace: str = "."


@dataclass
class Lesson:
    id: str
    title: str
    minutes: int
    body_md: str
    qcm: list[Question] = field(default_factory=list)
    tp: Tp | None = None


@dataclass
class Module:
    id: str
    title: str
    skill: str
    lessons: list[Lesson] = field(default_factory=list)


class ModuleError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def load_module(path: Path | str) -> Module:
    mod_path = Path(path).resolve()
    module_json_file = mod_path / "module.json"
    errors: list[str] = []

    if not module_json_file.exists():
        raise ModuleError([f"Fichier module.json manquant dans {mod_path}"])

    try:
        mod_data = json.loads(module_json_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise ModuleError([f"Erreur de syntaxe JSON dans module.json: {e}"])

    mod_id = mod_data.get("id", "")
    mod_title = mod_data.get("title", "")
    mod_skill = mod_data.get("skill", "")

    if not mod_id:
        errors.append("Le champ 'id' est requis dans module.json")
    if not mod_title:
        errors.append("Le champ 'title' est requis dans module.json")
    if not mod_skill:
        errors.append("Le champ 'skill' est requis dans module.json")

    lessons_meta = mod_data.get("lessons", [])
    if not isinstance(lessons_meta, list):
        errors.append("Le champ 'lessons' doit être une liste")
        raise ModuleError(errors)

    lessons_dir = mod_path / "lessons"
    loaded_lessons: list[Lesson] = []

    for item in lessons_meta:
        l_id = item.get("id")
        l_title = item.get("title", "")
        l_minutes = item.get("minutes", 10)

        if not l_id:
            errors.append("Une leçon dans module.json n'a pas d'id")
            continue

        md_file = lessons_dir / f"{l_id}.md"
        body_md = ""
        if not md_file.exists():
            errors.append(f"Fichier de leçon manquant: {l_id}.md dans {lessons_dir}")
        else:
            body_md = md_file.read_text(encoding="utf-8")

        # Chargement QCM
        qcm_file = lessons_dir / f"{l_id}.qcm.json"
        questions: list[Question] = []
        if qcm_file.exists():
            try:
                raw_qcm = json.loads(qcm_file.read_text(encoding="utf-8"))
                if not isinstance(raw_qcm, list):
                    errors.append(f"Le fichier QCM {qcm_file.name} doit contenir une liste")
                else:
                    for q in raw_qcm:
                        qid = q.get("id", "")
                        qtext = q.get("text", "")
                        qoptions = q.get("options", [])
                        qanswer = q.get("answer")
                        qexplain = q.get("explain", "")
                        qremedial = q.get("remedial_lesson_id")

                        if not isinstance(qoptions, list) or len(qoptions) == 0:
                            errors.append(f"Question {qid}: 'options' doit être une liste non vide")
                        elif not isinstance(qanswer, int) or qanswer < 0 or qanswer >= len(qoptions):
                            errors.append(
                                f"Question {qid}: answer ({qanswer}) invalide pour options (taille {len(qoptions)})"
                            )

                        questions.append(
                            Question(
                                id=qid,
                                text=qtext,
                                options=qoptions,
                                answer=qanswer if isinstance(qanswer, int) else 0,
                                explain=qexplain,
                                remedial_lesson_id=qremedial,
                            )
                        )
            except Exception as e:
                errors.append(f"Erreur de lecture de {qcm_file.name}: {e}")

        # Chargement TP
        tp_dir = lessons_dir / f"{l_id}.tp"
        tp_json_file = tp_dir / "tp.json"
        tp_obj: Tp | None = None

        if tp_dir.exists() and tp_json_file.exists():
            try:
                raw_tp = json.loads(tp_json_file.read_text(encoding="utf-8"))
                tp_id = raw_tp.get("id", f"{l_id}_tp")
                tp_title = raw_tp.get("title", f"TP {l_title}")
                tp_instr = raw_tp.get("instructions_md", "")
                tp_check = raw_tp.get("check", "check.sh")
                tp_hints = raw_tp.get("hints", [])
                tp_timeout = raw_tp.get("timeout_s", 10)
                tp_ws = raw_tp.get("workspace", ".")

                if not isinstance(tp_hints, list) or len(tp_hints) == 0:
                    errors.append(f"TP '{tp_id}': au moins un indice (hint) est requis")

                # If check is a relative path to a script file in tp_dir, verify it
                check_script_path = tp_dir / tp_check
                if check_script_path.exists():
                    check_cmd = str(check_script_path.resolve())
                else:
                    check_cmd = tp_check

                tp_obj = Tp(
                    id=tp_id,
                    title=tp_title,
                    instructions_md=tp_instr,
                    check=check_cmd,
                    hints=tp_hints if isinstance(tp_hints, list) else [],
                    timeout_s=tp_timeout,
                    workspace=tp_ws,
                )
            except Exception as e:
                errors.append(f"Erreur lors du chargement du TP pour {l_id}: {e}")

        loaded_lessons.append(
            Lesson(
                id=l_id,
                title=l_title,
                minutes=l_minutes,
                body_md=body_md,
                qcm=questions,
                tp=tp_obj,
            )
        )

    if errors:
        raise ModuleError(errors)

    return Module(
        id=mod_id,
        title=mod_title,
        skill=mod_skill,
        lessons=loaded_lessons,
    )
