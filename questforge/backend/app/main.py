from __future__ import annotations
import json
import logging
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Literal
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import connect
from app.content import load_module, Module, Lesson, Question, Tp, ModuleError
from app.progress import get_profile, award_xp
from app.quests import (
    build_daily_quest,
    complete_step,
    announce_rest,
    set_imposed_topic,
    current_streak,
    activity_history,
)
from app.review import record_answer, due_reviews, weak_notions, box_counts, REVIEW_XP
from app.llm import hint as get_llm_hint, explain_error as get_llm_explain
from app.tp import run_check
from app.terminal import register_terminal
from app.security import is_trusted
from app.gacha import pull, add_tokens, NoTokens
from app.boss import attempt_boss, count_attempts
from app.audio import synthesize
from app.weekly import build_brief, import_module

logger = logging.getLogger(__name__)

BOSS_FIRST_WIN_XP = 150

# Racine du projet (contient backend/ et content/), indépendante du dossier de lancement.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def local_only(request: Request):
    client_host = request.client.host if request.client else None
    if not is_trusted(client_host, request.headers):
        raise HTTPException(status_code=403, detail="Accès réservé à localhost")


class StepRequest(BaseModel):
    kind: Literal["lesson", "qcm", "tp", "bonus"]
    lesson_id: str


class TopicRequest(BaseModel):
    topic: str | None = None


class QcmAnswerRequest(BaseModel):
    question_id: str
    chosen: int


class BriefRequest(BaseModel):
    topic: str
    format: str


class BossAttemptRequest(BaseModel):
    boss_id: str | None = None
    crisis_mode: bool = False


class ModuleSwitchRequest(BaseModel):
    moduleId: str


class ImportRequest(BaseModel):
    path: str


