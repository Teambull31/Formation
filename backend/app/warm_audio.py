"""Préchauffe le cache audio : uv run python -m app.warm_audio [dossier_contenu] [dossier_audio]
Génère le mp3 des leçons qui n'en ont pas ou dont le .md est plus récent, pour que la première lecture soit instantanée."""
import sys
from pathlib import Path

from app.audio import fiche_speech, speak, stale, strip_markdown
from app.content import ModuleError, load_module

def main(content: Path, audio: Path) -> None:
    for d in sorted((content / "modules").glob("*/")):
        try:
            mod = load_module(d)
        except ModuleError:
            continue
        for les in mod.lessons:
            if not stale(audio / f"{les.id}.mp3", d / "lessons" / f"{les.id}.md"):
                continue  # mp3 présent et plus récent que la leçon
            try:
                print(les.id, speak(strip_markdown(les.body_md), audio / les.id).name, flush=True)
            except RuntimeError as e:
                print(les.id, "ÉCHEC", e, flush=True)
        fiche = d / "fiche.md"
        if mod.fiche_md is not None and stale(audio / f"fiche-{mod.id}.mp3", fiche):
            try:  # même nom et même texte que /api/fiche-audio : la première écoute est instantanée
                print(f"fiche-{mod.id}", speak(fiche_speech(mod.title, mod.fiche_md), audio / f"fiche-{mod.id}").name, flush=True)
            except RuntimeError as e:
                print(f"fiche-{mod.id}", "ÉCHEC", e, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../content"),
         Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / ".formation" / "audio"))
