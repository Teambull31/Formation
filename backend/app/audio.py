import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path


def strip_markdown(md: str) -> str:
    md = re.sub(r"```.*?```", "", md, flags=re.S)
    md = md.replace("**", "").replace("!!", "").replace("`", "")
    lines = [re.sub(r"^\s*(#+\s*|[-*]\s+)", "", ln) for ln in md.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip()).strip()


EDGE_VOICE = "fr-FR-VivienneMultilingualNeural"
EDGE_TIMEOUT_S = 300
EDGE_CHUNK = 800  # caractères par requête : edge-tts est lent sur un long texte, des morceaux en parallèle vont plus vite
EDGE_PARALLEL = 8


def _chunks(text: str, size: int = EDGE_CHUNK) -> list[str]:
    out, cur = [], ""
    for ln in text.splitlines():
        while len(ln) > size:  # ligne géante : coupe à la dernière espace
            cut = ln.rfind(" ", 0, size)
            if cut <= 0:
                cut = size
            out.append(ln[:cut]); ln = ln[cut:].lstrip()
        if cur and len(cur) + len(ln) + 1 > size:
            out.append(cur); cur = ""
        cur = f"{cur}\n{ln}" if cur else ln
    if cur.strip():
        out.append(cur)
    return out or [text]


def _synthesize_edge(text: str, out: Path) -> Path:
    # edge-tts : service Microsoft non officiel, en ligne ; produit du mp3 (des mp3 mis bout à bout se lisent)
    try:
        import edge_tts
    except ImportError as e:
        raise RuntimeError("edge-tts est introuvable") from e
    voice = os.environ.get("FORMATION_TTS_VOICE", EDGE_VOICE)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    async def one(sem, chunk):
        async with sem:
            data = b""
            async for m in edge_tts.Communicate(chunk, voice).stream():
                if m["type"] == "audio":
                    data += m["data"]
            return data

    async def run():
        sem = asyncio.Semaphore(EDGE_PARALLEL)
        parts = await asyncio.wait_for(asyncio.gather(*(one(sem, c) for c in _chunks(text))), EDGE_TIMEOUT_S)
        if not all(parts):
            raise RuntimeError("morceau sans audio")
        out.write_bytes(b"".join(parts))

    try:
        asyncio.run(run())
    except Exception as e:  # réseau, délai, voix refusée : l'appelant bascule sur espeak
        raise RuntimeError(f"Échec de la synthèse vocale (edge-tts) : {e}") from e
    return out


def speak(text: str, stem: Path) -> Path:
    """Génère l'audio de `stem` (sans extension) : edge-tts en mp3, repli espeak en wav.
    FORMATION_TTS=espeak force espeak. Écriture atomique ; ne laisse aucun fichier partiel."""
    stem = Path(stem)
    if os.environ.get("FORMATION_TTS", "edge") == "edge":
        mp3 = stem.with_suffix(".mp3")
        tmp = mp3.with_name(mp3.name + ".tmp")
        try:
            _synthesize_edge(text, tmp)
            os.replace(tmp, mp3)
            return mp3
        except RuntimeError:
            pass  # hors ligne ou service cassé : repli espeak
        finally:
            tmp.unlink(missing_ok=True)
    wav = stem.with_suffix(".wav")
    if wav.exists():
        return wav
    tmp = wav.with_name(wav.name + ".tmp")
    try:
        synthesize(text, tmp)
        os.replace(tmp, wav)
    finally:
        tmp.unlink(missing_ok=True)
    return wav


def synthesize(text: str, out: Path, engine: str = "espeak") -> Path:
    if engine == "edge":
        return _synthesize_edge(text, out)
    if engine != "espeak":
        raise ValueError(f"Moteur audio inconnu : {engine}")
    if shutil.which("espeak-ng") is None:
        raise RuntimeError("espeak-ng est introuvable : installez-le pour générer l'audio")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-w", str(out), "--", text],
                       check=True, capture_output=True, text=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        detail = getattr(e, "stderr", "") or str(e)
        raise RuntimeError(f"Échec de la synthèse vocale (espeak-ng) : {detail.strip()}") from e
    if not out.exists():
        raise RuntimeError("Échec de la synthèse vocale (espeak-ng) : aucun fichier produit")
    return out
