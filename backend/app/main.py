import json
import os
import random
import re
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import llm
from app.auth import BasicAuth, make_security, security_from_env
from app.audio import speak, strip_markdown
from app.boss import attempt_boss, count_attempts
from app import cards as cardlib, exam as examlib, plan as planlib
from app.content import Module, ModuleError, load_module
from app.db import connect
from app.gacha import NoTokens, pull
from app.interview import keyword_grade, load_questions
from app import portfolio, push
from app.progress import award_xp, get_profile, level_for_xp
from app.quests import XP, announce_rest, applicable_kinds, build_daily_quest, complete_step, current_streak, set_imposed_topic
from app.review import INTERVALS, box_counts, due_reviews, record_answer
from app.terminal import exec_ok, register_terminal, strictly_local
from app.tp import run_check, seed_workspace
from app.weekly import build_brief, import_module

HINT_COST = 10
REAL_TIMEOUT = 120  # labo réel : terraform init télécharge un provider
INTERVIEW_XP = 30  # max par question ; seules les améliorations de score rapportent
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


class InterviewIn(BaseModel):
    answer: str = Field(min_length=20, max_length=llm.MAX_EXPLANATION)


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class PushSub(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: PushKeys


class PushOut(BaseModel):
    endpoint: str = Field(max_length=1000)


class HintIn(BaseModel):
    level: int = Field(1, ge=1)


class ImportIn(BaseModel):
    path: str


class CardIn(BaseModel):
    known: bool


class ExamIn(BaseModel):
    answers: dict[str, int] = Field(max_length=100)


class PlanDayIn(BaseModel):
    done: bool


def local_only(request: Request) -> None:
    # peer IP + Host/Origin (anti DNS rebinding / cross-site); opt-in distant: Host autorise (mot de passe exige)
    if not exec_ok(request, request.app.state.remote_hosts):
        raise HTTPException(403, "Réservé à la machine locale")


def require_strictly_local(request: Request) -> None:
    # TP/boss `local_only` : jamais d'exécution distante, même avec FORMATION_REMOTE_EXEC=1
    if not strictly_local(request):
        raise HTTPException(403, "Réservé à la machine locale")


def create_app(db_path: str, content_dir: Path, workspace: Path, static_dir: Path | None = None,
               password: str | None = None, remote_exec: bool = False, allowed_hosts=()) -> FastAPI:
    sec = make_security(password, remote_exec, allowed_hosts)
    content_dir, workspace = Path(content_dir).resolve(), Path(workspace)  # LESSON_DIR absolu : les scripts tournent depuis le workspace
    connect(db_path).close()  # schema must exist at startup
    pool = json.loads((content_dir / "gacha.json").read_text(encoding="utf-8"))
    boss_files = sorted(p for p in (content_dir / "boss").glob("*/boss.json"))
    bosses = {json.loads(f.read_text(encoding="utf-8"))["id"]: f.parent for f in boss_files}
    for f in boss_files:
        if not isinstance(json.loads(f.read_text(encoding="utf-8")).get("local_only", False), bool):
            raise ValueError(f"{f}: local_only doit être un booléen")
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
        # modules ESP (esp1..) après les autres : ils ne changent pas la quête du jour des modules existants
        for d in sorted((content_dir / "modules").glob("*/"), key=lambda d: (d.name.startswith("esp"), d.name)):
            if d.name.startswith(".") or not d.is_dir():
                continue
            try:
                out.append((d, load_module(d)))
            except ModuleError:
                pass
        return sorted(out, key=lambda dm: (dm[0].name.startswith("esp"), dm[1].order))  # tri stable : nom ensuite

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
    def quest(request: Request, minutes: str = Query("30", pattern="^(30|60)$"), db=Depends(get_db)):
        minutes = int(minutes)
        local = strictly_local(request)
        today = date.today()
        mods = modules()
        for _, m in mods:
            q = build_daily_quest(db, m, today, minutes, local)
            if q.steps:
                return asdict(q)
        return asdict(build_daily_quest(db, mods[0][1], today, minutes, local)) if mods else \
            {"day": today, "steps": [], "bonus": None, "imposed_topic": None}

    @app.post("/api/quest/step")
    def quest_step(body: StepIn, request: Request, db=Depends(get_db)):
        if body.kind not in XP:
            raise HTTPException(400, "Type d'étape invalide")
        _, m, les = find_lesson(body.lesson_id)
        if body.kind == "tp" and les.tp:
            if les.tp.local_only:
                require_strictly_local(request)
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

    @app.get("/api/lessons")
    def lessons():
        return [{"id": m.id, "title": m.title, "fiche": m.fiche_md is not None,
                 "lessons": [{"id": les.id, "title": les.title, "minutes": les.minutes} for les in m.lessons]}
                for _, m in modules()]

    @app.get("/api/fiche/{module_id}")
    def fiche(module_id: str):
        for _, m in modules():
            if m.id == module_id and m.fiche_md is not None:
                return {"id": m.id, "title": m.title, "body_md": m.fiche_md}
        raise HTTPException(404, "Fiche inconnue")

    @app.get("/api/lesson/{lesson_id}")
    def lesson(lesson_id: str):
        d, _, les = find_lesson(lesson_id)
        return {
            "id": les.id, "title": les.title, "minutes": les.minutes, "body_md": les.body_md,
            "qcm": [{"id": q.id, "text": q.text, "options": q.options} for q in les.qcm],
            "tp": {"id": les.tp.id, "title": les.tp.title, "instructions_md": les.tp.instructions_md,
                   "timeout_s": les.tp.timeout_s, "real": (d / "lessons" / "_real.sh").is_file()} if les.tp else None,
        }

    @app.get("/api/audio/{name}")
    def audio(name: str):
        lid, ext = name[:-4], name[-4:]
        if ext not in (".mp3", ".wav") or not SAFE_ID.fullmatch(lid):
            raise HTTPException(404, "Audio inconnu")
        _, _, les = find_lesson(lid)
        stem = Path(db_path).parent / "audio" / lid
        out = stem.with_suffix(".mp3")  # pas d'audio mp3 : speak() tente edge-tts puis bascule sur espeak (wav)
        if not out.exists():
            try:
                out = speak(strip_markdown(les.body_md), stem)
            except RuntimeError as e:
                raise HTTPException(503, str(e))
        return FileResponse(out, media_type="audio/mpeg" if out.suffix == ".mp3" else "audio/wav")

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

    @app.get("/api/portfolio.zip", dependencies=[Depends(local_only)])
    def portfolio_zip(db=Depends(get_db)):
        won = [r[0] for r in db.execute("SELECT DISTINCT boss_id FROM boss_attempts WHERE won = 1 ORDER BY boss_id")]
        titles = [json.loads((bosses[b] / "boss.json").read_text(encoding="utf-8"))["title"] for b in won if b in bosses]
        data, _ = portfolio.build_zip(db, get_profile(db), modules(), workspace, titles)
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="portfolio.zip"'})

    @app.get("/api/push/key")
    def push_key(db=Depends(get_db)):
        return {"key": push.vapid(db)[1], "subscribed": push.count_subs(db) > 0}

    @app.post("/api/push/subscribe")
    def push_subscribe(body: PushSub, db=Depends(get_db)):
        if not push.endpoint_ok(body.endpoint):
            raise HTTPException(422, "Service de notification non pris en charge")
        push.subscribe(db, body.model_dump())
        return {"ok": True}

    @app.post("/api/push/unsubscribe")
    def push_unsubscribe(body: PushOut, db=Depends(get_db)):
        push.unsubscribe(db, body.endpoint)
        return {"ok": True}

    @app.post("/api/push/test")
    def push_test(db=Depends(get_db)):
        sent = push.send_all(db, "Formation", "Les rappels fonctionnent.")
        if not sent:
            raise HTTPException(503, "Aucune notification envoyée : abonne-toi d'abord, puis vérifie la connexion du serveur.")
        return {"sent": sent}

    @app.get("/api/interview")
    def interview_list(db=Depends(get_db)):
        best = dict(db.execute("SELECT question_id, best FROM interview").fetchall())
        return {"questions": [{"id": q["id"], "role": q["role"], "question": q["question"], "time_limit": q["time_limit"],
                               "best": best.get(q["id"])} for q in load_questions(content_dir)]}

    @app.post("/api/interview/{qid}")
    def interview_answer(qid: str, body: InterviewIn, db=Depends(get_db)):
        q = next((x for x in load_questions(content_dir) if x["id"] == qid), None)
        if q is None:
            raise HTTPException(404, "Question inconnue")
        labels = [k[0] for k in q["keywords"]]
        try:
            g = {**llm.grade_interview(q["question"], q["model_answer"], labels, body.answer), "mode": "ollama"}
        except llm.LlmUnavailable:  # offline fallback: coarser, but the drill still works
            score, missing = keyword_grade(body.answer, q["keywords"])
            g = {"score": score, "missing": missing, "mode": "mots-clés",
                 "feedback": "Ollama est indisponible : notation approximative par mots-clés."}
        row = db.execute("SELECT best FROM interview WHERE question_id = ?", (qid,)).fetchone()
        best = row[0] if row else 0
        top = max(g["score"], best)
        xp = round(INTERVIEW_XP * top / 100) - round(INTERVIEW_XP * best / 100)
        db.execute("INSERT OR REPLACE INTO interview(question_id, best) VALUES (?, ?)", (qid, top))
        if xp:
            award_xp(db, "entretien", xp)  # commits the score row too
        else:
            db.commit()
        return {**g, "xp": xp, "best": top, "model_answer": q["model_answer"]}

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
    def tp_check(request: Request, tp_id: str, db=Depends(get_db)):
        lesson_dir, _, tp = find_tp(tp_id)
        if tp.local_only:
            require_strictly_local(request)
        r = run_check(tp, workspace, lesson_dir)
        if r.passed:
            db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, '1')", (f"tp_passed:{tp.id}",))
            db.commit()
        return {"passed": r.passed, "output": r.output}

    @app.post("/api/tp/{tp_id}/real", dependencies=[Depends(local_only)])
    def tp_real(request: Request, tp_id: str):
        lesson_dir, _, tp = find_tp(tp_id)
        if tp.local_only:
            require_strictly_local(request)
        if not (lesson_dir.parent / "_real.sh").is_file():
            raise HTTPException(404, "Pas de labo réel pour ce TP")
        r = run_check(replace(tp, check='bash "$LESSON_DIR/../_real.sh"', timeout_s=REAL_TIMEOUT), workspace, lesson_dir)
        return {"passed": r.passed, "output": r.output}

    def studied_cards(db) -> list[cardlib.Card]:
        done = {r[0] for r in db.execute("SELECT lesson_id FROM quest_steps WHERE kind = 'lesson' AND done = 1")}
        return [c for _, m in modules() for les in m.lessons if les.id in done for c in cardlib.lesson_cards(les)]

    @app.get("/api/cards")
    def cards(db=Depends(get_db)):
        return cardlib.session(db, studied_cards(db), date.today())

    @app.post("/api/cards/{card_id}")
    def card_answer(card_id: str, body: CardIn, db=Depends(get_db)):
        if card_id not in {c.id for c in studied_cards(db)}:
            raise HTTPException(404, "Carte inconnue")
        return cardlib.record_card(db, card_id, body.known, date.today())

    @app.get("/api/plan")
    def plan(request: Request, db=Depends(get_db)):
        local = strictly_local(request)
        les = {x.id: x for _, m in modules() for x in m.lessons}
        done = {(r[0], r[1]) for r in db.execute("SELECT kind, lesson_id FROM quest_steps WHERE done = 1")}
        return planlib.status(db, planlib.load_plan(content_dir), date.today(),
                              lambda lid: lid in les and all((k, lid) in done for k in applicable_kinds(les[lid], local)))

    @app.post("/api/plan/start")
    def plan_start(db=Depends(get_db)):
        planlib.start(db, date.today())
        return {"ok": True}

    @app.post("/api/plan/day/{day}")
    def plan_day(day: int, body: PlanDayIn, db=Depends(get_db)):
        if not 1 <= day <= len(planlib.load_plan(content_dir)):
            raise HTTPException(404, "Jour inconnu")
        planlib.mark(db, day, body.done)
        return {"ok": True}

    def find_module(module_id: str) -> Module:
        for _, m in modules():
            if m.id == module_id and examlib.pool(m):
                return m
        raise HTTPException(404, "Module inconnu")

    @app.get("/api/exams")
    def exams(db=Depends(get_db)):
        best = dict(db.execute("SELECT module_id, best FROM exams").fetchall())
        return [{"id": m.id, "title": m.title, "questions": min(examlib.SIZE, len(examlib.pool(m))), "best": best.get(m.id)}
                for _, m in modules() if examlib.pool(m)]

    @app.get("/api/exam/{module_id}")
    def exam(module_id: str, db=Depends(get_db)):
        m = find_module(module_id)
        qs = examlib.draw(m, rng)
        row = db.execute("SELECT best FROM exams WHERE module_id = ?", (m.id,)).fetchone()
        return {"id": m.id, "title": m.title, "duration_s": examlib.SECONDS_PER_QUESTION * len(qs),
                "pass_pct": examlib.PASS_PCT, "best": row[0] if row else None,
                "questions": [{"id": q.id, "text": q.text, "options": q.options} for q in qs]}

    @app.post("/api/exam/{module_id}")
    def exam_submit(module_id: str, body: ExamIn, db=Depends(get_db)):
        m = find_module(module_id)
        try:
            score, detail = examlib.grade(m, body.answers)
        except ValueError as e:
            raise HTTPException(400, str(e))
        for d in detail:
            if not d["correct"]:
                record_answer(db, d["id"], False, date.today())  # les erreurs rejoignent les révisions
        row = db.execute("SELECT best FROM exams WHERE module_id = ?", (m.id,)).fetchone()
        best = row[0] if row else 0
        top = max(score, best)
        xp = round(examlib.EXAM_XP * top / 100) - round(examlib.EXAM_XP * best / 100)
        db.execute("INSERT OR REPLACE INTO exams(module_id, best) VALUES (?, ?)", (m.id, top))
        if xp:
            award_xp(db, m.skill, xp)  # commits the score row too
        else:
            db.commit()
        return {"score": score, "passed": score >= examlib.PASS_PCT, "pass_pct": examlib.PASS_PCT, "best": top,
                "xp": xp, "detail": detail}

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
    def boss_attempt(request: Request, id: str | None = None, db=Depends(get_db)):
        boss_dir, boss = pick_boss(id)
        if boss.get("local_only", False):
            require_strictly_local(request)
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
