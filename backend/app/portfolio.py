"""Export « portfolio » : les TP réussis des modules marqués `portfolio`, prêts à publier, dans un zip."""
import io
import json
import os
import re
import sqlite3
import zipfile
from pathlib import Path

from app.content import Module
from app.progress import Profile

MAX_FILE = 200_000
MAX_TOTAL = 5_000_000
KEEP_DOTFILES = {".gitignore", ".dockerignore"}
SKIP_DIRS = {".git", ".terraform", "__pycache__", "node_modules", ".venv"}
SKIP_SUFFIXES = (".tfstate", ".tfstate.backup", ".tfvars", ".pem", ".key", ".pyc", ".log")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SECRET = re.compile(r"(pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)\s*[=:]\s*['\"]?([^\s'\"]{6,})", re.I)
PLACEHOLDER = re.compile(r"^(\$\{|\$[A-Z_]|var\.|<|\{\{|changeme|example|xxx|\*+$)", re.I)


def leak_reason(text: str) -> str | None:
    """Pourquoi ce texte ne doit pas être publié, ou None."""
    for m in EMAIL.finditer(text):
        if not m.group(0).lower().endswith("@example.test"):
            return "adresse e-mail"
    for m in SECRET.finditer(text):
        if not PLACEHOLDER.match(m.group(2)):
            return "secret en clair"
    return None


def _files(root: Path):
    """Fichiers réguliers sous root, sans suivre les liens, dans un ordre stable."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink() or not p.is_file():
                continue
            yield p


def passed_tps(db: sqlite3.Connection) -> set[str]:
    return {r[0].split(":", 1)[1] for r in db.execute("SELECT key FROM settings WHERE key LIKE 'tp_passed:%'")}


def build_zip(db: sqlite3.Connection, profile: Profile, modules: list[tuple[Path, Module]], workspace: Path,
              bosses_won: list[str]) -> tuple[bytes, dict]:
    done = passed_tps(db)
    included: list[tuple[str, str]] = []  # (module title, tp title)
    excluded: list[str] = []
    total = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for mod_dir, mod in modules:
            if not json.loads((mod_dir / "module.json").read_text(encoding="utf-8")).get("portfolio"):
                continue
            for les in mod.lessons:
                tp = les.tp
                ws = (Path(workspace) / tp.workspace) if tp else None
                if tp is None or tp.id not in done or ws is None or not ws.is_dir() or \
                        not ws.resolve().is_relative_to(Path(workspace).resolve()):
                    continue
                added = False
                for p in _files(ws):
                    rel = p.relative_to(ws).as_posix()
                    name = f"{mod.id}/{tp.workspace}/{rel}"
                    if (p.name.startswith(".") and p.name not in KEEP_DOTFILES) or p.name.endswith(SKIP_SUFFIXES):
                        excluded.append(f"{name} (fichier d'état ou de secrets)")
                        continue
                    if p.stat().st_size > MAX_FILE or total + p.stat().st_size > MAX_TOTAL:
                        excluded.append(f"{name} (trop gros)")
                        continue
                    try:
                        text = p.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        excluded.append(f"{name} (fichier binaire)")
                        continue
                    why = leak_reason(text)
                    if why:
                        excluded.append(f"{name} ({why} détecté)")
                        continue
                    z.writestr(name, text)
                    total += len(text.encode())
                    added = True
                if added:
                    included.append((mod.title, tp.title))
        z.writestr("README.md", readme(profile, included, excluded, bosses_won))
    return buf.getvalue(), {"tps": len(included), "excluded": excluded}


def readme(profile: Profile, included: list[tuple[str, str]], excluded: list[str], bosses_won: list[str]) -> str:
    lines = ["# Mon parcours DevOps / SecOps", "",
             "> Généré par l'appli Formation. **Relis tout avant de publier** : le tri automatique ne remplace pas ton regard.", "",
             f"**Rang :** {profile.rank} · **XP :** {profile.total_xp}", ""]
    if profile.skills:
        lines += ["## Compétences", "", "| Compétence | XP |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in sorted(profile.skills.items())]
        lines.append("")
    if bosses_won:
        lines += ["## Boss vaincus", ""] + [f"- {b}" for b in bosses_won] + [""]
    lines += ["## Travaux pratiques réussis", ""]
    lines += [f"- {m} : {t}" for m, t in included] or ["Aucun pour l'instant : valide un TP des modules Terraform ou Docker."]
    if excluded:
        lines += ["", "## Fichiers écartés automatiquement", ""] + [f"- {e}" for e in excluded]
    return "\n".join(lines) + "\n"
