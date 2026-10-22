from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from app.content import load_module
from app.progress import Profile


def build_brief(
    profile: Profile,
    topic: str,
    fmt: str,
    weak_questions: list[str],
) -> str:
    skills_summary = ", ".join(f"{s}: niveau {lvl}" for s, lvl in profile.skills.items()) if profile.skills else "Débutant"
    weak_summary = ", ".join(weak_questions) if weak_questions else "Aucune faiblesse signalée"

    return f"""# Brief de génération de module pour Claude Code

## Contexte de l'apprenant
- Rang actuel : {profile.rank} ({profile.total_xp} XP)
- Profil de compétences : {skills_summary}
- Notions et erreurs récentes à renforcer : {weak_summary}

## Objectif du module
- Sujet ciblé : {topic}
- Format pédagogique souhaité : {fmt}

## Structure exacte attendue des fichiers
Génère un dossier de module complet conforme au standard QuestForge :
1. `module.json` :
   - `id`: identifiant court (ex: {topic.lower().replace(' ', '_')})
   - `title`: titre explicite
   - `skill`: compétence ciblée
   - `lessons`: tableau des leçons avec `id`, `title`, `minutes`
2. Pour chaque leçon dans `lessons/` :
   - `<id>.md` : cours rédigé avec points clés en `**gras**` et notions critiques en `!!rouge!!`
   - `<id>.qcm.json` : tableau de questions à choix multiples avec `id`, `text`, `options`, `answer` (index 0-basé), `explain`, et `remedial_lesson_id`
   - `<id>.tp/tp.json` (optionnel) : TP pratique avec `id`, `title`, `instructions_md`, `check`, `hints` (au moins un indice progressif)
   - `<id>.tp/check.sh` : script bash vérifiant le travail de l'apprenant et retournant code 0 en cas de succès.
"""


def import_module(src: Path | str, dest_root: Path | str) -> Path:
    src_path = Path(src).resolve()
    dest_path = Path(dest_root).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    # 1. Validation préalable stricte (lève ModuleError si invalide)
    module = load_module(src_path)

    # 2. Copie sécurisée via dossier temporaire
    target_dir = dest_path / module.id
    with tempfile.TemporaryDirectory(dir=str(dest_path)) as tmp_dir:
        tmp_target = Path(tmp_dir) / module.id
        shutil.copytree(src_path, tmp_target)

        # Si le dossier de destination existe déjà, on le remplace
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(tmp_target), str(target_dir))

    return target_dir
