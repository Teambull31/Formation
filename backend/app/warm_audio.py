"""Préchauffe le cache audio : uv run python -m app.warm_audio [dossier_contenu] [dossier_audio]
Génère le mp3 des leçons qui n'en ont pas, pour que la première lecture soit instantanée."""
import sys
from pathlib import Path

from app.audio import speak, strip_markdown
from app.content import ModuleError, load_module

if __name__ == "__main__":
    content = Path(sys.argv[1] if len(sys.argv) > 1 else "../content")
    audio = Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / ".formation" / "audio")
    for d in sorted((content / "modules").glob("*/")):
        try:
            mod = load_module(d)
        except ModuleError:
            continue
        for les in mod.lessons:
            if (audio / f"{les.id}.mp3").exists():
                continue
            try:
                print(les.id, speak(strip_markdown(les.body_md), audio / les.id).name, flush=True)
            except RuntimeError as e:
                print(les.id, "ÉCHEC", e, flush=True)
