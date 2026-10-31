"""TP es10 : MQTT sur TLS. Le client MQTT d'es8 passe en mqtts:// avec vérification du certificat du courtier, lit ses identifiants
en NVS (jamais dans le code), et quand la liaison est perdue ou ne s'établit pas il met le relais GPIO 5 en état sûr (éteint) et
réessaie avec une attente croissante (1 s, 2 s, 4 s, 8 s puis 8 s, comme es7).

Le certificat du courtier est fabriqué par le pilote à chaque exécution ("server_cert": "@generate") : le programme le lit par le
symbole _binary_server_cert_pem_start. Les identifiants sont préremplis en NVS par le scénario (clé "nvs"), espace « mqtt »,
clés « user » et « pass ».

Trois exécutions (SCENARIOS) ; niveau constant de 72,5 % (sous la limite de 80 %) :
  a : certificat valide, 100 s. {"relay": true} à 30 s : relais allumé ; « salut » à 50 s (ignoré) ; {"relay": false} à 70 s.
  b : poignée de main en échec 2 minutes, 290 s. {"relay": true} à 30 s ; à 60 s le courtier coupe la session et, de 60 s à 180 s,
      refuse toute poignée de main : le relais doit être éteint dans les 2 s et le rester ; le client réessaie avec une attente
      croissante et se reconnecte après 180 s ; {"relay": true} à 240 s (reçue seulement si le programme s'est réabonné) ; nouvelle
      coupure du courtier de 250 s à 253 s : relais éteint dans les 2 s, et l'attente repart de 1 s (remise à zéro).
  c : certificat expiré, 120 s. Le client ne doit JAMAIS se connecter (vérification maintenue) ni abandonner : il réessaie
      jusqu'à la fin. {"relay": true} à 30 s et à 100 s ne peuvent pas arriver : relais éteint tout du long.

Le contrôle juge la trace, et lit aussi le texte du programme pour deux choses : aucune option qui réduit la vérification (le champ
skip_cert_common_name_check ne vaut jamais autre chose que false, ni les options d'esp-tls qui coupent la vérification), et aucun
identifiant en clair (le texte des identifiants du scénario, ou une valeur littérale donnée à une variable ou à un champ de nom
« mot de passe » ou « utilisateur »). Les commentaires et les chaînes sont retirés avant la recherche des options ; les noms de clés
NVS (« user », « pass ») ne sont pas des identifiants.

Tolérances : relais commuté au plus 1 s après une commande, au plus 2 s après une perte de liaison ; abonnement dans les 5 s qui
suivent chaque connexion ; télémétrie de 9 s à 11 s entre deux messages d'une même connexion ; première attente de 1 s à 3 s, puis
jamais plus courte que la précédente (à 0,6 s près), la deuxième au moins 1,5 fois la première, au moins 8 s parmi les 6 premières,
jamais plus de 35 s ; une tentative au plus 36 s avant la fin si la liaison n'est pas rétablie.
"""
import json
import re

from esp_trace import code_only as _code, fmt_s as _s, need, topic_match as _match, Trace

PIN = 5
CHANNEL = 6
BASE = "home/devices/pool-ctl"
T_TELE, T_CMD = f"{BASE}/telemetry", f"{BASE}/command"
LEVEL = 72.5
LEVEL_TOL = 1.0
USER, PASS = "piscine-ctl-07","Pz9-ke4N-77qL"  # NVS d'essai : jamais montrés à l'apprenant
SETUP_MS, REACT_MS, SAFE_MS = 5_000, 1_000, 2_000
TELE_MIN_MS, TELE_MAX_MS = 9_000, 11_000
WAIT_FIRST_MIN, WAIT_FIRST_MAX, WAIT_SHRINK_MS = 1_000, 3_000, 600
WAIT_GROWTH, WAIT_REACH, WAIT_REACH_COUNT, WAIT_CAP_MS, TAIL_MS = 1.5, 8_000, 6, 35_000, 36_000
OUTPUT_MODES = {"output", "input_output"}
MAX_OUT = 4_000_000  # une boucle de reconnexion serrée produit plus que le plafond par défaut (1 Mo) : on veut la juger, pas la tronquer

