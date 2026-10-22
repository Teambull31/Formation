#!/usr/bin/env bash
# Contrôle du TP 10 : lance outlook_digest.py contre le simulateur mock_graph (2 puis 3 pages), vérifie
# les requêtes reçues (GET authentifiés seulement, pagination suivie, aucun autre hôte), digest.json,
# puis les erreurs (401, 500, réponse invalide, serveur éteint, GRAPH_URL absent). cwd = dossier du TP.
[ -f outlook_digest.py ] || { echo "ECHEC : le fichier outlook_digest.py est introuvable dans le dossier du TP."; exit 1; }
[ -f digest.py ] && [ -f kit/outlook_graph.py ] || { echo "ECHEC : digest.py ou le dossier kit/ est introuvable (il ne faut pas les supprimer)."; exit 1; }
TP="$PWD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; pkill -P $$ 2>/dev/null' EXIT
TP="$TP" TMP="$TMP" timeout 55 python3 -B - <<'PY'
import json, os, random, re, socket, stat, string, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TP, TMP = os.environ["TP"], os.environ["TMP"]
sys.dont_write_bytecode = True
KIT = os.path.join(TP, "kit")
sys.path.insert(0, KIT)
sys.path.insert(0, TP)
import mock_graph
from outlook_graph import OutlookGraphSource
rnd = random.Random()


def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)


# ---------- code source ----------
src = open(os.path.join(TP, "outlook_digest.py"), encoding="utf-8").read()
for needle, why in (("OutlookGraphSource", "construisez un OutlookGraphSource du kit"), ("GRAPH_URL", "l'adresse du serveur vient de la variable GRAPH_URL"),
                    ("token_path", "passez token_path= (un fichier à côté du script, jamais ailleurs)"),
                    ("auth", "passez auth= (un jeton fictif), pas de vraie connexion")):
    if needle not in src:
        fail(f"outlook_digest.py ne contient pas « {needle} » : {why}.")
bad = re.search(r"graph\.microsoft\.com|login\.microsoftonline|Mail\.ReadWrite|Mail\.Send|\.config", src)
if bad:
    fail(f"outlook_digest.py contient « {bad.group(0)} » : le TP n'utilise que le simulateur, en lecture seule (Mail.Read).")

# ---------- modèle factice : résumé = préfixe aléatoire + objet ----------
PFX = "Synthèse-" + "".join(rnd.choice(string.ascii_lowercase) for _ in range(8))


