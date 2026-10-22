from __future__ import annotations
import re
import subprocess
from pathlib import Path


def strip_markdown(md: str) -> str:
    # Retire blocs de code ```...```
    text = re.sub(r"```[\s\S]*?```", "", md)
    # Retire inline code `...`
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Retire les marqueurs de titres (# Title -> Title)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Retire **gras** -> gras
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # Retire !!rouge!! -> rouge
    text = re.sub(r"!!([^!]+)!!", r"\1", text)
    # Retire puces de listes
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Nettoie les lignes vides multiples
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def synthesize(text: str, out: Path | str, engine: str = "espeak") -> Path:
    out_path = Path(out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Use espeak-ng in French with speed 150 wpm
    clean_text = strip_markdown(text) if ("**" in text or "!!" in text or "#" in text) else text.strip()
    cmd = ["espeak-ng", "-v", "fr", "-s", "150", "-w", str(out_path)]

    proc = subprocess.run(
        cmd,
        input=clean_text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return out_path
