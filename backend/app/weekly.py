import shutil
import tempfile
from pathlib import Path

from app.content import ModuleError, load_module
from app.progress import Profile, level_for_xp


def build_brief(profile: Profile, topic: str, fmt: str, weak_questions: list[str]) -> str:
    levels = "\n".join(f"- {s} : niveau {level_for_xp(xp)}" for s, xp in sorted(profile.skills.items())) or "- (aucune compétence encore)"
    weak = ", ".join(weak_questions) or "aucune"
    return f"""Génère un module de formation hebdomadaire.

Sujet : {topic}
Format : {fmt}

Niveau par compétence :
{levels}

Notions à renforcer (ids de questions ratées) : {weak}

Structure exacte attendue (un dossier de module) :
- module.json : {{"id", "title", "skill", "lessons": [{{"id", "title", "minutes"}}]}}
  Les ids (module et leçons) ne contiennent que lettres, chiffres, _ et -.
- Pour chaque leçon <id> :
  - lessons/<id>.md : le cours, avec les points clés en **gras** et !!rouge!! (!!texte!! pour l'essentiel à retenir)
  - lessons/<id>.qcm.json : liste de {{"id", "text", "options", "answer", "explain", "remedial_lesson_id"}}
    (answer = index de la bonne option ; ids de questions uniques ; remedial_lesson_id = id d'une leçon du module ou null)
  - lessons/<id>.tp/tp.json et lessons/<id>.tp/check.sh : le TP (tp.json : id, title, instructions_md, check, hints (au moins un), timeout_s, workspace)

Les vérifications scriptées (check.sh) décident seules de la réussite d'un TP : elles doivent être déterministes et sans intervention humaine.
N'inclus aucune donnée réelle : pas de données personnelles ni professionnelles dans le contenu (noms, entreprises, hôtes, identifiants, secrets).
"""


def import_module(src: Path, dest_root: Path) -> Path:
    src, dest_root = Path(src), Path(dest_root)
    module = load_module(src)  # ModuleError propagates before anything is created
    links = [p for p in src.rglob("*") if p.is_symlink()]
    if links:
        raise ModuleError([f"symlink interdit: {p}" for p in links])
    dest_root.mkdir(parents=True, exist_ok=True)
    dest_root = dest_root.resolve()
    final = dest_root / module.id
    if final.is_symlink():
        raise ModuleError([f"destination symlink interdite: {final}"])
    tmp = Path(tempfile.mkdtemp(dir=dest_root, prefix=".import-"))
    try:
        staged = tmp / module.id
        shutil.copytree(src, staged, symlinks=False)
        if final.exists():
            shutil.rmtree(final)
        staged.rename(final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final
