import json
import os
import random
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import llm
from app.audio import strip_markdown, synthesize
from app.boss import attempt_boss, count_attempts
from app.content import Module, ModuleError, load_module
from app.db import connect
from app.gacha import NoTokens, pull
from app.progress import award_xp, get_profile, level_for_xp
from app.quests import XP, announce_rest, applicable_kinds, build_daily_quest, complete_step, current_streak, set_imposed_topic
from app.review import due_reviews, record_answer
from app.terminal import _origin_ok, is_local, register_terminal
from app.tp import run_check, seed_workspace
from app.weekly import build_brief, import_module

HINT_COST = 10
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")


class StepIn(BaseModel):
    kind: str
    lesson_id: str


class TopicIn(BaseModel):
    topic: str | None = None


class AnswerIn(BaseModel):
    question_id: str
    chosen: int


class BriefIn(BaseModel):
    topic: str
    format: str


class HintIn(BaseModel):
    level: int = Field(1, ge=1)


class ImportIn(BaseModel):
    path: str


def local_only(request: Request) -> None:
    # peer IP + Host/Origin (anti DNS rebinding / cross-site); _origin_ok only reads .headers
    if not is_local(request.client.host if request.client else None) or not _origin_ok(request):
        raise HTTPException(403, "Réservé à la machine locale")


