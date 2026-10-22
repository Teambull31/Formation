#!/usr/bin/env bash
# Contrôle du TP 7 : exécute digest.py sur des jeux de mails générés, contre un petit serveur
# factice (qui enregistre les prompts) et contre le mock_ollama du kit (ok, down, slow).
# cwd = dossier du TP.
[ -f digest.py ] || { echo "ECHEC : le fichier digest.py est introuvable dans le dossier du TP."; exit 1; }
[ -f kit/mock_ollama.py ] || { echo "ECHEC : le dossier kit/ est introuvable (il ne faut pas le supprimer)."; exit 1; }
TP="$PWD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; pkill -P $$ 2>/dev/null' EXIT
TP="$TP" TMP="$TMP" timeout 55 python3 -I -B - <<'PY'
import json, mailbox, os, random, re, socket, string, subprocess, sys, threading, time
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TP, TMP = os.environ["TP"], os.environ["TMP"]
sys.dont_write_bytecode = True
REF_KIT = os.path.normpath(os.path.join(os.environ["LESSON_DIR"], "..", "..", "kit"))  # simulateurs de référence, jamais ceux de l'apprenant
REF_DIGEST = os.path.normpath(os.path.join(os.environ["LESSON_DIR"], "..", "_starters"))
sys.path.insert(0, REF_KIT)
import mock_ollama

MARKER = "--- MAIL ---"
URG = ["haute", "normale", "basse"]
rnd = random.Random()


def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)