class Ollama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        prompt = json.loads(self.rfile.read(n)).get("prompt", "")
        m = re.search(r"Objet : (.*)", prompt.rsplit("--- MAIL ---", 1)[-1])
        out = json.dumps({"urgence": "normale", "resume": f"{PFX} {m.group(1) if m else '?'}"[:190]}, ensure_ascii=False)
        body = json.dumps({"response": out, "done": True}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Fake(BaseHTTPRequestHandler):
    """Graph défaillant : renvoie toujours `status` (corps JSON d'erreur, ou charabia avec 200)."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.server.hits.append(self.path)
        body = b"pas du json" if self.server.status == 200 else json.dumps({"error": {"code": "Boom"}}).encode()
        self.send_response(self.server.status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(handler, **attrs):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    for k, v in attrs.items():
        setattr(srv, k, v)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


ollama = serve(Ollama)
OURL = f"http://127.0.0.1:{ollama.server_address[1]}"

# ---------- garde : réseau, et trace des appels GET du connecteur ----------
GUARD = os.path.join(TMP, "guard")
os.makedirs(GUARD)
GUARD_LOG, GET_LOG, TOKEN_LOG = (os.path.join(TMP, n) for n in ("guard.log", "get.log", "token.log"))
with open(os.path.join(GUARD, "sitecustomize.py"), "w") as f:
    f.write('''
import os, socket, sys
_PORTS = {int(p) for p in os.environ.get("GUARD_PORT", "0").split(",")}
def _deny(what):
    with open(os.environ["GUARD_LOG"], "a") as f:
        f.write(what + "\\n")
    raise OSError("bloqué par le contrôle : " + what)
def _ok(addr):
    return isinstance(addr, tuple) and addr[0] in ("127.0.0.1", "localhost") and addr[1] in _PORTS
_connect, _connect_ex, _sendto = socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto
def connect(self, addr):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _ok(addr):
        _deny("réseau " + str(addr))
    return _connect(self, addr)
def connect_ex(self, addr):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _ok(addr):
        _deny("réseau " + str(addr))
    return _connect_ex(self, addr)
def sendto(self, data, *a):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _deny("réseau " + str(a[-1]))
    return _sendto(self, data, *a)
socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto = connect, connect_ex, sendto
_gai = socket.getaddrinfo
def getaddrinfo(host, *a, **k):
    if host not in (None, "127.0.0.1", "localhost"):
        _deny("dns " + str(host))
    return _gai(host, *a, **k)
socket.getaddrinfo = getaddrinfo
# trace : chaque requête passe-t-elle bien par le connecteur du kit (_http.get_json) ?
sys.path.insert(0, os.environ["KIT_DIR"])
import _http
sys.path.remove(os.environ["KIT_DIR"])
_get = _http.get_json
def get_json(url, token, base_url):
    with open(os.environ["GET_LOG"], "a") as f:
        f.write(url + "\\n")
    with open(os.environ["TOKEN_LOG"], "a") as f:
        f.write(token + "\\n")
    return _get(url, token, base_url)
_http.get_json = get_json
''')


def snapshot(root):
    snap = {}
    for d, _, files in os.walk(root):
        if "__pycache__" in d:
            continue
        for n in files:
            p = os.path.join(d, n)
            st = os.stat(p)
            snap[p] = (st.st_size, st.st_mtime_ns)
    return snap


counter = [0]


def run(label, graph_url, ports, expect_ok):
    counter[0] += 1
    wd = os.path.join(TMP, f"run{counter[0]}")
    home = os.path.join(wd, "home")
    os.makedirs(home)
    for p in (GUARD_LOG, GET_LOG, TOKEN_LOG):
        if os.path.exists(p):
            os.remove(p)
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": home, "NO_PROXY": "*", "no_proxy": "*",
           "OLLAMA_URL": OURL, "PYTHONPATH": GUARD, "GUARD_PORT": ",".join(map(str, ports + [ollama.server_address[1]])),
           "GUARD_LOG": GUARD_LOG, "GET_LOG": GET_LOG, "TOKEN_LOG": TOKEN_LOG, "KIT_DIR": KIT}
    if graph_url is not None:
        env["GRAPH_URL"] = graph_url
    before = snapshot(TP)
    existing = set(os.listdir(TP))
    try:
        p = subprocess.run(["python3", "-B", os.path.join(TP, "outlook_digest.py")], cwd=wd, env=env,
                           capture_output=True, timeout=25, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(f"{label} : outlook_digest.py ne se termine pas.")
    out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    if os.path.exists(GUARD_LOG):
        with open(GUARD_LOG) as f:
            fail(f"{label} : accès réseau interdit ({f.read().strip().splitlines()[0]}). Seuls le simulateur (GRAPH_URL) "
                 "et OLLAMA_URL sont joignables.")
    if "Traceback" in out + err:
        fail(f"{label} : trace Python affichée ; attrapez les erreurs et affichez un message lisible.\n{(out + err).strip()[-300:]}")
    tokens = set(open(TOKEN_LOG).read().split()) if os.path.exists(TOKEN_LOG) else set()
    for t in tokens:
        if t in out + err:
            fail(f"{label} : le jeton apparaît dans la sortie du programme ; un jeton ne s'affiche ni ne se journalise jamais.")
    # fichiers : seul digest.json dans le dossier courant ; dans le dossier du TP, seulement un fichier de jeton en 0600
    extra = set(os.listdir(wd)) - {"home", "digest.json"}
    if extra or os.listdir(home):
        fail(f"{label} : fichiers inattendus ({sorted(extra) or os.listdir(home)}) ; seul digest.json est écrit dans le dossier courant.")
    after = snapshot(TP)
    for path in after:
        if path not in before:
            name = os.path.basename(path)
            mode = stat.S_IMODE(os.stat(path).st_mode)
            if "token" not in name.lower():
                fail(f"{label} : fichier créé dans le dossier du TP : {name}.")
            if mode & 0o077:
                fail(f"{label} : le fichier de jeton {name} a les droits {oct(mode)} ; il doit être en 0600.")
        elif after[path] != before[path]:
            fail(f"{label} : {os.path.basename(path)} a été modifié par le programme.")
    gets = open(GET_LOG).read().split() if os.path.exists(GET_LOG) else []
    digest = None
    if os.path.exists(os.path.join(wd, "digest.json")):
        try:
            digest = json.load(open(os.path.join(wd, "digest.json"), encoding="utf-8"))
        except ValueError:
            fail(f"{label} : digest.json n'est pas du JSON valide.")
    if expect_ok:
        if p.returncode != 0:
            fail(f"{label} : code de sortie {p.returncode} au lieu de 0. {(out + err).strip()[-200:]}")
    else:
        if p.returncode == 0:
            fail(f"{label} : le programme doit sortir avec un code non nul quand la connexion échoue.")
        if len(err.strip()) < 10:
            fail(f"{label} : affichez un message d'erreur lisible sur stderr (sans trace, sans jeton).")
        if digest is not None:
            fail(f"{label} : digest.json ne doit pas être écrit quand la connexion échoue.")
    return out + err, gets, digest


def norm(s):
    return " ".join(s.split())


# ---------- attendu : le connecteur du kit + les fonctions de digest.py, même modèle factice ----------
os.environ["OLLAMA_URL"] = OURL
import digest as D  # noqa: E402  (fourni dans le dossier du TP)
with mock_graph.serve(port=0, pages=2) as ref:
    mails = OutlookGraphSource("x", base_url=f"http://127.0.0.1:{ref.port}/v1.0", auth=lambda: "t",
                               token_path=os.path.join(TMP, "ref_token.json")).fetch(limit=10_000)
if len(mails) != 12:
    fail("le simulateur du kit ne renvoie pas 12 mails : le kit a été modifié ?")
EXPECTED = [D.digest_entry(m) for m in mails]
bodies = [norm(m.body)[:30] for m in mails if len(norm(m.body)) >= 30]

# ===== 1. succès : 2 pages, puis 3 pages =====
for pages in (2, 3):
    with mock_graph.serve(port=0, pages=pages) as h:
        output, gets, digest = run(f"{pages} pages", f"http://127.0.0.1:{h.port}/v1.0", [h.port], True)
        reqs = list(h.requests)
    if not reqs:
        fail(f"{pages} pages : le simulateur n'a reçu aucune requête (GRAPH_URL est-elle utilisée ?).")
    if any(m != "GET" for m, _, _ in reqs):
        fail(f"{pages} pages : requête non GET reçue ({[m for m, _, _ in reqs]}) : l'accès est en lecture seule.")
    if not all(ok for _, _, ok in reqs):
        fail(f"{pages} pages : une requête est arrivée sans jeton Bearer (401). Le connecteur envoie le jeton fourni par auth=.")
    if any(path != "/v1.0/me/messages" for _, path, _ in reqs):
        fail(f"{pages} pages : chemin inattendu {sorted({p for _, p, _ in reqs})}.")
    if len(reqs) != pages:
        fail(f"{pages} pages : {len(reqs)} requête(s) reçue(s), {pages} attendue(s) : suivez les pages (@odata.nextLink) une fois chacune, "
             "ce que fait fetch du connecteur.")
    if len(gets) < pages:
        fail("les requêtes ne passent pas par OutlookGraphSource.fetch : utilisez le connecteur du kit, pas urllib à la main.")
    if not isinstance(digest, list) or len(digest) != 12:
        fail(f"{pages} pages : digest.json doit contenir 12 entrées (un mail par entrée), obtenu {len(digest) if isinstance(digest, list) else digest!r}.")
    if digest != EXPECTED:
        bad = next((i for i, (a, b) in enumerate(zip(digest, EXPECTED)) if a != b), 0)
        fail(f"{pages} pages : l'entrée {bad} de digest.json diffère de ce qu'on obtient avec digest.digest_entry sur les mails du "
             f"connecteur (mêmes mails, même ordre) : obtenu {digest[bad]!r}, attendu {EXPECTED[bad]!r}.")
    low = norm(output)
    if any(b in low for b in bodies):
        fail("la sortie du programme contient un morceau de corps de mail ; ne journalisez jamais le contenu des mails.")

# ===== 2. erreurs : 401, 500, réponse invalide, serveur éteint, GRAPH_URL absent =====
for status, what in ((401, "401 (jeton refusé)"), (500, "500 (panne du serveur)"), (200, "réponse qui n'est pas du JSON")):
    srv = serve(Fake, status=status, hits=[])
    port = srv.server_address[1]
    run(what, f"http://127.0.0.1:{port}/v1.0", [port], False)
    if not srv.hits:
        fail(f"{what} : le programme n'a même pas contacté le serveur indiqué par GRAPH_URL.")
    srv.shutdown()
s = socket.socket()
s.bind(("127.0.0.1", 0))
dead = s.getsockname()[1]
s.close()
run("serveur éteint", f"http://127.0.0.1:{dead}/v1.0", [dead], False)
run("GRAPH_URL absent", None, [], False)

print("OK : outlook_digest.py lit les 12 mails page par page (GET authentifiés seulement, un seul hôte), produit digest.json, "
      "et échoue proprement (message lisible, code non nul, sans jeton ni trace).")
PY
