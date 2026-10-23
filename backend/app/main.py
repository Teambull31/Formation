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
from app.auth import BasicAuth, make_security, security_from_env
from app.audio import strip_markdown, synthesize
from app.boss import attempt_boss, count_attempts
from app.content import Module, ModuleError, load_module
from app.db import connect
from app.gacha import NoTokens, pull
from app.progress import award_xp, get_profile, level_for_xp
from app.quests import XP, announce_rest, applicable_kinds, build_daily_quest, complete_step, current_streak, set_imposed_topic
from app.review import INTERVALS, box_counts, due_reviews, record_answer
from app.terminal import exec_ok, register_terminal
from app.tp import run_check, seed_workspace
from app.weekly import build_brief, import_module

HINT_COST = 10
FEYNMAN_XP = 60  # max par leçon ; seules les améliorations de score rapportent
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


class FeynmanIn(BaseModel):
    explanation: str = Field(min_length=40, max_length=llm.MAX_EXPLANATION)


class HintIn(BaseModel):
    level: int = Field(1, ge=1)


class ImportIn(BaseModel):
    path: str


def local_only(request: Request) -> None:
    # peer IP + Host/Origin (anti DNS rebinding / cross-site); opt-in distant: Host autorise (mot de passe exige)
    if not exec_ok(request, request.app.state.remote_hosts):
        raise HTTPException(403, "Réservé à la machine locale")


def create_app(db_path: str, content_dir: Path, workspace: Path, static_dir: Path | None = None,
               password: str | None = None, remote_exec: bool = False, allowed_hosts=()) -> FastAPI:
    sec = make_security(password, remote_exec, allowed_hosts)
    content_dir, workspace = Path(content_dir), Path(workspace)
    connect(db_path).close()  # schema must exist at startup
    pool = json.loads((content_dir / "gacha.json").read_text(encoding="utf-8"))
    boss_files = sorted(p for p in (content_dir / "boss").glob("*/boss.json"))
    bosses = {json.loads(f.read_text(encoding="utf-8"))["id"]: f.parent for f in boss_files}
    rng = random.Random()
    app = FastAPI()
    app.state.remote_hosts = sec.allowed_hosts

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
        xp = None
        if body.kind == "qcm" and les.qcm:  # XP scales with first-try right answers; wrong ones go to the reviews
            right = sum(1 for q in les.qcm if (r := db.execute(
                "SELECT correct FROM qcm_first WHERE question_id = ?", (q.id,)).fetchone()) and r[0])
            xp = round(XP["qcm"] * right / len(les.qcm))
        complete_step(db, date.today(), body.kind, body.lesson_id, m.skill, applicable_kinds(les), xp)
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
        db.execute("INSERT OR IGNORE INTO qcm_first(question_id, correct) VALUES (?, ?)", (q.id, int(correct)))
        db.commit()  # record_answer returns early on a right answer with nothing tracked
        record_answer(db, q.id, correct, date.today())
        return {
            "correct": correct,
            "explanation": q.explain if correct else llm.explain_error(q, body.chosen),
            "remedial_lesson_id": None if correct else q.remedial_lesson_id,
        }

    @app.get("/api/reviews")
    def reviews(db=Depends(get_db)):
        due = []
        boxes = dict(db.execute("SELECT question_id, box FROM mistakes").fetchall())
        questions = []
        for qid in due_reviews(db, date.today()):
            try:
                q = find_question(qid)
            except HTTPException:  # question removed from content: not due anymore
                continue
            due.append(qid)
            questions.append({"id": q.id, "text": q.text, "options": q.options, "box": boxes.get(qid, 0)})
        return {"due": due, "questions": questions, "boxes": box_counts(db), "intervals": INTERVALS}

    @app.post("/api/feynman/{lesson_id}", dependencies=[Depends(local_only)])
    def feynman(lesson_id: str, body: FeynmanIn, db=Depends(get_db)):
        _, m, les = find_lesson(lesson_id)
        try:
            g = llm.grade_explanation(les.title, les.body_md, body.explanation)
        except llm.LlmUnavailable as e:
            raise HTTPException(503, str(e))
        row = db.execute("SELECT best FROM feynman WHERE lesson_id = ?", (les.id,)).fetchone()
        best = row[0] if row else 0
        top = max(g["score"], best)
        xp = round(FEYNMAN_XP * top / 100) - round(FEYNMAN_XP * best / 100)
        db.execute("INSERT OR REPLACE INTO feynman(lesson_id, best) VALUES (?, ?)", (les.id, top))
        if xp:
            award_xp(db, m.skill, xp)  # commits the score row too
        else:
            db.commit()
        return {**g, "xp": xp, "best": top}

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
        return {"xp": p.total_xp, "level": level_for_xp(p.total_xp), "rank": p.rank, "rank_capped": p.rank_capped, "skills": p.skills,
                "skill_levels": {k: level_for_xp(v) for k, v in p.skills.items()}, "tokens": p.tokens, "streak": current_streak(db, date.today()), "inventory": inv}

    @app.post("/api/gacha/pull")
    def gacha_pull(db=Depends(get_db)):
        try:
            return pull(db, pool, rng)
        except NoTokens:
            raise HTTPException(409, "Pas de jeton")

    def pick_boss(boss_id: str | None):
        # no id = first boss (sorted dir name); several bosses can ship, one per module
        if not bosses:
            raise HTTPException(404, "Aucun boss")
        bid = boss_id if boss_id is not None else next(iter(bosses))
        if bid not in bosses:
            raise HTTPException(404, "Boss inconnu")
        return bosses[bid], json.loads((bosses[bid] / "boss.json").read_text(encoding="utf-8"))

    @app.get("/api/boss")
    def boss_info(id: str | None = None, db=Depends(get_db)):
        _, boss = pick_boss(id)
        return {"id": boss["id"], "title": boss["title"], "phases": [{"label": p["label"]} for p in boss["phases"]],
                "attempts": count_attempts(db, boss["id"]),
                "bosses": [{"id": b, "title": json.loads((d / "boss.json").read_text(encoding="utf-8"))["title"]}
                           for b, d in bosses.items()]}

    @app.post("/api/boss/attempt", dependencies=[Depends(local_only)])
    def boss_attempt(id: str | None = None, db=Depends(get_db)):
        boss_dir, boss = pick_boss(id)
        r = attempt_boss(db, boss, workspace, boss_dir)
        return {**asdict(r), "attempts": count_attempts(db, boss["id"])}

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

    register_terminal(app, workspace, sec.allowed_hosts)

    static = static_dir if static_dir is not None else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    if sec.password is not None:
        app.add_middleware(BasicAuth, password=sec.password)  # ajouté en dernier = le plus externe
    return app


def app_factory() -> FastAPI:
    sec = security_from_env()  # avant tout effet de bord disque
    home = Path.home() / ".formation"
    workspace = Path(os.environ.get("FORMATION_WORKSPACE", home / "workspace"))
    workspace.mkdir(parents=True, exist_ok=True)
    db = Path(os.environ.get("FORMATION_DB", home / "formation.db"))
    db.parent.mkdir(parents=True, exist_ok=True)
    default_content = Path(__file__).resolve().parents[2] / "content"
    return create_app(str(db), Path(os.environ.get("FORMATION_CONTENT", default_content)), workspace,
                      password=sec.password, remote_exec=sec.remote_exec, allowed_hosts=sec.allowed_hosts)
