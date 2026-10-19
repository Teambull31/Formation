import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePath


@dataclass
class Question:
    id: str
    text: str
    options: list[str]
    answer: int
    explain: str
    remedial_lesson_id: str | None


@dataclass
class Tp:
    id: str
    title: str
    instructions_md: str
    check: str
    hints: list[str]
    timeout_s: int
    workspace: str
    seed: list[str] = field(default_factory=list)


@dataclass
class Lesson:
    id: str
    title: str
    minutes: int
    body_md: str
    qcm: list[Question]
    tp: Tp | None


@dataclass
class Module:
    id: str
    title: str
    skill: str
    lessons: list[Lesson]


class ModuleError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: fichier manquant")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        errors.append(f"{path}: JSON invalide ({e})")
    return None


def _fields(obj, path: Path, keys: list[str], errors: list[str]) -> bool:
    if not isinstance(obj, dict):
        errors.append(f"{path}: objet attendu")
        return False
    missing = [k for k in keys if k not in obj]
    for k in missing:
        errors.append(f"{path}: champ '{k}' manquant")
    return not missing


def _qcm(path: Path, errors: list[str]) -> list[Question]:
    data = _json(path, errors)
    if data is None:
        return []
    if not isinstance(data, list):
        errors.append(f"{path}: liste de questions attendue")
        return []
    out = []
    for i, q in enumerate(data):
        keys = ["id", "text", "options", "answer", "explain"]
        if not _fields(q, path, keys, errors):
            continue
        n = len(q["options"]) if isinstance(q["options"], list) else 0
        ans = q["answer"]
        if not isinstance(ans, int) or isinstance(ans, bool) or not 0 <= ans < n:
            errors.append(f"{path}: question {q['id']}: answer {ans!r} hors des {n} options")
            continue
        out.append(Question(q["id"], q["text"], q["options"], ans, q["explain"],
                            q.get("remedial_lesson_id")))
    return out


def _tp(path: Path, errors: list[str], module: Path) -> Tp | None:
    d = _json(path, errors)
    keys = ["id", "title", "instructions_md", "check", "hints", "timeout_s", "workspace"]
    if d is None or not _fields(d, path, keys, errors):
        return None
    if not isinstance(d["hints"], list) or not d["hints"]:
        errors.append(f"{path}: hints doit contenir au moins un indice")
        return None
    ws = d["workspace"]
    if not isinstance(ws, str) or not ws or PurePath(ws).is_absolute() or ".." in PurePath(ws).parts:
        errors.append(f"{path}: workspace {ws!r} doit être un chemin relatif sans '..'")
        return None
    seed = d.get("seed", [])
    if not isinstance(seed, list) or not all(isinstance(e, str) and e for e in seed):
        errors.append(f"{path}: seed doit être une liste de chemins")
        return None
    root = module.resolve()
    for e in seed:
        p = path.parent / e
        if PurePath(e).is_absolute() or p.is_symlink() or not p.exists() or not p.resolve().is_relative_to(root):
            errors.append(f"{path}: seed {e!r} invalide (doit exister dans le module, sans lien symbolique)")
            return None
    return Tp(**{k: d[k] for k in keys}, seed=seed)


def _safe_id(v) -> bool:
    # ids become file/dir names: reject anything that could escape a directory
    return isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]+", v) is not None


def load_module(path: Path) -> Module:
    path = Path(path)
    errors: list[str] = []
    meta = _json(path / "module.json", errors)
    if meta is None or not _fields(meta, path / "module.json", ["id", "title", "skill", "lessons"], errors):
        raise ModuleError(errors)
    if not _safe_id(meta["id"]):
        errors.append(f"{path / 'module.json'}: id invalide {meta['id']!r} (attendu : lettres, chiffres, _ ou -)")
    lessons = []
    ids = []
    for ref in meta["lessons"]:
        if not _fields(ref, path / "module.json", ["id", "title", "minutes"], errors):
            continue
        lid = ref["id"]
        if not _safe_id(lid):
            errors.append(f"{path / 'module.json'}: id invalide {lid!r} (leçon) (attendu : lettres, chiffres, _ ou -)")
            continue
        ids.append(lid)
        md = path / "lessons" / f"{lid}.md"
        try:
            body = md.read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"{md}: fichier manquant")
            body = ""
        qcm = _qcm(path / "lessons" / f"{lid}.qcm.json", errors)
        tp_file = path / "lessons" / f"{lid}.tp" / "tp.json"
        tp = _tp(tp_file, errors, path) if tp_file.exists() else None
        lessons.append(Lesson(lid, ref["title"], ref["minutes"], body, qcm, tp))
    seen = set()
    for les in lessons:
        for q in les.qcm:
            if q.id in seen:
                errors.append(f"lesson {les.id}: id de question '{q.id}' en double")
            seen.add(q.id)
            if q.remedial_lesson_id is not None and q.remedial_lesson_id not in ids:
                errors.append(f"lesson {les.id}: question {q.id}: remedial_lesson_id inconnu")
    if errors:
        raise ModuleError(errors)
    return Module(meta["id"], meta["title"], meta["skill"], lessons)