def create_app(
    db_path: str = "app.db",
    content_dir: Path | str = "content",
    workspace: Path | str = "workspace",
) -> FastAPI:
    content_path = Path(content_dir).resolve()
    ws_path = Path(workspace).resolve()
    ws_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="QuestForge API")

    # Audio cache dir
    audio_cache = content_path / ".audio_cache"
    audio_cache.mkdir(parents=True, exist_ok=True)

    def get_db():
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    # Exception handlers
    @app.exception_handler(NoTokens)
    async def no_tokens_handler(request: Request, exc: NoTokens):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ModuleError)
    async def module_error_handler(request: Request, exc: ModuleError):
        return JSONResponse(status_code=422, content={"errors": exc.errors})

    # Cache/Store modules
    def get_modules() -> list[Module]:
        mods: list[Module] = []
        modules_dir = content_path / "modules"
        if modules_dir.exists():
            for entry in sorted(modules_dir.iterdir()):
                if entry.is_dir() and (entry / "module.json").exists():
                    try:
                        mods.append(load_module(entry))
                    except Exception as exc:
                        logger.warning("Module ignoré (%s) : %s", entry.name, exc)
        return mods

    def active_module(db, mods: list[Module]) -> Module:
        """Parcours choisi par l'apprenant (persisté), sinon le premier module disponible."""
        row = db.execute("SELECT value FROM settings WHERE key = 'active_module_id'").fetchone()
        if row:
            for mod in mods:
                if mod.id == row["value"]:
                    return mod
        return mods[0]

    def find_lesson(lesson_id: str) -> tuple[Lesson, Module] | None:
        for mod in get_modules():
            for les in mod.lessons:
                if les.id == lesson_id:
                    return les, mod
        return None

    def find_question(q_id: str) -> tuple[Question, Lesson, Module] | None:
        for mod in get_modules():
            for les in mod.lessons:
                for q in les.qcm:
                    if q.id == q_id:
                        return q, les, mod
        return None

    def find_tp(tp_id: str) -> tuple[Tp, Lesson, Module] | None:
        for mod in get_modules():
            for les in mod.lessons:
                if les.tp and les.tp.id == tp_id:
                    return les.tp, les, mod
        return None

    def get_gacha_pool() -> list[dict]:
        gacha_file = content_path / "gacha.json"
        if gacha_file.exists():
            try:
                return json.loads(gacha_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def load_bosses() -> list[tuple[dict, Path]]:
        bosses: list[tuple[dict, Path]] = []
        bosses_dir = content_path / "bosses"
        if bosses_dir.exists():
            for b_dir in sorted(bosses_dir.iterdir()):
                boss_file = b_dir / "boss.json"
                if b_dir.is_dir() and boss_file.exists():
                    try:
                        bosses.append((json.loads(boss_file.read_text(encoding="utf-8")), b_dir))
                    except Exception as exc:
                        logger.warning("Boss ignoré (%s) : %s", b_dir.name, exc)
        return bosses

    def find_boss(boss_id: str | None) -> tuple[dict, Path]:
        bosses = load_bosses()
        if not bosses:
            raise HTTPException(status_code=404, detail="Aucun boss disponible")
        for boss, b_dir in bosses:
            if boss.get("id") == boss_id:
                return boss, b_dir
        return bosses[0]

    def public_boss(boss: dict) -> dict:
        """Vue exposée à l'interface : jamais la commande de vérification, seulement sa description."""
        return {
            "id": boss.get("id"),
            "title": boss.get("title", ""),
            "description": boss.get("description", ""),
            "avatar": boss.get("avatar", "👾"),
            "color": boss.get("color", "from-rose-500/20 to-red-950/40 border-rose-700/50"),
            "phases": [
                {
                    "pattern_id": ph.get("pattern_id"),
                    "label": ph.get("label", ""),
                    "check": ph.get("check_label", "Vérification automatique de votre dossier de travail"),
                    "remedial_lesson_id": ph.get("remedial_lesson_id"),
                }
                for ph in boss.get("phases", [])
            ],
        }

    # Register terminal
    register_terminal(app, ws_path)

    # Quest routes
    @app.get("/api/quest")
    def get_quest(minutes: int = 30, db=Depends(get_db)):
        mods = get_modules()
        if not mods:
            # Fallback placeholder if no modules found
            default_mod = Module(id="default", title="Socle Initial", skill="devops", lessons=[])
        else:
            default_mod = active_module(db, mods)

        if not default_mod.lessons:
            raise HTTPException(status_code=503, detail=f"Aucun module de contenu disponible dans {content_path / 'modules'}")

        today = date.today()
        quest = build_daily_quest(db, default_mod, today, minutes=minutes)
        streak = current_streak(db, today)
        profile = get_profile(db)

        return {
            "day": quest.day.isoformat(),
            "steps": [
                {
                    "kind": s.kind,
                    "lesson_id": s.lesson_id,
                    "minutes": s.minutes,
                    "xp": s.xp,
                    "done": s.done,
                }
                for s in quest.steps
            ],
            "bonus": (
                {
                    "kind": quest.bonus.kind,
                    "lesson_id": quest.bonus.lesson_id,
                    "minutes": quest.bonus.minutes,
                    "xp": quest.bonus.xp,
                    "done": quest.bonus.done,
                }
                if quest.bonus
                else None
            ),
            "imposed_topic": quest.imposed_topic,
            "streak": streak,
            "profile": {
                "total_xp": profile.total_xp,
                "rank": profile.rank,
                "skills": profile.skills,
                "tokens": profile.tokens,
                "active_module_id": default_mod.id,
            },
            "dueReviewsCount": len(due_reviews(db, today)),
            "activityHistory": activity_history(db, today),
        }

    @app.post("/api/quest/step")
    def post_step(payload: StepRequest, db=Depends(get_db)):
        today = date.today()
        # Find skill associated with lesson
        found = find_lesson(payload.lesson_id)
        if not found:
            raise HTTPException(status_code=404, detail="Leçon introuvable")
        skill = found[1].skill
        newly_awarded = complete_step(db, today, payload.kind, payload.lesson_id, skill=skill)

        # Jeton de gacha : une fois, quand la dernière étape requise de la leçon est validée.
        tokens_awarded = 0
        if newly_awarded:
            lesson = found[0]
            required = {"lesson", "qcm"} | ({"tp"} if lesson.tp else set())
            done = {
                r["kind"]
                for r in db.execute("SELECT kind FROM quest_steps WHERE lesson_id = ?", (lesson.id,))
            }
            if payload.kind in required and required <= done:
                add_tokens(db, 1)
                tokens_awarded = 1
        return {"ok": True, "alreadyCompleted": not newly_awarded, "tokensAwarded": tokens_awarded}

    @app.get("/api/modules")
    def get_module_list():
        return [
            {
                "id": mod.id,
                "title": mod.title,
                "skill": mod.skill,
                "description": mod.description,
                "icon": mod.icon,
                "lessonsCount": len(mod.lessons),
                "totalMinutes": sum(les.minutes for les in mod.lessons),
            }
            for mod in get_modules()
        ]

    @app.post("/api/module/switch")
    def post_module_switch(payload: ModuleSwitchRequest, db=Depends(get_db)):
        if not any(mod.id == payload.moduleId for mod in get_modules()):
            raise HTTPException(status_code=404, detail="Parcours introuvable")
        db.execute(
            """
            INSERT INTO settings (key, value) VALUES ('active_module_id', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (payload.moduleId,),
        )
        db.commit()
        return {"ok": True}

    @app.post("/api/rest")
    def post_rest(db=Depends(get_db)):
        today = date.today()
        announce_rest(db, today)
        return {"ok": True}

    @app.post("/api/topic")
    def post_topic(payload: TopicRequest, db=Depends(get_db)):
        set_imposed_topic(db, payload.topic)
        return {"ok": True}

    # Lesson routes
    @app.get("/api/lesson/{lesson_id}")
    def get_lesson(lesson_id: str):
        found = find_lesson(lesson_id)
        if not found:
            raise HTTPException(status_code=404, detail="Leçon introuvable")
        les, mod = found

        # Ensure answer is not leaked in QCM
        sanitized_qcm = [
            {
                "id": q.id,
                "text": q.text,
                "options": q.options,
                "explain": q.explain,
                "remedial_lesson_id": q.remedial_lesson_id,
            }
            for q in les.qcm
        ]

        tp_info = None
        if les.tp:
            tp_info = {
                "id": les.tp.id,
                "title": les.tp.title,
                "instructions_md": les.tp.instructions_md,
                "timeout_s": les.tp.timeout_s,
                "total_hints": len(les.tp.hints),
            }

        return {
            "id": les.id,
            "title": les.title,
            "module_id": mod.id,
            "module_title": mod.title,
            "skill": mod.skill,
            "minutes": les.minutes,
            "body_md": les.body_md,
            "qcm": sanitized_qcm,
            "tp": tp_info,
        }

    @app.get("/api/audio/{lesson_id}.wav")
    def get_audio(lesson_id: str):
        found = find_lesson(lesson_id)
        if not found:
            raise HTTPException(status_code=404, detail="Leçon introuvable")
        les, _ = found

        wav_path = audio_cache / f"{lesson_id}.wav"
        if not wav_path.exists():
            try:
                synthesize(les.body_md, wav_path)
            except (OSError, subprocess.CalledProcessError) as exc:
                wav_path.unlink(missing_ok=True)
                logger.warning("Synthèse vocale indisponible : %s", exc)
                raise HTTPException(
                    status_code=503,
                    detail="Synthèse vocale indisponible : installez espeak-ng pour activer l'audio.",
                )

        return FileResponse(
            wav_path,
            media_type="audio/wav",
            headers={"Content-Disposition": f'inline; filename="{lesson_id}.wav"'},
        )

    # QCM and reviews
    @app.post("/api/qcm/answer")
    def answer_qcm(payload: QcmAnswerRequest, db=Depends(get_db)):
        found = find_question(payload.question_id)
        if not found:
            raise HTTPException(status_code=404, detail="Question introuvable")
        q, _, mod = found

        if not 0 <= payload.chosen < len(q.options):
            raise HTTPException(status_code=422, detail="Option de réponse invalide")

        today = date.today()
        correct = (payload.chosen == q.answer)
        review_success = record_answer(db, q.id, correct, today)
        xp_awarded = 0
        if review_success:
            award_xp(db, mod.skill, REVIEW_XP)
            xp_awarded = REVIEW_XP

        if correct:
            explanation = q.explain
        else:
            explanation = get_llm_explain(q, payload.chosen)

        return {
            "correct": correct,
            "explanation": explanation,
            "remedial_lesson_id": q.remedial_lesson_id,
            "xpAwarded": xp_awarded,
        }

    @app.get("/api/reviews")
    def get_reviews(db=Depends(get_db)):
        today = date.today()
        due_ids = due_reviews(db, today)
        boxes = {r["question_id"]: r["box"] for r in db.execute("SELECT question_id, box FROM mistakes")}
        reviews = []
        for qid in due_ids:
            found = find_question(qid)
            if found:
                q, les, mod = found
                reviews.append({
                    "id": q.id,
                    "text": q.text,
                    "options": q.options,
                    "lesson_id": les.id,
                    "module_title": mod.title,
                    "remedial_lesson_id": q.remedial_lesson_id,
                    "box": boxes.get(qid, 0),
                })
        return {"due": due_ids, "reviews": reviews, "boxesCount": box_counts(db)}

    # TP routes
    @app.get("/api/tp/{tp_id}/hint")
    def get_tp_hint(tp_id: str, level: int = 1, db=Depends(get_db)):
        found = find_tp(tp_id)
        if not found:
            raise HTTPException(status_code=404, detail="TP introuvable")
        tp, _, mod = found

        # Retrait de 10 XP
        award_xp(db, mod.skill, -10)

        hint_text = get_llm_hint(tp, level, "")
        return {
            "hint": hint_text,
            "level": level,
            "xp_cost": 10,
        }

    @app.post("/api/tp/{tp_id}/check", dependencies=[Depends(local_only)])
    def check_tp(tp_id: str):
        found = find_tp(tp_id)
        if not found:
            raise HTTPException(status_code=404, detail="TP introuvable")
        tp, les, mod = found
        les_dir = content_path / "modules" / mod.id / "lessons"
        res = run_check(tp, ws_path, les_dir)
        return {
            "passed": res.passed,
            "output": res.output,
        }

    # Team & Gacha
    @app.get("/api/team")
    def get_team(db=Depends(get_db)):
        profile = get_profile(db)
        inv_rows = db.execute("SELECT item_id, name, type, rarity, count FROM inventory").fetchall()
        inventory = [dict(r) for r in inv_rows]
        pool = get_gacha_pool()
        return {
            "profile": {
                "total_xp": profile.total_xp,
                "rank": profile.rank,
                "skills": profile.skills,
                "tokens": profile.tokens,
            },
            "inventory": inventory,
            "pool_size": len(pool),
        }

    @app.post("/api/gacha/pull")
    def do_gacha_pull(db=Depends(get_db)):
        pool = get_gacha_pool()
        if not pool:
            raise HTTPException(status_code=500, detail="Pool de gacha indisponible")
        item = pull(db, pool)
        profile = get_profile(db)
        return {
            "item": item,
            "tokens": profile.tokens,
        }

    # Boss routes
    @app.get("/api/bosses")
    def list_bosses():
        return [public_boss(boss) for boss, _ in load_bosses()]

    @app.get("/api/boss")
    def get_boss_info(id: str | None = None, db=Depends(get_db)):
        boss, _ = find_boss(id)
        attempts = count_attempts(db, boss.get("id"))
        history_rows = db.execute(
            """
            SELECT won, phase_reached, failed_pattern, remedial_lesson_id, created_at
            FROM boss_attempts
            WHERE boss_id = ?
            ORDER BY id DESC LIMIT 5
            """,
            (boss.get("id"),),
        ).fetchall()
        return {
            "boss": public_boss(boss),
            "attempts_count": attempts,
            "history": [dict(r) for r in history_rows],
        }

    @app.post("/api/boss/attempt", dependencies=[Depends(local_only)])
    def post_boss_attempt(payload: BossAttemptRequest | None = None, db=Depends(get_db)):
        boss, boss_dir = find_boss(payload.boss_id if payload else None)
        boss_id = boss.get("id")
        prior_wins = db.execute(
            "SELECT COUNT(*) AS c FROM boss_attempts WHERE boss_id = ? AND won = 1", (boss_id,)
        ).fetchone()["c"]
        res = attempt_boss(db, boss, ws_path, boss_dir)

        # Récompense à la première victoire seulement : rejouer le boss ne la redonne pas.
        xp_awarded = tokens_awarded = 0
        if res.won and prior_wins == 0:
            award_xp(db, boss.get("skill", "general"), BOSS_FIRST_WIN_XP)
            add_tokens(db, 1)
            xp_awarded, tokens_awarded = BOSS_FIRST_WIN_XP, 1
        return {
            "won": res.won,
            "phase_reached": res.phase_reached,
            "failed_pattern": res.failed_pattern,
            "remedial_lesson_id": res.remedial_lesson_id,
            "xpAwarded": xp_awarded,
            "tokensAwarded": tokens_awarded,
        }

    # Weekly prep
    @app.post("/api/weekly/brief")
    def post_weekly_brief(payload: BriefRequest, db=Depends(get_db)):
        profile = get_profile(db)
        weak_ids = weak_notions(db)
        brief_text = build_brief(profile, payload.topic, payload.format, weak_ids)
        return {"brief": brief_text}

    @app.post("/api/weekly/import", dependencies=[Depends(local_only)])
    def post_weekly_import(payload: ImportRequest):
        src_path = Path(payload.path)
        dest_root = content_path / "modules"
        res = import_module(src_path, dest_root)
        return {"ok": True, "module_id": res.name}

    # Serve static frontend if present
    frontend_dist = Path("frontend/dist")
    if not frontend_dist.exists():
        frontend_dist = Path("dist")

    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


# Default instance for uvicorn
# Données d'exécution (base SQLite, dossier de travail des TP) : QUESTFORGE_DATA_DIR, sinon le dossier courant.
DATA_DIR = Path(os.environ.get("QUESTFORGE_DATA_DIR", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = create_app(
    db_path=str(DATA_DIR / "questforge.db"),
    content_dir=os.environ.get("QUESTFORGE_CONTENT_DIR", PROJECT_ROOT / "content"),
    workspace=DATA_DIR / "workspace",
)
