#!/usr/bin/env bash
# Contrôle du TP 3 : lance client.py contre le serveur du kit (compteurs côté serveur)
# et contre de faux serveurs (panne permanente, 404, POST en 503, serveur muet).
# cwd = dossier du TP ; le serveur du kit est dans ./kit.
[ -f client.py ] || { echo "ECHEC : le fichier client.py est introuvable dans le dossier du TP."; exit 1; }
[ -f kit/test_api.py ] || { echo "ECHEC : le dossier kit/ est introuvable (il ne faut pas le supprimer)."; exit 1; }
TP="$PWD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; pkill -P $$ 2>/dev/null' EXIT
TP="$TP" TMP="$TMP" timeout 50 python3 -B - <<'PY'
import json, os, random, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TP, TMP = os.environ["TP"], os.environ["TMP"]
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(TP, "kit"))
import test_api

def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)

def run(url, limit=20):
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": TMP, "NO_PROXY": "*", "no_proxy": "*"}
    if url is not None:
        env["API_URL"] = url
    t0 = time.time()
    try:
        p = subprocess.run(["python3", "-B", "client.py"], cwd=TP, env=env, capture_output=True,
                           timeout=limit, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(f"client.py ne s'arrête pas en {limit} s : un appel sans timeout reste bloqué.")
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    if "Traceback" in out:
        fail("client.py affiche une trace Python : attrapez les erreurs et affichez un message lisible.")
    return p.returncode, out, time.time() - t0

# ---- 1. vrai serveur du kit : lignes, compteur de /flaky, POST unique ----
WORDS = ["rapport", "facture", "réunion", "café", "équipe", "devis", "mise à jour", "Noël"]
def random_tasks():
    return [{"id": i, "title": f"{random.choice(WORDS)} {random.randint(100, 999)}", "done": False}
            for i in range(1, random.randint(2, 5) + 1)]

with test_api.serve(port=0) as h:
    url = f"http://127.0.0.1:{h.port}"
    for start in (0, 1, 2, 0):  # 3, 2, 1, 3 requêtes /flaky nécessaires
        tasks = random_tasks()
        h.state["tasks"], h.state["calls"] = [dict(t) for t in tasks], start
        code, out, _ = run(url)
        if code != 0:
            fail(f"code de sortie {code} au lieu de 0 sur un serveur qui finit par répondre. Sortie : {out.strip()[:200]}")
        lines = [l.rstrip() for l in out.splitlines()]
        want = [f"{t['id']}: {t['title']}" for t in tasks]
        got = [l for l in lines if l in want]
        if got != want:
            fail(f"les tâches doivent être affichées une par ligne, « id: title », dans l'ordre. Attendu : {want}.")
        flaky = [l for l in lines if l.lower().startswith("flaky:")]
        if len(flaky) != 1 or "ok" not in flaky[0].lower() or "true" not in flaky[0].lower():
            fail("il manque la ligne « flaky: {...} » avec la réponse réussie de /flaky.")
        expected_calls = start + (3 - start % 3)
        if h.state["calls"] != expected_calls:
            made = h.state["calls"] - start
            fail(f"/flaky a reçu {made} requête(s) au lieu de {3 - start % 3} : il faut réessayer (3 tentatives au plus) et s'arrêter dès le succès.")
        if len(h.state["tasks"]) != len(tasks) + 1:
            fail(f"le POST /tasks doit être envoyé exactement une fois ({len(h.state['tasks']) - len(tasks)} tâche(s) ajoutée(s)).")
        new = h.state["tasks"][-1]
        if new.get("title") != "Relancer le client":
            fail("le POST doit envoyer le corps JSON {\"title\": \"Relancer le client\"}.")
        if not any(l.startswith("créée:") and str(new["id"]) in l for l in lines):
            fail(f"il manque la ligne « créée: {new['id']} » avec l'id reçu du serveur.")

# ---- 2. faux serveurs : compteurs, 4xx, POST en échec, serveur muet ----
class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        mode, hits = self.server.mode, self.server.hits
        hits.append("GET " + self.path)
        self.server.times.append(time.time())
        if mode == "slow":  # répond après 2,7 s : un timeout de 2 s coupe, un timeout de 3 s ou plus laisse passer
            threading.Event().wait(2.7)
            try:
                return self.reply(200, [{"id": 1, "title": "a", "done": False}] if self.path == "/tasks" else {"ok": True})
            except OSError:
                return
        if mode == "notfound":
            return self.reply(404, {"error": "nope"})
        if self.path == "/tasks":
            return self.reply(200, [{"id": 1, "title": "a", "done": False}])
        if self.path == "/flaky":
            return self.reply(503 if mode == "down" else 200, {"ok": True})
        self.reply(404, {})
    def do_POST(self):
        self.server.hits.append("POST " + self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        ct = self.headers.get("Content-Type", "")
        if "application/json" not in ct:
            self.server.bad = "en-tête Content-Type: application/json manquant sur le POST"
        try:
            json.loads(body)
        except ValueError:
            self.server.bad = "le corps du POST n'est pas du JSON valide"
        self.reply(503, {"error": "boom"})

def stub(mode):
    s = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    s.daemon_threads = True
    s.mode, s.hits, s.bad, s.times = mode, [], None, []
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s

def count(s, what):
    return sum(1 for h in s.hits if h == what)

def readable(out):
    return len(out.strip()) >= 8

s = stub("down")   # /flaky ne répond jamais correctement
code, out, _ = run(f"http://127.0.0.1:{s.server_address[1]}")
if code == 0:
    fail("code de sortie 0 alors que /flaky échoue 3 fois : utilisez sys.exit(1).")
if count(s, "GET /flaky") != 3:
    fail(f"/flaky en panne permanente doit recevoir exactement 3 tentatives (reçu : {count(s, 'GET /flaky')}).")
if not readable(out):
    fail("un échec définitif doit afficher un message lisible.")
flaky_times = s.times[-3:]
gaps = [b - a for a, b in zip(flaky_times, flaky_times[1:])]
if gaps[0] < 0.15 or gaps[1] < 0.3 or gaps[1] < gaps[0] * 1.4:
    fail("il faut une pause qui double entre les essais (0,2 s puis 0,4 s) : des essais collés martèlent le serveur.")
if count(s, "POST /tasks"):
    fail("après l'échec de /flaky, le script doit s'arrêter sans envoyer le POST.")
s.shutdown()

s = stub("notfound")   # 404 : jamais de retry
code, out, _ = run(f"http://127.0.0.1:{s.server_address[1]}")
if code == 0:
    fail("code de sortie 0 sur un 404 : sortez avec le code 1.")
if len(s.hits) != 1:
    fail(f"une erreur 4xx ne se réessaie pas : {len(s.hits)} requêtes reçues au lieu de 1.")
if not readable(out):
    fail("un 404 doit afficher un message lisible.")
s.shutdown()

s = stub("post503")   # POST en échec : un seul essai, jamais rejoué
code, out, _ = run(f"http://127.0.0.1:{s.server_address[1]}")
if code == 0:
    fail("code de sortie 0 alors que le POST a échoué : sortez avec le code 1.")
if count(s, "POST /tasks") != 1:
    fail(f"un POST n'est pas idempotent : exactement 1 tentative attendue (reçu : {count(s, 'POST /tasks')}).")
if s.bad:
    fail(s.bad + ".")
if not readable(out):
    fail("l'échec du POST doit afficher un message lisible.")
s.shutdown()

s = stub("slow")   # serveur muet : le timeout doit couper chaque tentative
code, out, dt = run(f"http://127.0.0.1:{s.server_address[1]}", limit=25)
if code == 0:
    fail("code de sortie 0 alors que le serveur répond après 2,7 s : le timeout doit être de 2 secondes (timeout=2), pas plus.")
if count(s, "GET /tasks") < 2:
    fail("le serveur répond après 2,7 s : avec timeout=2, la 1re tentative doit expirer puis être rejouée (GET). "
         f"Reçu {count(s, 'GET /tasks')} requête(s) GET /tasks : le timeout est trop long, utilisez timeout=2.")
if dt > 12:
    fail(f"le timeout est trop long ({dt:.0f} s pour 3 tentatives) : utilisez timeout=2.")
if not 2 <= len(s.hits) <= 3:
    fail(f"un timeout sur un GET se réessaie (3 tentatives au plus) : {len(s.hits)} requêtes reçues.")
if not readable(out):
    fail("un timeout doit afficher un message lisible.")
s.shutdown()

# ---- 3. port fermé et variable manquante : échec rapide, propre ----
import socket
sock = socket.socket(); sock.bind(("127.0.0.1", 0)); dead = sock.getsockname()[1]; sock.close()
code, out, dt = run(f"http://127.0.0.1:{dead}")
if code == 0 or not readable(out) or dt > 12:
    fail("serveur injoignable : attendu un échec rapide, code non nul et un message lisible.")
code, out, _ = run(None)
if code == 0 or not readable(out):
    fail("sans API_URL : attendu un message lisible et un code non nul.")

# ---- 4. inspection statique : le timeout est écrit dans le code ----
src = open(os.path.join(TP, "client.py"), encoding="utf-8").read()
if "timeout" not in src:
    fail("client.py ne mentionne aucun timeout.")

print("OK : client.py réessaie les GET (3 essais, backoff), ne rejoue pas le POST, gère timeout et pannes avec le code 1.")
PY