# ---------- serveur factice : répond en JSON à partir du jeton REF-xxxxxxxx du mail ----------
class Stub:
    def __init__(self):
        self.mode, self.prompts = "json", []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                prompt = json.loads(self.rfile.read(n)).get("prompt", "")
                outer.prompts.append(prompt)
                text = outer.answer(prompt)
                body = json.dumps({"response": text, "done": True}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.srv.daemon_threads = True
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def answer(self, prompt):
        found = re.findall(r"REF-[a-z]{8}", prompt.rsplit(MARKER, 1)[-1])
        if self.mode == "plain" or not found:
            return "Voici un résumé en prose, sans JSON."
        ref = found[0]
        urg = expected_urg(ref)
        if self.mode == "badurgence":
            return json.dumps({"urgence": "critique", "resume": f"Synthèse {ref}"})
        if self.mode == "emptyresume":
            return json.dumps({"urgence": urg, "resume": "  "})
        if self.mode == "list":
            return json.dumps(["haute", ref])
        return json.dumps({"urgence": urg, "resume": f"Synthèse {ref}"}, ensure_ascii=False)


def expected_urg(ref):
    return URG[sum(map(ord, ref)) % 3]


# ---------- génération de mails ----------
WORDS = "dossier client budget serveur contrat planning équipe livraison réunion rapport demande retard projet version accès".split()


def token(n=8):
    return "".join(rnd.choice(string.ascii_lowercase) for _ in range(n))


def sentence():
    return " ".join(rnd.choice(WORDS) for _ in range(rnd.randint(6, 12))).capitalize() + "."


def gen_mails(n, subject_prefix=None, bodies=None):
    base = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
    mails = []
    for i in range(n):
        ref = "REF-" + token()
        body = bodies[i] if bodies and bodies[i] is not None else \
            f"Bonjour,\n\n{sentence()} {sentence()} « Réf. » {ref}.\n\nCordialement,\n{token(5)}"
        if "REF-" not in body:
            body = f"{body} {ref}" if body else body
        mails.append({
            "id": f"g{i}-{token(6)}",
            "sender": f"{token(5)}@example.test",
            "subject": ((subject_prefix[i] + " ") if subject_prefix and subject_prefix[i] else "") + sentence()[:-1],
            "received": (base - timedelta(hours=i + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "body": body,
        })
    return mails


def ref_of(mail):
    m = re.search(r"REF-[a-z]{8}", mail["body"])
    return m.group(0) if m else None


def write_json(mails, name):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(mails, f, ensure_ascii=False)
    return p


def run(args, url, label, out=None, limit=15, cwd=None):
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": TMP, "NO_PROXY": "*", "no_proxy": "*",
           "OLLAMA_URL": url}
    cwd = cwd or TMP
    try:
        p = subprocess.run(["python3", "-B", os.path.join(TP, "digest.py")] + args, cwd=cwd, env=env,
                           capture_output=True, timeout=limit, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(f"{label} : digest.py ne se termine pas en {limit} s (timeout court sur generate, pas de boucle infinie).")
    err = p.stderr.decode("utf-8", "replace")
    if "Traceback" in err + p.stdout.decode("utf-8", "replace"):
        fail(f"{label} : digest.py affiche une trace Python ; attrapez les erreurs (LlmUnavailable, JSON invalide...).\n{err.strip()[-300:]}")
    if p.returncode != 0:
        fail(f"{label} : code de sortie {p.returncode} au lieu de 0. {err.strip()[-200:]}")
    path = out or os.path.join(cwd, "digest.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        fail(f"{label} : le fichier de sortie {os.path.basename(path)} est absent ou n'est pas du JSON valide.")


def norm(s):
    return " ".join(s.split())


def check_schema(digest, mails, label, ids=None):
    if not isinstance(digest, list):
        fail(f"{label} : digest.json doit être une liste JSON.")
    want = ids or [m["id"] for m in mails]
    if [d.get("id") if isinstance(d, dict) else None for d in digest] != want:
        fail(f"{label} : il faut une entrée par mail, dans l'ordre d'entrée (le même nombre : {len(want)}, mêmes id).")
    for d in digest:
        if set(d) != {"id", "urgence", "resume", "suspect"}:
            fail(f"{label} : chaque entrée a exactement les clés id, urgence, resume, suspect (obtenu {sorted(d)}).")
        if d["urgence"] not in URG:
            fail(f"{label} : urgence doit être haute, normale ou basse (obtenu {d['urgence']!r}).")
        if not isinstance(d["resume"], str) or not d["resume"].strip():
            fail(f"{label} : resume doit être un texte non vide.")
        if d["suspect"] is not False:
            fail(f"{label} : à ce stade suspect vaut toujours false (leçon 8 pour le reste).")


def check_extractive(digest, mails, label):
    seen = set()
    for d, m in zip(digest, mails):
        r = d["resume"].strip().rstrip("…").rstrip(".").rstrip()
        b, s = norm(m["body"]), norm(m["subject"])
        if len(d["resume"]) > 220:
            fail(f"{label} : le résumé de secours est trop long ({len(d['resume'])} caractères ; 200 au plus).")
        if not (r in b or r in s):
            fail(f"{label} : le résumé de secours doit être extrait du corps (ou de l'objet si le corps est vide), "
                 f"pas inventé ni constant. Obtenu : {d['resume'][:80]!r}")
        if b and len(r) < min(30, len(b)):
            fail(f"{label} : le résumé de secours est trop court : prenez les 200 premiers caractères du corps.")
        if not b and r != s:
            fail(f"{label} : corps vide : le résumé doit être l'objet du mail.")
        seen.add(d["resume"])
    if len(mails) > 1 and len(seen) < len(mails):
        fail(f"{label} : des mails différents ont le même résumé de secours : il doit dépendre du contenu.")


stub = Stub()
URL = f"http://127.0.0.1:{stub.port}"

# ===== 1. réponses JSON valides du modèle (jeu aléatoire, ordre, prompts) =====
mails = gen_mails(5)
digest = run(["--source", "json", "--path", write_json(mails, "a.json"), "--out", os.path.join(TMP, "o1.json")],
             URL, "jeu 1", out=os.path.join(TMP, "o1.json"))
check_schema(digest, mails, "jeu 1")
for d, m in zip(digest, mails):
    ref = ref_of(m)
    if d["resume"] != f"Synthèse {ref}" or d["urgence"] != expected_urg(ref):
        fail("jeu 1 : le résumé et l'urgence doivent venir de la réponse JSON du modèle quand elle est valide "
             f"(attendu « Synthèse {ref} » / {expected_urg(ref)}, obtenu {d['resume'][:50]!r} / {d['urgence']}).")
if len(stub.prompts) != len(mails):
    fail(f"jeu 1 : un appel au modèle par mail est attendu ({len(mails)}), il y en a eu {len(stub.prompts)}.")
for p, m in zip(sorted(stub.prompts, key=lambda p: re.findall(r"REF-[a-z]{8}", p)[0]),
                sorted(mails, key=ref_of)):
    if MARKER not in p:
        fail(f"jeu 1 : le prompt doit contenir le délimiteur {MARKER} avant chaque mail.")
    avant, apres = p.rsplit(MARKER, 1)
    if ref_of(m) not in apres or len(re.findall(r"REF-[a-z]{8}", p)) != 1:
        fail(f"jeu 1 : le mail doit venir APRÈS le dernier {MARKER}, et un prompt ne contient qu'un seul mail.")
    if "json" not in avant.lower():
        fail("jeu 1 : les consignes (avant le délimiteur) doivent demander une réponse au format JSON.")

# ===== 2. un énorme corps + un corps vide : découpage =====
stub.prompts.clear()
huge = "Début important REF-" + token() + ". " + ("bla bla " * 40000) + " fin."
mails = gen_mails(4, bodies=[None, huge, None, None])
digest = run(["--source", "json", "--path", write_json(mails, "b.json"), "--out", os.path.join(TMP, "o2.json")],
             URL, "jeu 2", out=os.path.join(TMP, "o2.json"))
check_schema(digest, mails, "jeu 2")
longest = max(len(p) for p in stub.prompts)
if longest > 8000:
    fail(f"jeu 2 : un corps de 320 000 caractères est envoyé presque en entier au modèle (prompt de {longest} caractères) ; "
         "découpez le corps à quelques milliers de caractères.")
if not any(ref_of(mails[1]) in p for p in stub.prompts):
    fail("jeu 2 : le début du gros mail doit rester dans le prompt (on coupe la fin, pas le début).")

# ===== 3. liste vide, et --out par défaut =====
stub.prompts.clear()
sub = os.path.join(TMP, "vide")
os.mkdir(sub)
digest = run(["--source", "json", "--path", write_json([], "c.json")], URL, "liste vide", cwd=sub)
if digest != [] or stub.prompts:
    fail("liste vide : digest.json doit valoir [] (sans appel au modèle ; --out vaut digest.json par défaut).")

# ===== 4. source mbox =====
stub.prompts.clear()
box_path = os.path.join(TMP, "boite.mbox")
box = mailbox.mbox(box_path)
base = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
mb_refs, mb_ids = [], []
for i in range(3):
    msg = EmailMessage()
    ref = "REF-" + token()
    mid = f"{token(10)}@example.test"
    msg["From"], msg["To"], msg["Subject"] = f"{token(4)}@example.test", "moi@example.test", f"Sujet {token(5)}"
    msg["Date"] = format_datetime(base - timedelta(hours=i))
    msg["Message-ID"] = f"<{mid}>"
    msg.set_content(f"Bonjour, {sentence()} {ref}.")
    box.add(msg)
    mb_refs.append(ref)
    mb_ids.append(mid)
box.flush()
box.close()
digest = run(["--source", "mbox", "--path", box_path, "--out", os.path.join(TMP, "o4.json")], URL, "mbox",
             out=os.path.join(TMP, "o4.json"))
check_schema(digest, None, "mbox", ids=mb_ids)
if [d["resume"] for d in digest] != [f"Synthèse {r}" for r in mb_refs]:
    fail("mbox : --source mbox doit lire la boîte avec MboxMailSource et résumer chaque message.")

# ===== 5. secours : réponses inutilisables du modèle =====
cases = gen_mails(5, subject_prefix=["URGENT :", "", "Alerte", "", ""],
                  bodies=[None, "La newsletter du mois. Pour vous DÉSABONNER, répondez STOP. " + "x" * 300, None,
                          "Newsletter et alerte réseau, c'est CRITIQUE ce soir sur le serveur.", ""])
cases[3]["subject"] = "Point sur le " + token(4)
attendu = ["haute", "basse", "haute", "haute", "normale"]
for mode in ("plain", "badurgence", "emptyresume", "list"):
    stub.mode = mode
    digest = run(["--source", "json", "--path", write_json(cases, "d.json"), "--out", os.path.join(TMP, "o5.json")],
                 URL, f"secours ({mode})", out=os.path.join(TMP, "o5.json"))
    check_schema(digest, cases, f"secours ({mode})")
    check_extractive(digest, cases, f"secours ({mode})")
    got = [d["urgence"] for d in digest]
    if got != attendu:
        fail(f"secours ({mode}) : urgence de secours par mots-clés : haute si urgent/alerte/critique, "
             f"basse si newsletter/désabonner (haute l'emporte), sinon normale. Attendu {attendu}, obtenu {got}.")
stub.mode = "json"

# ===== 6. mock_ollama du kit : ok (réponse non JSON), down, slow, serveur absent =====
mails = gen_mails(4)
src = write_json(mails, "e.json")
with mock_ollama.serve(port=0, mode="ok") as srv:
    murl = f"http://127.0.0.1:{srv.port}"
    for mode in ("ok", "down"):
        srv.set_mode(mode)
        digest = run(["--source", "json", "--path", src, "--out", os.path.join(TMP, "o6.json")], murl,
                     f"mock {mode}", out=os.path.join(TMP, "o6.json"))
        check_schema(digest, mails, f"mock {mode}")
        check_extractive(digest, mails, f"mock {mode}")
    srv.set_mode("slow")
    one = mails[:1]
    t0 = time.time()
    digest = run(["--source", "json", "--path", write_json(one, "f.json"), "--out", os.path.join(TMP, "o7.json")],
                 murl, "mock slow", out=os.path.join(TMP, "o7.json"), limit=12)
    check_schema(digest, one, "mock slow")
    check_extractive(digest, one, "mock slow")
    if time.time() - t0 > 4.8:
        fail("mock slow : le secours doit se déclencher après un timeout d'au plus 3 secondes, pas après la réponse lente.")
s = socket.socket()
s.bind(("127.0.0.1", 0))
dead = s.getsockname()[1]
s.close()
digest = run(["--source", "json", "--path", src, "--out", os.path.join(TMP, "o8.json")], f"http://127.0.0.1:{dead}",
             "serveur absent", out=os.path.join(TMP, "o8.json"))
check_schema(digest, mails, "serveur absent")
check_extractive(digest, mails, "serveur absent")

print("OK : digest.py produit un résumé par mail (JSON validé, secours extractif, gros corps coupé, ordre conservé).")
PY
