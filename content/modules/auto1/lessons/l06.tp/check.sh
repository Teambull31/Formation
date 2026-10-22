#!/usr/bin/env bash
# Contrôle du TP 6 : lance le simulateur du kit (modes ok, down, slow) et exécute ask.py
# avec OLLAMA_URL ; vérifie réponse, secours, absence du prompt dans les sorties.
# cwd = dossier du TP.
[ -f ask.py ] || { echo "ECHEC : le fichier ask.py est introuvable dans le dossier du TP."; exit 1; }
[ -f kit/mock_ollama.py ] || { echo "ECHEC : le dossier kit/ est introuvable (il ne faut pas le supprimer)."; exit 1; }
TP="$PWD"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; pkill -P $$ 2>/dev/null' EXIT
TP="$TP" TMP="$TMP" timeout 50 python3 -I -B - <<'PY'
import os, random, socket, string, subprocess, sys, time

TP, TMP = os.environ["TP"], os.environ["TMP"]
sys.dont_write_bytecode = True
REF_KIT = os.path.normpath(os.path.join(os.environ["LESSON_DIR"], "..", "..", "kit"))  # simulateurs de référence, jamais ceux de l'apprenant
REF_DIGEST = os.path.normpath(os.path.join(os.environ["LESSON_DIR"], "..", "_starters"))
sys.path.insert(0, REF_KIT)
import mock_ollama
mock_ollama.SLOW_SECONDS = 3.6  # juste au-dessus de 3 s : un timeout de 4 s laisserait passer la réponse tardive

SECOURS = "(secours) Ollama indisponible"

def fail(msg):
    print("ECHEC : " + msg)
    sys.exit(1)

def run(url, prompt, label, limit=9):
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "HOME": TMP, "NO_PROXY": "*", "no_proxy": "*",
           "OLLAMA_URL": url}
    t0 = time.time()
    try:
        p = subprocess.run(["python3", "-B", "ask.py", prompt], cwd=TP, env=env, capture_output=True,
                           timeout=limit, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        fail(f"{label} : ask.py ne se termine pas en {limit} s ; fixez un timeout d'au plus 3 secondes.")
    out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    if "Traceback" in out + err:
        fail(f"{label} : ask.py affiche une trace Python ; attrapez LlmUnavailable.")
    return p.returncode, out, err, time.time() - t0

rnd = random.Random()
def token():
    return "".join(rnd.choice(string.ascii_lowercase) for _ in range(10)) + str(rnd.randint(100, 999))

def make_prompt(kind):
    a, b = token(), token()
    if kind == "simple":
        return f"Question {a} sur le dossier {b}", [a, b]
    return (f"Résumé-moi « {a} » : l'équipe dit \"d'accord\"\nDeuxième ligne éàç {b}\n  fin 'ok'", [a, b])

with mock_ollama.serve(port=0, mode="ok") as srv:
    url = f"http://127.0.0.1:{srv.port}"

    # ---- mode ok : la réponse du modèle, rien d'autre ----
    for kind in ("simple", "tordu"):
        prompt, secrets = make_prompt(kind)
        want = mock_ollama.fake_answer(prompt, "ok")
        rc, out, err, _ = run(url, prompt, f"mode ok ({kind})")
        if rc != 0:
            fail(f"mode ok ({kind}) : code de sortie {rc} au lieu de 0. {err.strip()[-200:]}")
        if "(secours)" in out + err:
            fail(f"mode ok ({kind}) : « (secours) » affiché alors que le simulateur répond.")
        if out.strip() != want:
            fail(f"mode ok ({kind}) : la réponse affichée ne correspond pas à celle du modèle "
                 f"(envoyez la question telle quelle, sans rien ajouter).\n  attendu : {want!r}\n  obtenu  : {out.strip()!r}")

    # ---- modes down et slow : secours, prompt jamais divulgué ----
    for mode, limit in (("down", 9), ("slow", 9)):
        srv.set_mode(mode)
        for kind in ("simple", "tordu"):
            if mode == "slow" and kind == "tordu":
                continue  # un seul passage lent suffit (garde le contrôle court)
            prompt, secrets = make_prompt(kind)
            label = f"mode {mode} ({kind})"
            rc, out, err, dt = run(url, prompt, label, limit)
            if out.strip() == mock_ollama.fake_answer(prompt, "ok"):
                fail(f"{label} : ask.py a attendu la réponse lente ({dt:.0f} s). Utilisez un timeout d'au plus 3 secondes.")
            if rc != 0:
                fail(f"{label} : code de sortie {rc} au lieu de 0 ; le secours se termine normalement.")
            if out.strip() != SECOURS:
                fail(f"{label} : stdout doit être exactement « {SECOURS} ». Obtenu : {out.strip()!r}")
            if not err.strip():
                fail(f"{label} : écrivez une courte raison sur stderr.")
            if len(err.strip().splitlines()) > 1 or len(err) > 200:
                fail(f"{label} : la raison sur stderr doit tenir en une ligne de moins de 200 caractères.")
            for leak in [prompt] + secrets + [s for s in prompt.split("\n") if len(s) > 12]:
                if leak in out or leak in err:
                    fail(f"{label} : le texte de la question apparaît dans la sortie ; le prompt est privé, ne l'affichez jamais.")

# ---- serveur absent (connexion refusée) : secours aussi ----
s = socket.socket()
s.bind(("127.0.0.1", 0))
dead = s.getsockname()[1]
s.close()
prompt, secrets = make_prompt("tordu")
rc, out, err, _ = run(f"http://127.0.0.1:{dead}", prompt, "serveur absent")
if rc != 0 or out.strip() != SECOURS or not err.strip() or any(x in out + err for x in secrets):
    fail(f"serveur absent : attendu le secours (stdout « {SECOURS} », raison sur stderr sans la question, code 0). "
         f"Obtenu : code {rc}, stdout {out.strip()!r}.")

print("OK : ask.py affiche la réponse en mode ok, le secours en down/slow/serveur absent, sans jamais divulguer la question.")
PY
