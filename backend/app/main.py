import hashlib
import json
import os
import random
import re
import subprocess
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import llm
from app.auth import BasicAuth, make_security, security_from_env
from app.audio import fiche_speech, speak, stale, strip_markdown
from app.boss import attempt_boss, count_attempts
from app import cards as cardlib, exam as examlib, plan as planlib
from app.content import Module, ModuleError, load_module
from app.db import connect
from app.gacha import NoTokens, pull
from app.interview import keyword_grade, load_questions
from app import learn, portfolio, push
from app.tp import child_env
from app.progress import award_xp, get_profile, level_for_xp
from app.quests import (XP, Quest, advanced, announce_rest, applicable_kinds, build_daily_quest, complete_step, current_streak,
                        pending_tps, set_imposed_topic, week_status)
from app.review import INTERVALS, box_counts, due_reviews, record_answer
from app.terminal import exec_ok, register_terminal, strictly_local
from app.tp import run_check, seed_workspace
from app.weekly import build_brief, import_module

HINT_COST = 10
REAL_TIMEOUT = 120  # labo réel : terraform init télécharge un provider
INTERVIEW_XP = 30  # max par question ; seules les améliorations de score rapportent
REVIEW_XP = 15  # toutes les révisions du jour faites (une fois par jour)
WEAK_MAX = 5
AHEAD = 3  # questions proposées d'avance quand rien n'est dû
KEYS_MAX = 6  # « À retenir » en fin de leçon
MISSION_XP = 200  # mission réelle sur un de tes dépôts
ARTICLE_XP = 50
MISSION_TIMEOUT = 120
RELISTEN_DAYS = [1, 7, 30]  # réécoute espacée d'un épisode après la 1re écoute
FEYNMAN_XP = 60  # max par leçon ; seules les améliorations de score rapportent
REVISION_MAX = 15  # questions par catégorie : environ 10 minutes d'écoute
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")


class StepIn(BaseModel):
    kind: str
    lesson_id: str


class TopicIn(BaseModel):
    topic: str | None = None


class AnswerIn(BaseModel):
    question_id: str
    chosen: int
    confident: bool | None = None  # « sûr » / « je devine », facultatif


class OralIn(BaseModel):
    kind: str = Field(pattern="^(card|qcm)$")
    id: str = Field(max_length=200)
    transcript: str = Field(max_length=2000)


class PanneIn(BaseModel):
    symptom: str = Field(min_length=5, max_length=300)
    cause: str = Field(min_length=3, max_length=300)
    fix: str = Field(min_length=3, max_length=500)


class UnclearIn(BaseModel):
    lesson_id: str = Field(min_length=1, max_length=64)
    excerpt: str = Field(min_length=1, max_length=200)


class RephraseIn(BaseModel):
    text: str = Field(min_length=20, max_length=8000)


class PerDayIn(BaseModel):
    per_day: int = Field(ge=0, le=50)


class CueIn(BaseModel):
    cue: str = Field(max_length=120)


class CertIn(BaseModel):
    key: str | None = None
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class ArticleIn(BaseModel):
    text: str = Field(min_length=200, max_length=20000)


class ProofIn(BaseModel):
    proof: str = Field(pattern=r"^https://github\.com/[\w.-]+/[\w.-]+/\S+$", max_length=500)


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


