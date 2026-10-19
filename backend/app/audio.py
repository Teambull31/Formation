import re
import shutil
import subprocess
from pathlib import Path


def strip_markdown(md: str) -> str:
    md = re.sub(r"```.*?```", "", md, flags=re.S)
    md = md.replace("**", "").replace("!!", "").replace("`", "")
    lines = [re.sub(r"^\s*(#+\s*|[-*]\s+)", "", ln) for ln in md.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip()).strip()


def synthesize(text: str, out: Path, engine: str = "espeak") -> Path:
    if engine != "espeak":
        raise ValueError(f"Moteur audio inconnu : {engine}")
    if shutil.which("espeak-ng") is None:
        raise RuntimeError("espeak-ng est introuvable : installez-le pour générer l'audio")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-w", str(out), text],
                       check=True, capture_output=True, text=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        detail = getattr(e, "stderr", "") or str(e)
        raise RuntimeError(f"Échec de la synthèse vocale (espeak-ng) : {detail.strip()}") from e
    return out