CMD_ON, CMD_OFF = '{"relay": true}', '{"relay":false}'
INCOMING = {
    "a": [(30_000, CMD_ON), (50_000, "salut"), (70_000, CMD_OFF)],
    "b": [(30_000, CMD_ON), (100_000, CMD_ON), (240_000, CMD_ON)],
    "c": [(30_000, CMD_ON), (100_000, CMD_ON)],
}
MAX_MS = {"a": 100_000, "b": 290_000, "c": 120_000}
OUTAGE_B = [(60_000, 61_000), (250_000, 253_000)]  # coupures du courtier de b ; la première coupe la session, la poignée de main échoue ensuite
HANDSHAKE_FAIL_B = (60_000, 180_000)  # 2 minutes
# (t_ms, relais attendu, délai accordé, sorte) : à partir de t + délai et jusqu'à l'instant suivant, la broche a cette valeur.
RELAY = {
    "a": [(0, 0, 0, "start"), (30_000, 1, REACT_MS, "cmd"), (70_000, 0, REACT_MS, "cmd")],
    "b": [(0, 0, 0, "start"), (30_000, 1, REACT_MS, "cmd"), (60_000, 0, SAFE_MS, "safe"), (240_000, 1, REACT_MS, "cmd"),
          (250_000, 0, SAFE_MS, "safe")],
    "c": [(0, 0, 0, "start")],
}


def _scenario(name: str) -> dict:
    mqtt = {"incoming": [{"t_ms": t, "topic": T_CMD, "payload": p} for t, p in INCOMING[name]]}
    tls: dict = {"server_cert": "@generate"}
    if name == "b":
        mqtt["broker_down"] = [{"from_ms": a, "to_ms": b} for a, b in OUTAGE_B]
        tls["handshake_fail"] = [{"from_ms": HANDSHAKE_FAIL_B[0], "to_ms": HANDSHAKE_FAIL_B[1]}]
    if name == "c":
        tls["server_cert_valid"] = False
    tank = {"level_pct0": LEVEL, "fill_pct_per_min": 0, "loss_pct_per_min": 0, "relay_pin": PIN, "adc_channel": CHANNEL,
            "raw_at_0": 620, "raw_at_100": 3723}
    return {"plant": {"tank": tank}, "mqtt": mqtt, "tls": tls, "nvs": {"mqtt": {"user": USER, "pass": PASS}}}


SCENARIOS = {name: (_scenario(name), MAX_MS[name]) for name in ("a", "b", "c")}
LABELS = {"a": "scénario a (certificat valide)",
          "b": "scénario b (poignée de main en échec de 60 s à 180 s, puis coupure du courtier de 250 s à 253 s)",
          "c": "scénario c (certificat expiré)"}

S_WHY = "Pourquoi TLS, et ce qu'il garantit"
S_CHAIN = "Certificat, autorité et chaîne de confiance"
S_NEVER = "Ne jamais désactiver la vérification"
S_CLIENT = "mqtts:// et la vérification dans esp-mqtt"
S_EMBED = "Embarquer le certificat du courtier"
S_CREDS = "Les identifiants se lisent en NVS, jamais dans le code"
S_ERR = "Quand la poignée de main échoue : lire l'erreur"
S_RETRY = "Réessayer avec une attente croissante"
S_SAFE = "Le relais reste en état sûr pendant la panne"


# ---- analyse du texte du programme ----