def create_app(db_path: str, content_dir: Path, workspace: Path, static_dir: Path | None = None) -> FastAPI:
    content_dir, workspace = Path(content_dir), Path(workspace)
    connect(db_path).close()  # schema must exist at startup
    pool = json.loads((content_dir / "gacha.json").read_text(encoding="utf-8"))
    boss_dirs = sorted(p for p in (content_dir / "boss").glob("*/boss.json"))
    boss_dir = boss_dirs[0].parent if boss_dirs else None
    boss = json.loads(boss_dirs[0].read_text(encoding="utf-8")) if boss_dirs else None
    rng = random.Random()
    app = FastAPI()

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        # CSRF guard: a browser-sent Origin on a write must match Host; curl/TestClient send none
        origin = request.headers.get("origin")
        if (request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api")
                and origin is not None and urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower()):
            return JSONResponse({"detail": "Origine interdite"}, status_code=403)
        return await call_next(request)

    def get_db():
        db = connect(db_path)
        try:
            yield db
        finally:
            db.close()

    def modules() -> list[tuple[Path, Module]]:
        # scanned per request so a weekly import shows up immediately; broken modules are skipped
        out = []
        for d in sorted((content_dir / "modules").glob("*/")):
            if d.name.startswith(".") or not d.is_dir():
                continue
            try:
                out.append((d, load_module(d)))
            except ModuleError:
                pass
        return out

    def find_lesson(lid: str):
        for d, m in modules():
            for les in m.lessons:
                if les.id == lid:
                    return d, m, les
        raise HTTPException(404, "Leçon inconnue")

    def find_question(qid: str):
        for _, m in modules():
            for les in m.lessons:
                for q in les.qcm:
                    if q.id == qid:
                        return q
        raise HTTPException(404, "Question inconnue")

    def find_tp(tid: str):
        for d, m in modules():
            for les in m.lessons:
                if les.tp and les.tp.id == tid:
                    return d / "lessons" / f"{les.id}.tp", m, les.tp
        raise HTTPException(404, "TP inconnu")

    @app.get("/api/quest")
    def quest(minutes: str = Query("30", pattern="^(30|60)$"), db=Depends(get_db)):
        minutes = int(minutes)
        today = date.today()
        mods = modules()
        for _, m in mods:
            q = build_daily_quest(db, m, today, minutes)
            if q.steps:
                return asdict(q)
        return asdict(build_daily_quest(db, mods[0][1], today, minutes)) if mods else \
            {"day": today, "steps": [], "bonus": None, "imposed_topic": None}

    @app.post("/api/quest/step")
    def quest_step(body: StepIn, db=Depends(get_db)):
        if body.kind not in XP:
            raise HTTPException(400, "Type d'étape invalide")
        _, m, les = find_lesson(body.lesson_id)
        if body.kind == "tp" and les.tp:
            if db.execute("SELECT 1 FROM settings WHERE key = ?", (f"tp_passed:{les.tp.id}",)).fetchone() is None:
                raise HTTPException(409, "TP non validé : lancez la vérification d'abord")
        complete_step(db, date.today(), body.kind, body.lesson_id, m.skill, applicable_kinds(les))
        return {"ok": True}

    @app.post("/api/rest")
    def rest(db=Depends(get_db)):
        announce_rest(db, date.today())
        return {"ok": True}

    @app.post("/api/topic")
    def topic(body: TopicIn, db=Depends(get_db)):
        set_imposed_topic(db, body.topic, date.today())
        return {"ok": True}

    @app.get("/api/lesson/{lesson_id}")
    def lesson(lesson_id: str):
        _, _, les = find_lesson(lesson_id)
        return {
            "id": les.id, "title": les.title, "minutes": les.minutes, "body_md": les.body_md,
            "qcm": [{"id": q.id, "text": q.text, "options": q.options} for q in les.qcm],
            "tp": {"id": les.tp.id, "title": les.tp.title, "instructions_md": les.tp.instructions_md,
                   "timeout_s": les.tp.timeout_s} if les.tp else None,
        }

    @app.get("/api/audio/{name}")
    def audio(name: str):
        lid = name[:-4] if name.endswith(".wav") else ""
        if not SAFE_ID.fullmatch(lid):
            raise HTTPException(404, "Audio inconnu")
        _, _, les = find_lesson(lid)
        out = Path(db_path).parent / "audio" / f"{lid}.wav"
        if not out.exists():
            tmp = out.with_name(out.name + ".tmp")
            try:
                synthesize(strip_markdown(les.body_md), tmp)
                os.replace(tmp, out)
            except RuntimeError as e:
                raise HTTPException(503, str(e))
            finally:
                tmp.unlink(missing_ok=True)
        return FileResponse(out, media_type="audio/wav")

    @app.post("/api/qcm/answer")
    def qcm_answer(body: AnswerIn, db=Depends(get_db)):
        q = find_question(body.question_id)
        if not 0 <= body.chosen < len(q.options):
            raise HTTPException(400, "Choix hors des options")
        correct = body.chosen == q.answer
        record_answer(db, q.id, correct, date.today())
        return {
            "correct": correct,
            "explanation": q.explain if correct else llm.explain_error(q, body.chosen),
            "remedial_lesson_id": None if correct else q.remedial_lesson_id,
        }

    @app.get("/api/reviews")
    def reviews(db=Depends(get_db)):
        return {"due": due_reviews(db, date.today())}

    @app.post("/api/tp/{tp_id}/hint", dependencies=[Depends(local_only)])
    def tp_hint(tp_id: str, body: HintIn, db=Depends(get_db)):
        _, m, tp = find_tp(tp_id)
        award_xp(db, m.skill, -HINT_COST)
        return {"hint": llm.hint(tp, body.level, ""), "cost": HINT_COST}

    @app.post("/api/tp/{tp_id}/start", dependencies=[Depends(local_only)])
    def tp_start(tp_id: str):
        lesson_dir, _, tp = find_tp(tp_id)
        try:
            seed_workspace(tp, lesson_dir, workspace)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return {"dir": tp.workspace}

    @app.post("/api/tp/{tp_id}/check", dependencies=[Depends(local_only)])
    def tp_check(tp_id: str, db=Depends(get_db)):
        lesson_dir, _, tp = find_tp(tp_id)
        r = run_check(tp, workspace, lesson_dir)
        if r.passed:
            db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, '1')", (f"tp_passed:{tp.id}",))
            db.commit()
        return {"passed": r.passed, "output": r.output}

    @app.get("/api/team")
    def team(db=Depends(get_db)):
        p = get_profile(db)
        inv = [dict(r) for r in db.execute("SELECT item_id, name, type, rarity, obtained_at FROM inventory")]
        return {"xp": p.total_xp, "level": level_for_xp(p.total_xp), "rank": p.rank, "skills": p.skills,
                "skill_levels": {k: level_for_xp(v) for k, v in p.skills.items()}, "tokens": p.tokens, "streak": current_streak(db, date.today()), "inventory": inv}

    @app.post("/api/gacha/pull")
    def gacha_pull(db=Depends(get_db)):
        try:
            return pull(db, pool, rng)
        except NoTokens:
            raise HTTPException(409, "Pas de jeton")

    @app.get("/api/boss")
    def boss_info(db=Depends(get_db)):
        if boss is None:
            raise HTTPException(404, "Aucun boss")
        return {"title": boss["title"], "phases": [{"label": p["label"]} for p in boss["phases"]],
                "attempts": count_attempts(db)}

    @app.post("/api/boss/attempt", dependencies=[Depends(local_only)])
    def boss_attempt(db=Depends(get_db)):
        if boss is None:
            raise HTTPException(404, "Aucun boss")
        r = attempt_boss(db, boss, workspace, boss_dir)
        return {**asdict(r), "attempts": count_attempts(db)}

    @app.post("/api/weekly/brief")
    def weekly_brief(body: BriefIn, db=Depends(get_db)):
        weak = [r[0] for r in db.execute("SELECT question_id FROM mistakes ORDER BY question_id")]
        return {"brief": build_brief(get_profile(db), body.topic, body.format, weak)}

    @app.post("/api/weekly/import", dependencies=[Depends(local_only)])
    def weekly_import(body: ImportIn):
        try:
            final = import_module(Path(body.path), content_dir / "modules")
        except ModuleError as e:
            return JSONResponse({"errors": e.errors}, status_code=422)
        return {"module_id": final.name}

    register_terminal(app, workspace)

    static = static_dir if static_dir is not None else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    return app


def app_factory() -> FastAPI:
    home = Path.home() / ".formation"
    workspace = Path(os.environ.get("FORMATION_WORKSPACE", home / "workspace"))
    workspace.mkdir(parents=True, exist_ok=True)
    db = Path(os.environ.get("FORMATION_DB", home / "formation.db"))
    db.parent.mkdir(parents=True, exist_ok=True)
    default_content = Path(__file__).resolve().parents[2] / "content"
    return create_app(str(db), Path(os.environ.get("FORMATION_CONTENT", default_content)), workspace)