class HourIn(BaseModel):
    hour: int = Field(ge=0, le=23)


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
        db = connect(db_path, schema=False)
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

    def all_questions() -> dict:
        return {q.id: q for _, m in modules() for les in m.lessons for q in les.qcm}

    def find_question(qid: str):
        if (q := all_questions().get(qid)) is None:
            raise HTTPException(404, "Question inconnue")
        return q

    def find_tp(tid: str):
        for d, m in modules():
            for les in m.lessons:
                if les.tp and les.tp.id == tid:
                    return d / "lessons" / f"{les.id}.tp", m, les.tp
        raise HTTPException(404, "TP inconnu")

    def setting(db, key: str) -> str | None:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(db, key: str, value: str = "1") -> None:
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, value))

    def review_due(db) -> int:
        return len(due_reviews(db, date.today())) + len(card_session(db)["cards"])

    def review_progress(db) -> None:
        """Une révision vient d'être faite : jour actif ; révisions du jour toutes faites = XP, une fois par jour."""
        today = date.today().isoformat()
        db.execute("INSERT OR IGNORE INTO activity_days(day) VALUES (?)", (today,))
        if review_due(db) == 0 and setting(db, f"review_done:{today}") is None:
            put(db, f"review_done:{today}")
            award_xp(db, "revision", REVIEW_XP)  # commits
        db.commit()

    def episodes() -> list[dict]:
        idx = podcast / "episodes.json"
        eps = json.loads(idx.read_text(encoding="utf-8")) if idx.is_file() else []
        return [e for e in eps if (podcast / e["file"]).is_file()]  # mp3 hors git : ne lister que les présents

    def suggestions(db, mods, module_id: str | None, local: bool) -> list[dict]:
        out = []
        best = dict(db.execute("SELECT module_id, best FROM exams").fetchall())
        eps = episodes()
        ep = next((e for e in eps if e.get("module") == module_id and setting(db, f"listened:{e['file']}") is None), None)
        if ep:
            out.append({"kind": "episode", "id": ep["file"], "label": f"À écouter : {ep['title']}"})
        for e in eps:  # réécoute espacée : J+1, J+7, J+30 après la première écoute
            v = setting(db, f"listened:{e['file']}") or ""
            if "|" in v:
                first, n = v.split("|")
                if int(n) <= len(RELISTEN_DAYS) and date.today() >= date.fromisoformat(first) + timedelta(days=RELISTEN_DAYS[int(n) - 1]):
                    out.append({"kind": "episode", "id": e["file"], "label": f"Réécouter (rappel n°{n}) : {e['title']}"})
                    break
        missions_done = {r[0] for r in db.execute("SELECT mission_id FROM missions_done")}
        for ms in learn.load_missions(content_dir):
            m = next((m for _, m in mods if m.id == ms["module"]), None)
            if m and ms["id"] not in missions_done and all(advanced(db, les, local) for les in m.lessons):
                out.append({"kind": "mission", "id": ms["id"], "label": f"Mission réelle : {ms['title']}"})
                break
        written = {r[0] for r in db.execute("SELECT module_id FROM articles")}
        if mid := next((k for k, b in best.items() if b >= examlib.PASS_PCT and k in {m.id for _, m in mods} and k not in written), None):
            out.append({"kind": "article", "id": mid, "label": f"Écris l'article du module {mid} (300 mots pour ton portfolio)"})
        for _, m in mods:  # module entièrement vu : l'examen consolide
            if examlib.pool(m) and best.get(m.id, 0) < examlib.PASS_PCT and all(advanced(db, les, local) for les in m.lessons):
                out.append({"kind": "exam", "id": m.id, "label": f"Examen final : {m.title}"})
                break
        last = setting(db, "interview_last")
        if last is None or (date.today() - date.fromisoformat(last)).days >= 7:
            out.append({"kind": "interview", "id": "", "label": "Entraînement d'entretien de la semaine (2 questions)"})
        explained = {r[0] for r in db.execute("SELECT lesson_id FROM feynman")}
        tp_done = [r[0] for r in db.execute("SELECT lesson_id FROM quest_steps WHERE kind = 'tp' AND done = 1 ORDER BY day")]
        if lid := next((x for x in tp_done if x not in explained), None):
            out.append({"kind": "feynman", "id": lid, "label": f"Explique {lid} à un junior (Feynman)"})
        return out

    def plan_target(db, local: bool) -> str | None:
        """Plan commencé : la quête suit son ordre (première leçon du plan pas encore vue)."""
        if setting(db, "plan_start") is None:
            return None
        les = {x.id: x for _, m in modules() for x in m.lessons}
        return next((lid for d in planlib.load_plan(content_dir) for lid in d.get("lessons", [])
                     if lid in les and not advanced(db, les[lid], local)), None)

    @app.get("/api/quest")
    def quest(request: Request, minutes: str = Query("30", pattern="^(30|60)$"), db=Depends(get_db)):
        minutes = int(minutes)
        local = strictly_local(request)
        today = date.today()
        mods = modules()
        target = plan_target(db, local)
        q, mid = None, None
        for tp_only in (False, True):  # d'abord les leçons pas vues (tous modules), ensuite les TP en attente
            ordered = sorted(mods, key=lambda dm: not any(les.id == target for les in dm[1].lessons))
            for _, m in ordered:
                c = build_daily_quest(db, m, today, minutes, local, target=target, tp_only=tp_only)
                if c.steps:
                    q, mid = c, m.id
                    break
            if q:
                break
        if q is None:
            q = build_daily_quest(db, mods[0][1], today, minutes, local) if mods else Quest(today, [], None, None)
        q.pending_tp = [lid for _, m in mods for lid in pending_tps(db, m, local)
                        if not any(s.lesson_id == lid and s.kind == "tp" for s in q.steps)]
        n = review_due(db)
        done = setting(db, f"review_done:{today.isoformat()}") is not None
        q.review = {"due": n, "done": done} if n or done else None
        q.suggestions = suggestions(db, mods, mid, local)
        out = asdict(q)
        out["week"] = week_status(db, today)
        r = retention_stats(db)
        # rythme adaptatif : au-dessus de 85 % on peut accélérer, sous 60 % on consolide avant d'avancer
        out["pace"] = "normal" if r["answered7"] < 10 else "fast" if r["rate7"] > 85 else "consolidate" if r["rate7"] < 60 else "normal"
        return out

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

    audio_dir = Path(db_path).parent / "audio"

    def spoken(stem: Path, text, source: Path | None) -> FileResponse:
        """Audio en cache de `stem`, refait si absent ou plus ancien que `source`. `text` : fonction, appelée seulement s'il faut synthétiser."""
        out = stem.with_suffix(".mp3")  # pas d'audio mp3 : speak() tente edge-tts puis bascule sur espeak (wav)
        if not out.exists() or (source is not None and stale(out, source)):
            try:
                out = speak(text(), stem)
            except RuntimeError as e:
                if not out.exists():  # l'ancien audio vaut mieux que rien
                    raise HTTPException(503, str(e))
        return FileResponse(out, media_type="audio/mpeg" if out.suffix == ".mp3" else "audio/wav")

    def mp3_id(name: str) -> str:
        if not name.endswith(".mp3") or not SAFE_ID.fullmatch(name[:-4]):
            raise HTTPException(404, "Audio inconnu")
        return name[:-4]

    @app.post("/api/lesson/{lesson_id}/rephrase")
    def lesson_rephrase(lesson_id: str, body: RephraseIn):
        _, _, les = find_lesson(lesson_id)
        try:
            return {"text": llm.rephrase(les.title, body.text)}
        except llm.LlmUnavailable as e:
            raise HTTPException(503, str(e))

    @app.get("/api/lesson/{lesson_id}/keys")
    def lesson_keys(lesson_id: str):
        # fin de leçon : ses pièges et termes clés, à se rappeler avant de voir la réponse
        _, _, les = find_lesson(lesson_id)
        return [{"id": c.id, "kind": c.kind, "front": c.front, "back": c.back} for c in cardlib.lesson_cards(les)][:KEYS_MAX]

    @app.get("/api/audio/{name}")
    def audio(name: str):
        lid, ext = name[:-4], name[-4:]
        if ext not in (".mp3", ".wav") or not SAFE_ID.fullmatch(lid):
            raise HTTPException(404, "Audio inconnu")
        d, _, les = find_lesson(lid)
        return spoken(audio_dir / lid, lambda: strip_markdown(les.body_md), d / "lessons" / f"{lid}.md")

    @app.get("/api/fiche-audio/{name}")
    def fiche_audio(name: str):
        mid = mp3_id(name)
        for d, m in modules():
            if m.id == mid and m.fiche_md is not None:
                return spoken(audio_dir / f"fiche-{mid}", lambda: fiche_speech(m.title, m.fiche_md),
                              d / "fiche.md")
        raise HTTPException(404, "Fiche inconnue")

    def interview_of_day(db) -> dict | None:
        """Parmi les 5 questions d'entretien les moins réussies (jamais tentées d'abord), une différente chaque jour."""
        qs = load_questions(content_dir)
        if not qs:
            return None
        best = dict(db.execute("SELECT question_id, best FROM interview").fetchall())
        weakest = sorted(qs, key=lambda q: (best.get(q["id"], -1), q["id"]))[:5]
        return weakest[date.today().toordinal() % len(weakest)]

    def revision_text(db) -> str:
        # révision express pour la voiture : question, temps de réflexion, réponse
        lines = []
        for c in card_session(db)["cards"][:REVISION_MAX]:
            lines.append(f"{c['front']}\nRéfléchis… … …\nRéponse : {c['back']}")
        qs = all_questions()
        for qid in due_reviews(db, date.today())[:REVISION_MAX]:
            if (q := qs.get(qid)) is not None:
                lines.append(f"{q.text}\nRéfléchis… … …\nRéponse : {q.options[q.answer]}. {q.explain}")
        if iq := interview_of_day(db):  # une question d'entretien par jour : la révision n'est jamais vide
            short = ". ".join(iq["model_answer"].split(". ")[:3]).rstrip(".")
            lines.append(f"Question d'entretien : {iq['question']}\nRéponds à voix haute, comme face à un recruteur… … … … …\n"
                         f"Réponse type : {short}.")
        if not lines:
            return ""
        return "Révision express du jour.\n" + "\n".join(f"Question {i}. {t}" for i, t in enumerate(lines, 1)) + \
            "\nC'est fini pour aujourd'hui. Bravo."

    @app.get("/api/revision")
    def revision(db=Depends(get_db)):
        text = revision_text(db)
        # la clé change avec le contenu : l'URL du mp3 change, le cache hors ligne ne sert jamais une vieille révision
        return {"items": text.count("Réfléchis"), "key": hashlib.sha1(text.encode()).hexdigest()[:12] if text else None}

    @app.post("/api/revision/done")
    def revision_done(db=Depends(get_db)):
        # révision express écoutée jusqu'au bout : compte comme les révisions du jour (les boîtes ne bougent pas)
        today = date.today().isoformat()
        db.execute("INSERT OR IGNORE INTO activity_days(day) VALUES (?)", (today,))
        xp = 0
        if setting(db, f"review_done:{today}") is None:
            put(db, f"review_done:{today}")
            award_xp(db, "revision", REVIEW_XP)
            xp = REVIEW_XP
        db.commit()
        return {"xp": xp}

    @app.get("/api/revision/{name}")
    def revision_audio(name: str, db=Depends(get_db)):
        key = mp3_id(name)
        text = revision_text(db)
        if not text or hashlib.sha1(text.encode()).hexdigest()[:12] != key:
            raise HTTPException(404, "Révision périmée : rechargez la liste")
        for old in audio_dir.glob("revision-*"):  # une seule révision gardée
            if not old.name.startswith(f"revision-{key}."):
                old.unlink(missing_ok=True)
        return spoken(audio_dir / f"revision-{key}", lambda: text, None)

    podcast = content_dir / "podcast"

    @app.get("/api/podcast")
    def podcast_list(db=Depends(get_db)):
        # nombre d'écoutes complètes : l'onglet Écoute prépare d'abord les épisodes pas encore écoutés
        heard = {k[len("listened:"):]: v for k, v in db.execute("SELECT key, value FROM settings WHERE key LIKE 'listened:%'")}
        return [{**e, "listened": int(heard[e["file"]].split("|")[1]) if "|" in heard.get(e["file"], "") else 0} for e in episodes()]

    @app.post("/api/podcast/{name}/done")
    def podcast_done(name: str, db=Depends(get_db)):
        if mp3_id(name) and name not in {e["file"] for e in episodes()}:
            raise HTTPException(404, "Épisode inconnu")
        v = setting(db, f"listened:{name}") or ""
        first, n = v.split("|") if "|" in v else (date.today().isoformat(), "0")
        put(db, f"listened:{name}", f"{first}|{int(n) + 1}")  # date de 1re écoute | nombre d'écoutes
        db.execute("INSERT OR IGNORE INTO activity_days(day) VALUES (?)", (date.today().isoformat(),))
        db.commit()
        return {"ok": True}

    @app.get("/api/podcast/{name}")
    def podcast_file(name: str):
        f = podcast / name
        if not name.endswith(".mp3") or not SAFE_ID.fullmatch(name[:-4]) or not f.is_file():
            raise HTTPException(404, "Épisode inconnu")
        return FileResponse(f, media_type="audio/mpeg")

    @app.post("/api/qcm/answer")
    def qcm_answer(body: AnswerIn, db=Depends(get_db)):
        q = find_question(body.question_id)
        if not 0 <= body.chosen < len(q.options):
            raise HTTPException(400, "Choix hors des options")
        correct = body.chosen == q.answer
        was_due = q.id in due_reviews(db, date.today())
        db.execute("INSERT OR IGNORE INTO qcm_first(question_id, correct) VALUES (?, ?)", (q.id, int(correct)))
        db.commit()
        record_answer(db, q.id, correct, date.today(), body.confident)
        if was_due:
            review_progress(db)
        return {
            "correct": correct,
            "sure_wrong": bool(body.confident) and not correct,  # erreur sûre de soi : revient aujourd'hui
            "explanation": q.explain if correct else llm.explain_error(q, body.chosen),
            "remedial_lesson_id": None if correct else q.remedial_lesson_id,
            # après une erreur : la leçon d'origine et la bonne réponse, pour rouvrir la page qui l'explique
            "lesson_id": None if correct else next((les.id for _, m in modules() for les in m.lessons
                                                    if any(x.id == q.id for x in les.qcm)), None),
            "answer": None if correct else q.options[q.answer],
        }

    @app.get("/api/reviews")
    def reviews(db=Depends(get_db)):
        due = []
        boxes = dict(db.execute("SELECT question_id, box FROM mistakes").fetchall())
        questions = []
        qs = all_questions()  # un seul parcours des modules, pas un par question due
        order = due_reviews(db, date.today())
        random.Random(date.today().isoformat()).shuffle(order)  # mélange des modules, stable dans la journée
        for qid in order:
            if (q := qs.get(qid)) is None:  # question removed from content: not due anymore
                continue
            due.append(qid)
            questions.append({"id": q.id, "text": q.text, "options": q.options, "box": boxes.get(qid, 0)})
        ahead = []
        if not questions:  # rien de dû : les plus proches de leur échéance, pour ne pas finir sur un écran vide
            for qid, box in db.execute("SELECT question_id, box FROM mistakes ORDER BY due, question_id LIMIT 20"):
                if (q := qs.get(qid)) is not None and len(ahead) < AHEAD:
                    ahead.append({"id": q.id, "text": q.text, "options": q.options, "box": box})
        return {"due": due, "questions": questions, "boxes": box_counts(db), "intervals": INTERVALS, "ahead": ahead}

    @app.get("/api/portfolio.zip", dependencies=[Depends(local_only)])
    def portfolio_zip(db=Depends(get_db)):
        won = [r[0] for r in db.execute("SELECT DISTINCT boss_id FROM boss_attempts WHERE won = 1 ORDER BY boss_id")]
        titles = [json.loads((bosses[b] / "boss.json").read_text(encoding="utf-8"))["title"] for b in won if b in bosses]
        data, _ = portfolio.build_zip(db, get_profile(db), modules(), workspace, titles)
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="portfolio.zip"'})

    @app.get("/api/push/key")
    def push_key(db=Depends(get_db)):
        return {"key": push.vapid(db)[1], "subscribed": push.count_subs(db) > 0, "hour": push.remind_hour(db),
                "cue": setting(db, "habit_cue") or ""}

    @app.post("/api/push/cue")
    def push_cue(body: CueIn, db=Depends(get_db)):
        if body.cue.strip():
            put(db, "habit_cue", body.cue.strip())
        else:
            db.execute("DELETE FROM settings WHERE key = 'habit_cue'")
        db.commit()
        return {"ok": True}

    @app.post("/api/push/hour")
    def push_hour(body: HourIn, db=Depends(get_db)):
        put(db, "remind_hour", str(body.hour))
        db.commit()
        return {"ok": True}

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
        put(db, "interview_last", date.today().isoformat())
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

    def card_session(db) -> dict:
        v = setting(db, "cards_per_day")
        return cardlib.session(db, studied_cards(db), date.today(), int(v) if v and v.isdigit() else cardlib.NEW_PER_DAY)

    @app.post("/api/cards/per-day")
    def cards_per_day(body: PerDayIn, db=Depends(get_db)):
        put(db, "cards_per_day", str(body.per_day))
        db.commit()
        return {"ok": True}

    def studied_cards(db) -> list[cardlib.Card]:
        done = {r[0] for r in db.execute("SELECT lesson_id FROM quest_steps WHERE kind = 'lesson' AND done = 1")}
        mine = [cardlib.Card(f"panne-{r[0]}", "", "panne", r[1], r[2]) for r in db.execute("SELECT id, front, back FROM user_cards")]
        return mine + [c for _, m in modules() for les in m.lessons if les.id in done for c in cardlib.lesson_cards(les)]

    @app.post("/api/cards/panne")
    def card_panne(body: PanneIn, db=Depends(get_db)):
        # une panne résolue devient une carte écrite par toi : celles-là se retiennent le mieux
        cur = db.execute("INSERT INTO user_cards(front, back, created) VALUES (?, ?, ?)",
                         (f"Panne : {body.symptom.strip()}. Cause et correction ?",
                          f"{body.cause.strip()} → {body.fix.strip()}", date.today().isoformat()))
        db.commit()
        return {"id": f"panne-{cur.lastrowid}"}

    def oral_items(db) -> list[dict]:
        items = [{"kind": "card", "id": c["id"], "prompt": c["front"].replace("＿＿＿", "blanc")}
                 for c in card_session(db)["cards"]]
        qs = all_questions()
        for qid in due_reviews(db, date.today()):
            if (q := qs.get(qid)) is not None:
                opts = " ; ".join(f"réponse {'ABCDEF'[i]} : {o}" for i, o in enumerate(q.options))
                items.append({"kind": "qcm", "id": q.id, "prompt": f"{q.text} {opts}"})
        return items

    @app.get("/api/oral")
    def oral(db=Depends(get_db)):
        return {"items": oral_items(db)}

    @app.post("/api/oral/answer")
    def oral_answer(body: OralIn, db=Depends(get_db)):
        """Réponse dictée (révision orale en voiture) : notée côté serveur, puis rangée comme une réponse écrite."""
        if body.kind == "card":
            c = next((c for c in studied_cards(db) if c.id == body.id), None)
            if c is None:
                raise HTTPException(404, "Carte inconnue")
            ok = learn.oral_match(body.transcript, c.back)
            cardlib.record_card(db, c.id, ok, date.today())
            review_progress(db)
            return {"correct": ok, "answer": c.back, "explain": ""}
        q = find_question(body.id)
        said = learn.norm(body.transcript)
        letter = re.search(r"\b(?:reponse|lettre)\s+([a-f])\b", said)
        chosen = "abcdef".index(letter.group(1)) if letter else \
            next((i for i, o in enumerate(q.options) if learn.oral_match(body.transcript, o)), -1)
        ok = chosen == q.answer
        was_due = q.id in due_reviews(db, date.today())
        record_answer(db, q.id, ok, date.today())
        if was_due:
            review_progress(db)
        return {"correct": ok, "answer": q.options[q.answer], "explain": q.explain}

    @app.get("/api/cards")
    def cards(db=Depends(get_db)):
        return card_session(db)

    @app.post("/api/cards/{card_id}")
    def card_answer(card_id: str, body: CardIn, db=Depends(get_db)):
        if card_id not in {c.id for c in studied_cards(db)}:
            raise HTTPException(404, "Carte inconnue")
        r = cardlib.record_card(db, card_id, body.known, date.today())
        review_progress(db)
        return r

    def plan_status(db, local: bool) -> dict:
        les = {x.id: x for _, m in modules() for x in m.lessons}
        # jour fait = leçons et QCM vus ; les TP en attente sont suivis à part (quête, « TP à faire sur PC »)
        return planlib.status(db, planlib.load_plan(content_dir), date.today(),
                              lambda lid: lid in les and advanced(db, les[lid], local))

    @app.get("/api/plan")
    def plan(request: Request, db=Depends(get_db)):
        return plan_status(db, strictly_local(request))

    @app.post("/api/plan/rebase")
    def plan_rebase(request: Request, db=Depends(get_db)):
        st = plan_status(db, strictly_local(request))
        if not st["started"]:
            raise HTTPException(409, "Plan pas commencé")
        planlib.rebase(db, st["days"], date.today())
        return {"ok": True}

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

    def exam_spec(module_id: str, db) -> tuple[Module, int, float]:
        """(module, nombre de questions, secondes par question). « melange » : toutes les leçons vues, modules mêlés ;
        « blanc » : examen blanc de la certification visée, à sa taille et son rythme réels."""
        mods = [m for _, m in modules()]
        if module_id in ("melange", "blanc"):
            cert = learn.CERTS.get(setting(db, "cert") or "") if module_id == "blanc" else None
            if module_id == "blanc" and cert is None:
                raise HTTPException(404, "Aucune certification visée")
            if cert and cert["modules"]:
                lessons = [les for m in mods if m.id in cert["modules"] for les in m.lessons]
            else:
                lessons = [les for m in mods for les in m.lessons if advanced(db, les)]
            m = Module(module_id, cert["title"] if cert else "Examen mélangé (tous les modules vus)", "revision", lessons)
            if len(examlib.pool(m)) < 5:
                raise HTTPException(404, "Pas encore assez de questions vues")
            if cert:
                return m, cert["questions"], cert["minutes"] * 60 / cert["questions"]
            return m, examlib.SIZE, examlib.SECONDS_PER_QUESTION
        for m in mods:
            if m.id == module_id and examlib.pool(m):
                return m, examlib.SIZE, examlib.SECONDS_PER_QUESTION
        raise HTTPException(404, "Module inconnu")

    @app.get("/api/exams")
    def exams(db=Depends(get_db)):
        best = dict(db.execute("SELECT module_id, best FROM exams").fetchall())
        out = []
        for mid in ("blanc", "melange"):
            try:
                m, size, _ = exam_spec(mid, db)
            except HTTPException:
                continue
            out.append({"id": mid, "title": m.title, "questions": min(size, len(examlib.pool(m))), "best": best.get(mid)})
        return out + [{"id": m.id, "title": m.title, "questions": min(examlib.SIZE, len(examlib.pool(m))), "best": best.get(m.id)}
                      for _, m in modules() if examlib.pool(m)]

    @app.get("/api/exam/{module_id}")
    def exam(module_id: str, db=Depends(get_db)):
        m, size, per_q = exam_spec(module_id, db)
        qs = examlib.draw(m, rng, size)
        row = db.execute("SELECT best FROM exams WHERE module_id = ?", (m.id,)).fetchone()
        return {"id": m.id, "title": m.title, "duration_s": round(per_q * len(qs)),
                "pass_pct": examlib.PASS_PCT, "best": row[0] if row else None,
                "questions": [{"id": q.id, "text": q.text, "options": q.options} for q in qs]}

    @app.post("/api/exam/{module_id}")
    def exam_submit(module_id: str, body: ExamIn, db=Depends(get_db)):
        m, size, _ = exam_spec(module_id, db)
        try:
            score, detail = examlib.grade(m, body.answers, size)
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

    @app.get("/api/glossary")
    def glossary():
        """Terme en gras → la phrase de la première leçon qui l'introduit (pour la retrouver quand il revient plus loin)."""
        out: dict[str, dict] = {}
        for _, m in modules():
            for les in m.lessons:
                for c in cardlib.lesson_cards(les):
                    if c.kind == "terme" and c.back.lower() not in out:
                        out[c.back.lower()] = {"term": c.back, "sentence": c.front.replace(cardlib.BLANK, c.back),
                                               "lesson_id": les.id, "title": les.title}
        return out

    @app.get("/api/today")
    def today_recap(db=Depends(get_db)):
        """Bilan de fin de séance : ce qui a été fait aujourd'hui et ce qui attend demain (clôture nette, envie de revenir)."""
        today = date.today()
        titles = {les.id: les.title for _, m in modules() for les in m.lessons}
        done = [r[0] for r in db.execute(
            "SELECT DISTINCT lesson_id FROM quest_steps WHERE day = ? AND done = 1 ORDER BY lesson_id", (today.isoformat(),))]
        n, ok = db.execute("SELECT COUNT(*), COALESCE(SUM(correct), 0) FROM review_log WHERE day = ?", (today.isoformat(),)).fetchone()
        tomorrow = len(due_reviews(db, today + timedelta(days=1)))
        return {"lessons": [titles.get(i, i) for i in done], "reviewed": n, "correct": ok, "tomorrow": tomorrow}

    @app.post("/api/unclear")
    def unclear_add(body: UnclearIn, db=Depends(get_db)):
        # page « pas claire » : à revoir plus tard, et signal pour retravailler le contenu
        find_lesson(body.lesson_id)
        db.execute("INSERT OR IGNORE INTO unclear(lesson_id, excerpt, at) VALUES (?, ?, ?)",
                   (body.lesson_id, body.excerpt, date.today().isoformat()))
        db.commit()
        return {"ok": True}

    @app.get("/api/unclear")
    def unclear_list(db=Depends(get_db)):
        titles = {les.id: les.title for _, m in modules() for les in m.lessons}
        return [{"id": i, "lesson_id": lid, "title": titles.get(lid, lid), "excerpt": ex, "at": at}
                for i, lid, ex, at in db.execute("SELECT id, lesson_id, excerpt, at FROM unclear ORDER BY at, id")
                if lid in titles]

    @app.delete("/api/unclear/{item_id}")
    def unclear_done(item_id: int, db=Depends(get_db)):
        db.execute("DELETE FROM unclear WHERE id = ?", (item_id,))
        db.commit()
        return {"ok": True}

    @app.get("/api/weak")
    def weak(db=Depends(get_db)):
        """Leçons aux erreurs encore fragiles (boîtes basses), les plus touchées d'abord : où concentrer l'effort."""
        fragile = {r[0] for r in db.execute("SELECT question_id FROM mistakes WHERE box < 3")}
        out = []
        for _, m in modules():
            for les in m.lessons:
                n = sum(q.id in fragile for q in les.qcm)
                if n:
                    out.append({"lesson_id": les.id, "title": les.title, "module": m.title, "count": n})
        return sorted(out, key=lambda x: -x["count"])[:WEAK_MAX]

    @app.get("/api/missions")
    def missions(request: Request, db=Depends(get_db)):
        done = dict(db.execute("SELECT mission_id, proof FROM missions_done").fetchall())
        local = strictly_local(request)
        mods = {m.id: m for _, m in modules()}
        return [{**{k: ms[k] for k in ("id", "module", "title", "goal", "steps")}, "checkable": "check" in ms and local,
                 "done": ms["id"] in done, "proof": done.get(ms["id"]),
                 "ready": ms["module"] in mods and all(advanced(db, les, local) for les in mods[ms["module"]].lessons)}
                for ms in learn.load_missions(content_dir)]

    def finish_mission(db, ms: dict, proof: str) -> int:
        if db.execute("SELECT 1 FROM missions_done WHERE mission_id = ?", (ms["id"],)).fetchone():
            return 0
        db.execute("INSERT INTO missions_done(mission_id, proof, at) VALUES (?, ?, ?)", (ms["id"], proof, date.today().isoformat()))
        db.execute("INSERT OR IGNORE INTO activity_days(day) VALUES (?)", (date.today().isoformat(),))
        skill = next((m.skill for _, m in modules() if m.id == ms["module"]), ms["module"])
        award_xp(db, skill, MISSION_XP)  # commits
        return MISSION_XP

    def find_mission(mid: str) -> dict:
        ms = next((x for x in learn.load_missions(content_dir) if x["id"] == mid), None)
        if ms is None:
            raise HTTPException(404, "Mission inconnue")
        return ms

    @app.post("/api/missions/{mid}/check", dependencies=[Depends(require_strictly_local)])
    def mission_check(mid: str, db=Depends(get_db)):
        """Vérification sur le PC (tes dépôts, gh, docker, kubectl y sont) ; jamais à distance."""
        ms = find_mission(mid)
        if "check" not in ms:
            raise HTTPException(404, "Pas de vérification automatique : donne un lien de preuve")
        try:
            r = subprocess.run(["bash", "-c", ms["check"]], cwd=Path.home(), env=child_env(), capture_output=True,
                               text=True, timeout=MISSION_TIMEOUT, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return {"passed": False, "output": f"Délai dépassé ({MISSION_TIMEOUT} s)", "xp": 0}
        passed = r.returncode == 0
        xp = finish_mission(db, ms, "vérifiée automatiquement") if passed else 0
        return {"passed": passed, "output": (r.stdout + r.stderr)[-2000:], "xp": xp}

    @app.post("/api/missions/{mid}/done")
    def mission_done(mid: str, body: ProofIn, db=Depends(get_db)):
        # depuis le téléphone : un lien vers le commit, la PR ou le run qui prouve le travail
        return {"xp": finish_mission(db, find_mission(mid), body.proof)}

    @app.get("/api/articles")
    def articles(db=Depends(get_db)):
        text = dict(db.execute("SELECT module_id, text FROM articles").fetchall())
        best = dict(db.execute("SELECT module_id, best FROM exams").fetchall())
        return [{"id": m.id, "title": m.title, "text": text.get(m.id, ""), "unlocked": best.get(m.id, 0) >= examlib.PASS_PCT}
                for _, m in modules() if m.id in text or best.get(m.id, 0) >= examlib.PASS_PCT]

    @app.put("/api/articles/{module_id}")
    def article_save(module_id: str, body: ArticleIn, db=Depends(get_db)):
        if module_id not in {m.id for _, m in modules()}:
            raise HTTPException(404, "Module inconnu")
        first = db.execute("SELECT 1 FROM articles WHERE module_id = ?", (module_id,)).fetchone() is None
        db.execute("INSERT OR REPLACE INTO articles(module_id, text, updated) VALUES (?, ?, ?)",
                   (module_id, body.text, date.today().isoformat()))
        if first:
            award_xp(db, "portfolio", ARTICLE_XP)  # commits
        else:
            db.commit()
        return {"xp": ARTICLE_XP if first else 0, "words": len(body.text.split())}

    @app.get("/api/cert")
    def cert(db=Depends(get_db)):
        key, when = setting(db, "cert"), setting(db, "cert_date")
        c = learn.CERTS.get(key or "")
        return {"key": key if c else None, "date": when, "title": c["title"] if c else None,
                "days_left": (date.fromisoformat(when) - date.today()).days if c and when else None,
                "options": [{"key": k, "title": v["title"]} for k, v in learn.CERTS.items()]}

    @app.post("/api/cert")
    def cert_set(body: CertIn, db=Depends(get_db)):
        if body.key is None:
            db.execute("DELETE FROM settings WHERE key IN ('cert', 'cert_date')")
        elif body.key not in learn.CERTS:
            raise HTTPException(422, "Certification inconnue")
        else:
            put(db, "cert", body.key)
            if body.date:
                put(db, "cert_date", body.date)
        db.commit()
        return {"ok": True}

    @app.get("/api/retention")
    def retention(db=Depends(get_db)):
        return retention_stats(db)

    def retention_stats(db) -> dict:
        since = (date.today() - timedelta(days=7)).isoformat()
        n, ok = db.execute("SELECT COUNT(*), COALESCE(SUM(correct), 0) FROM review_log WHERE day > ?", (since,)).fetchone()
        solid = db.execute("SELECT COUNT(*) FROM cards WHERE box >= 3").fetchone()[0] + \
            db.execute("SELECT COUNT(*) FROM mistakes WHERE box >= 4").fetchone()[0]
        weak = db.execute("SELECT COUNT(*) FROM mistakes WHERE box < 3").fetchone()[0]
        return {"answered7": n, "rate7": round(100 * ok / n) if n else None, "solid": solid, "weak": weak,
                "summary": push.weekly_text(db, date.today())}

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
        weak = [r[0] for r in db.execute("SELECT question_id FROM mistakes WHERE box < 3 ORDER BY question_id")]
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