def _no_comments(source: str) -> str:
    """Le texte sans commentaires (les chaînes sont gardées, mais un // dans une chaîne n'est pas un commentaire)."""
    return re.sub(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', lambda m: m.group(0) if m.group(0)[0] == '"' else " ", source, flags=re.S)


SKIP_CN = re.compile(r"\bskip_cert_common_name_check\b(?!\s*=\s*(?:\(\s*bool\s*\)\s*)?(?:false|0)\s*[;,})])")
BYPASS = re.compile(r"\b(?:CONFIG_ESP_TLS_INSECURE|CONFIG_ESP_TLS_SKIP_SERVER_CERT_VERIFY|skip_server_cert_verify|skip_common_name)\b")
# Un nom qui désigne une clé NVS, un sujet ou une étiquette n'est pas un identifiant : NVS_CLE_MDP = "pass" est permis.
KEY_LIKE = re.compile(r"(?:cle|clef|key|nvs|espace|namespace|topic|tag|label|hint|msg|message|text)", re.I)
KEY_NAMES = {"user", "pass"}  # les clés NVS du TP : une chaîne qui ne vaut que ça n'est pas un identifiant
SECRET_NAME = r"\w*(?:mdp|pass(?:word|wd)?|passe|pwd|secret|token|utilisateur|username|user|login)\w*"
LITERAL_TO_SECRET = re.compile(rf"(?<![\w.])({SECRET_NAME}|(?:\w+\.)+(?:password|username)|\.(?:password|username))\s*(?:\[[^\]\n]*\])?\s*=(?!=)\s*\"([^\"\\\n]+)\"")
COPY_TO_SECRET = re.compile(rf"\b(?:strcpy|strncpy|strlcpy|memcpy|sprintf|snprintf)\s*\(\s*(?:\(\s*char\s*\*\s*\))?\s*(\w*(?:{SECRET_NAME}))\b[^;]*?\"([^\"\\\n]+)\"")
URI_USERINFO = re.compile(r"://[^/\s\"@:]+:[^/\s\"@]+@")


def _check_source(source: str) -> None:
    code = _code(source)
    m = SKIP_CN.search(code)
    need(not m, "le programme touche à skip_cert_common_name_check : cette option supprime la vérification du nom du courtier, ce qui "
         "expose le client aux attaques de l'homme du milieu (documentation d'esp-mqtt) ; n'écrivez pas ce champ (ou seulement "
         f"= false) (relire : « {S_NEVER} »)")
    m = BYPASS.search(code)
    need(not m, f"le programme utilise « {m and m.group(0)} » : une option qui coupe la vérification du certificat du serveur est "
         f"interdite, il faut fournir le certificat du courtier (relire : « {S_NEVER} »)")
    nc = _no_comments(source)
    for secret in (USER, PASS):
        need(secret not in nc, "un identifiant est écrit en clair dans le programme : le nom d'utilisateur et le mot de passe se lisent en "
             f"NVS, jamais dans le code (relire : « {S_CREDS} »)")
    need(not URI_USERINFO.search(nc), "l'URI du courtier contient un nom d'utilisateur et un mot de passe (mqtts://nom:mot@hôte) : "
         f"les identifiants se lisent en NVS, jamais dans le code (relire : « {S_CREDS} »)")
    for rx in (LITERAL_TO_SECRET, COPY_TO_SECRET):
        for m in rx.finditer(nc):
            if KEY_LIKE.search(m.group(1)) or m.group(2) in KEY_NAMES:
                continue
            need(False, f"« {m.group(1)} » reçoit une valeur écrite dans le programme : les identifiants se lisent en NVS, jamais "
                 f"dans le code (relire : « {S_CREDS} »)")


# ---- lecture de la trace ----

def _marks(trace: Trace) -> list[tuple[int, int]]:
    return trace.gpio_levels(PIN)


def _levels_in(marks: list[tuple[int, int]], a: int, b: int) -> set[int]:
    cur = 0
    for t, lv in marks:
        if t < a:
            cur = lv
    return {cur} | {lv for t, lv in marks if a <= t < b}


def _pin_states(marks: list[tuple[int, int]], t: int) -> set[int]:
    before = after = 0
    for tc, lv in marks:
        if tc < t:
            before = after = lv
        elif tc == t:
            after = lv
    return {before, after}


def _connections(trace: Trace, name: str) -> list[tuple[int, int]]:
    out, start = [], None
    for e in sorted(trace.events("mqtt"), key=lambda e: e["t_ms"]):
        if e["event"] == "connected":
            start = e["t_ms"]
        elif e["event"] == "disconnected" and start is not None:
            out.append((start, e["t_ms"]))
            start = None
    if start is not None:
        out.append((start, MAX_MS[name]))
    return out


def _why_not_connected(trace: Trace) -> str:
    """Ce que la poignée de main a dit, en une phrase, pour expliquer l'absence de connexion."""
    hs = trace.events("tls_handshake")
    if not hs:
        return ("aucune poignée de main TLS n'a eu lieu : l'adresse du courtier est-elle en mqtts:// et le client est-il démarré "
                f"(identifiants lus, étape 1) ? (relire : « {S_CLIENT} »)")
    fail = next((e for e in hs if not e["ok"]), None)
    if fail is None:
        return f"la poignée de main réussit mais le client ne signale pas de connexion (relire : « {S_CLIENT} »)"
    why = fail["verify"]
    if why == "failed:no_verification":
        return ("le client n'a aucune option de vérification : sans certificat, esp-tls refuse la connexion (« fatal error by "
                f"default » dans la documentation) ; donnez broker.verification.certificate (relire : « {S_EMBED} »)")
    if why == "failed:parse":
        return ("le certificat donné au client n'est pas un PEM valide : passez le symbole _binary_server_cert_pem_start, pas un texte "
                f"à vous (relire : « {S_EMBED} »)")
    if why == "failed:not_trusted":
        return ("le certificat fourni n'est pas celui du courtier, ou le paquet de certificats public (crt_bundle_attach) ne contient "
                f"pas l'autorité d'un courtier privé : fournissez son certificat (relire : « {S_CLIENT} »)")
    if why == "failed:cn_mismatch":
        return f"le nom du certificat du courtier ne correspond pas à l'hôte de l'URI (relire : « {S_CHAIN} »)"
    if why == "failed:expired":
        return f"le certificat présenté est expiré alors qu'il devrait être valide (relire : « {S_CHAIN} »)"
    return f"la poignée de main échoue ({why}) (relire : « {S_ERR} »)"


def _common(trace: Trace, name: str) -> None:
    label = LABELS[name]
    reboots = trace.events("reboot")
    need(not reboots, f"{label} : la carte a redémarré à {_s(reboots[0]['t_ms'] if reboots else 0)} : rien dans ce TP ne doit "
         f"redémarrer la carte (relire : « {S_RETRY} »)")
    need(trace.events("mqtt"), f"{label} : aucun événement MQTT : le client n'a jamais démarré. Les identifiants sont-ils lus en NVS "
         f"(étape 1, espace « mqtt », clés « user » et « pass ») et demarrer_mqtt appelle-t-il esp_mqtt_client_start ? "
         f"(relire : « {S_CREDS} »)")
    hs = trace.events("tls_handshake")
    need(hs, f"{label} : aucune poignée de main TLS : l'adresse du courtier doit commencer par mqtts:// (relire : « {S_CLIENT} »)")
    skipped = [e for e in hs if e["verify"] == "cn_skipped"]
    need(not skipped, f"{label} : la vérification du nom du courtier est désactivée (skip_cert_common_name_check) : le client "
         f"accepte un certificat au nom d'un autre serveur (relire : « {S_NEVER} »)")
    need(any(e["channel"] == CHANNEL for e in trace.events("adc_read")),
         f"{label} : aucune lecture du canal {CHANNEL} de l'ADC1 : la télémétrie lit le niveau sur le capteur (relire : « {S_SAFE} »)")
    need(any(e["pin"] == PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} du relais n'est pas configurée en sortie (relire : « {S_SAFE} »)")


def _check_credentials(trace: Trace, name: str) -> None:
    label = LABELS[name]
    for e in trace.events("mqtt", event="connected"):
        user, pw = e.get("username"), e.get("password")
        need(user is not None and pw is not None,
             f"{label} : la connexion de {_s(e['t_ms'])} ne transmet pas d'identifiants : renseignez credentials.username et "
             f"credentials.authentication.password avec ce qui est lu en NVS (relire : « {S_CREDS} »)")
        need(user == USER and pw == PASS,
             f"{label} : les identifiants de la connexion de {_s(e['t_ms'])} ne sont pas ceux enregistrés en NVS : lisez-les avec "
             f"nvs_get_str, ne les écrivez pas dans le code (relire : « {S_CREDS} »)")


def _check_subscriptions(trace: Trace, name: str) -> None:
    label = LABELS[name]
    connected = [e["t_ms"] for e in trace.events("mqtt", event="connected")]
    bounds = connected[1:] + [MAX_MS[name] + 1]
    for tc, nxt in zip(connected, bounds):
        subs = [e for e in trace.events("mqtt_subscribe") if tc <= e["t_ms"] <= min(tc + SETUP_MS, nxt) and _match(e["topic"], T_CMD)]
        need(subs, f"{label} : aucun abonnement à « {T_CMD} » dans les {_s(SETUP_MS)} qui suivent la connexion de {_s(tc)} : la session "
             f"est propre, le courtier a tout oublié : il faut s'abonner dans la réaction à MQTT_EVENT_CONNECTED, à chaque "
             f"connexion (relire : « {S_RETRY} »)")


def _check_relay(trace: Trace, name: str) -> None:
    label = LABELS[name]
    marks = _marks(trace)
    tl = RELAY[name]
    for i, (t, state, tol, kind) in enumerate(tl):
        stop = tl[i + 1][0] if i + 1 < len(tl) else MAX_MS[name]
        got = _levels_in(marks, t + tol, stop)
        if got == {state}:
            continue
        if kind == "safe":
            need(False, f"{label} : le relais est encore allumé après la perte de la liaison à {_s(t)} (au plus {_s(SAFE_MS)} accordées) "
                 f"ou se rallume avant la prochaine commande : sans liaison sûre plus personne ne surveille la pompe, on l'éteint "
                 f"et on la laisse éteinte (relire : « {S_SAFE} »)")
        if name == "c":
            need(False, f"{label} : le relais est allumé alors que le client ne doit jamais se connecter : une commande n'a pu "
                 f"venir que d'une connexion non vérifiée (relire : « {S_NEVER} »)")
        need(False, f"{label} : après la commande de {_s(t)}, le relais devrait être {'allumé' if state else 'éteint'} dans la seconde "
             f"(niveau 72,5 %, sous la limite de 80 %) : le programme est-il abonné à chaque connexion et le gestionnaire traite-t-il "
             f"la commande ? (relire : « {S_RETRY} »)")


def _check_telemetry(trace: Trace, name: str) -> None:
    label = LABELS[name]
    pubs = trace.events("mqtt_publish", topic=T_TELE)
    need(pubs, f"{label} : aucun message sur « {T_TELE} » : la télémétrie se publie dès que le client est connecté (relire : « {S_RETRY} »)")
    marks = _marks(trace)
    for e in pubs:
        t, text = e["t_ms"], e["payload"]
        try:
            obj = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        except ValueError:
            need(False, f"{label} : le message de {_s(t)} n'est pas un JSON valide : « {text} » (relire : « {S_RETRY} »)")
        need(isinstance(obj, dict) and set(obj) == {"level", "relay"},
             f"{label} : le message de {_s(t)} (« {text} ») doit avoir exactement les clés level et relay : ne modifiez pas "
             f"publier_telemetrie (relire : « {S_RETRY} »)")
        level, relay = obj["level"], obj["relay"]
        need(isinstance(level, (int, float)) and not isinstance(level, bool) and abs(level - LEVEL) <= LEVEL_TOL,
             f"{label} : niveau publié {level!r} à {_s(t)} alors que le niveau lu est de 72,5 % (relire : « {S_RETRY} »)")
        need(isinstance(relay, bool) and int(relay) in _pin_states(marks, t),
             f"{label} : le message de {_s(t)} annonce relay={str(relay).lower()}, ce n'est pas l'état réel du relais (relire : « {S_SAFE} »)")
    times = [e["t_ms"] for e in pubs]
    for a, b in _connections(trace, name):
        if b - a < TELE_MAX_MS + 1_000:
            continue
        sel = [t for t in times if a <= t <= b]
        need(sel, f"{label} : aucune télémétrie pendant la connexion de {_s(a)} à {_s(b)} : elle reprend après chaque reconnexion "
             f"(relire : « {S_RETRY} »)")
        need(sel[0] - a <= TELE_MAX_MS, f"{label} : première télémétrie de la connexion de {_s(a)} à {_s(sel[0])} : il en faut une toutes "
             f"les 10 s (relire : « {S_RETRY} »)")
        need(b - sel[-1] <= TELE_MAX_MS, f"{label} : plus de télémétrie après {_s(sel[-1])}, la connexion dure jusqu'à {_s(b)} (relire : « {S_RETRY} »)")
        for x, y in zip(sel, sel[1:]):
            need(TELE_MIN_MS <= y - x <= TELE_MAX_MS, f"{label} : {_s(y - x)} entre deux télémétries ({_s(x)} puis {_s(y)}) : la période "
                 f"est de 10 s, de {_s(TELE_MIN_MS)} à {_s(TELE_MAX_MS)} acceptées (relire : « {S_RETRY} »)")


def _series(trace: Trace) -> list[list[list]]:
    """Chaque série d'échecs de suite : [[t de MQTT_EVENT_DISCONNECTED, t de la tentative suivante ou None], ...]."""
    out: list[list[list]] = []
    cur, pending = None, None
    for e in sorted(trace.events("mqtt"), key=lambda e: e["t_ms"]):
        if e["event"] == "connected":
            cur = pending = None
        elif e["event"] == "disconnected":
            if cur is None:
                cur = []
                out.append(cur)
            pending = [e["t_ms"], None]
            cur.append(pending)
        elif e["event"] == "before_connect" and pending is not None and pending[1] is None:
            pending[1] = e["t_ms"]
    return out


def _check_backoff(trace: Trace, name: str) -> None:
    label = LABELS[name]
    end = MAX_MS[name]
    for n, series in enumerate(_series(trace), 1):
        waits = [b - a for a, b in series if b is not None]
        start = series[0][0]
        where = f"la série d'échecs commencée à {_s(start)}"
        for a, b in series:
            need(b is not None or end - a <= TAIL_MS,
                 f"{label} : plus aucune tentative de connexion après l'échec de {_s(a)} (la fin est à {_s(end)}) : le client ne doit "
                 f"jamais abandonner, il réessaie tant que la liaison n'est pas rétablie (relire : « {S_RETRY} »)")
        if not waits:
            continue
        need(WAIT_FIRST_MIN <= waits[0] <= WAIT_FIRST_MAX,
             f"{label} : {where} : la première attente est de {_s(waits[0])} au lieu de 1 s à 3 s : "
             + ("on ne rappelle pas aussitôt (boucle serrée)" if waits[0] < WAIT_FIRST_MIN else
                "l'attente doit repartir de 1 s après chaque connexion réussie (echecs remis à 0)")
             + f" (relire : « {S_RETRY} »)")
        for k in range(1, len(waits)):
            need(waits[k] >= waits[k - 1] - WAIT_SHRINK_MS,
                 f"{label} : {where} : l'attente raccourcit ({_s(waits[k - 1])} puis {_s(waits[k])}) : elle croît à chaque échec "
                 f"(relire : « {S_RETRY} »)")
        if len(waits) >= 2:
            need(waits[1] >= WAIT_GROWTH * waits[0],
                 f"{label} : {where} : la deuxième attente ({_s(waits[1])}) n'est pas au moins {str(WAIT_GROWTH).replace('.', ',')} fois la "
                 f"première ({_s(waits[0])}) : elle double à chaque échec (relire : « {S_RETRY} »)")
        if len(waits) >= WAIT_REACH_COUNT:
            need(max(waits[:WAIT_REACH_COUNT]) >= WAIT_REACH,
                 f"{label} : {where} : après {WAIT_REACH_COUNT} échecs l'attente n'a pas atteint {_s(WAIT_REACH)} (plus long attente "
                 f"{_s(max(waits[:WAIT_REACH_COUNT]))}) : elle double jusqu'au plafond (relire : « {S_RETRY} »)")
        need(max(waits) <= WAIT_CAP_MS, f"{label} : {where} : une attente de {_s(max(waits))} dépasse {_s(WAIT_CAP_MS)} : l'attente a un "
             f"plafond (8 s dans ce TP) (relire : « {S_RETRY} »)")


# ---- les trois exécutions ----

def _check_a(trace: Trace) -> None:
    label = LABELS["a"]
    connected = trace.events("mqtt", event="connected")
    need(connected, f"{label} : le client n'a jamais pu se connecter : {_why_not_connected(trace)}")
    bad = [e for e in trace.events("tls_handshake") if e["verify"] != "ok"]
    need(not bad, f"{label} : la poignée de main TLS de {_s(bad[0]['t_ms'] if bad else 0)} n'est pas une vérification complète "
         f"({bad[0]['verify'] if bad else ''}) (relire : « {S_NEVER} »)")
    _check_credentials(trace, "a")
    _check_subscriptions(trace, "a")
    _check_relay(trace, "a")
    _check_telemetry(trace, "a")
    _check_backoff(trace, "a")
    need(not any("command refused" in e["msg"] for e in trace.logs(tag="tls")),
         f"{label} : une commande est refusée alors que le niveau est de 72,5 %, sous la limite de 80 % : ne modifiez pas "
         f"traiter_commande (relire : « {S_SAFE} »)")


def _check_b(trace: Trace) -> None:
    label = LABELS["b"]
    connected = [e["t_ms"] for e in trace.events("mqtt", event="connected")]
    need(connected, f"{label} : le client n'a jamais pu se connecter : {_why_not_connected(trace)}")
    lo, hi = HANDSHAKE_FAIL_B
    need(not any(lo <= t < hi for t in connected), f"{label} : le client se déclare connecté pendant la panne de {_s(lo)} à {_s(hi)} : "
         f"il accepte une poignée de main qui échoue (relire : « {S_ERR} »)")
    fails = [e for e in trace.events("tls_handshake") if lo <= e["t_ms"] < hi]
    need(fails, f"{label} : aucune tentative de poignée de main entre {_s(lo)} et {_s(hi)} : après la perte de la liaison le client doit "
         f"réessayer (esp_mqtt_client_reconnect après l'attente), il n'abandonne jamais (relire : « {S_RETRY} »)")
    need(len(fails) >= 4 and all(e["verify"] == "failed:handshake" for e in fails),
         f"{label} : pendant la panne de {_s(lo)} à {_s(hi)} le client doit tenter la poignée de main plusieurs fois, chaque fois sans "
         f"succès ({len(fails)} tentative(s) trouvée(s)) (relire : « {S_RETRY} »)")
    back = [t for t in connected if hi <= t < 240_000]
    need(back, f"{label} : le client ne s'est pas reconnecté entre {_s(hi)} et 240 s alors que le courtier répond de nouveau : il ne "
         f"doit jamais abandonner, l'attente a un plafond (8 s) (relire : « {S_RETRY} »)")
    need(any(t >= OUTAGE_B[1][1] for t in connected), f"{label} : le client ne s'est pas reconnecté après la coupure du courtier de "
         f"{_s(OUTAGE_B[1][0])} à {_s(OUTAGE_B[1][1])} (relire : « {S_RETRY} »)")
    _check_credentials(trace, "b")
    _check_subscriptions(trace, "b")
    _check_relay(trace, "b")
    _check_telemetry(trace, "b")
    _check_backoff(trace, "b")
    series = _series(trace)
    need(len(series) >= 2, f"{label} : la coupure du courtier de {_s(OUTAGE_B[1][0])} n'a pas déclenché de nouvelle série de "
         f"tentatives (relire : « {S_RETRY} »)")


def _check_c(trace: Trace) -> None:
    label = LABELS["c"]
    hs = trace.events("tls_handshake")
    connected = trace.events("mqtt", event="connected")
    need(not connected, f"{label} : le client s'est connecté à {_s(connected[0]['t_ms'] if connected else 0)} alors que le certificat du "
         f"courtier est expiré : la vérification doit refuser cette connexion (relire : « {S_NEVER} »)")
    other = [e for e in hs if e["verify"] != "failed:expired"]
    need(not other, f"{label} : la poignée de main de {_s(other[0]['t_ms'] if other else 0)} échoue pour une autre raison "
         f"({other[0]['verify'] if other else ''}) que le certificat expiré : {_why_not_connected(trace)}")
    need(len(hs) >= 6, f"{label} : seulement {len(hs)} tentative(s) de connexion en {_s(MAX_MS['c'])} : après un échec le client "
         f"réessaie (attente croissante, plafond de 8 s), il n'abandonne jamais (relire : « {S_RETRY} »)")
    errors = [e for e in trace.events("mqtt", event="error") if e.get("esp_tls_last_esp_err")]
    need(errors, f"{label} : aucune erreur TLS signalée par le client : MQTT_EVENT_ERROR doit porter les codes d'esp-tls "
         f"(relire : « {S_ERR} »)")
    _check_relay(trace, "c")
    need(not trace.events("mqtt_publish"), f"{label} : un message est publié alors que le client n'a jamais été connecté (relire : « {S_NEVER} »)")
    _check_backoff(trace, "c")
    code = errors[0]["esp_tls_last_esp_err"]
    forms = {f"{code:x}", str(code)}
    warned = [e for e in trace.logs(tag="tls") if e["level"] in ("W", "E") and any(f in e["msg"].lower() for f in forms)]
    need(warned, f"{label} : l'échec de la poignée de main n'est pas journalisé avec son code : écrivez un ESP_LOGW de tag « tls » dans la "
         f"réaction à MQTT_EVENT_ERROR, avec esp_tls_last_esp_err (en hexadécimal, %x, ou en décimal) (relire : « {S_ERR} »)")


def verify(traces: dict, source: str) -> None:
    _check_source(source)
    for name, check in (("a", _check_a), ("b", _check_b), ("c", _check_c)):
        _common(traces[name], name)
        check(traces[name])
