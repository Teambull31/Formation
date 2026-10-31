"""Boss final, phase 2 : le contrôleur connecté (Wi-Fi, MQTT sur TLS, reprise après coupure, consigne en NVS ; leçons es10 et es9).

Le programme de la phase 1 se connecte : Wi-Fi, puis MQTT sur TLS (mqtts://broker.local:8883, certificat du courtier embarqué
_binary_server_cert_pem_start, jamais de vérification désactivée), identifiants lus en NVS (espace « mqtt », clés « user » et « pass »), abonnement à
home/devices/pool-ctl/command à chaque connexion, télémétrie toutes les 10 s sur home/devices/pool-ctl/telemetry : {"level": 72.5, "relay": false,
"high": 80}. La consigne haute `high` (80 % par défaut, bornée à 40..80 %) arrive par {"high": N} ; la pompe démarre 20 points sous elle
(60 % par défaut) et s'arrête au-dessus ; elle est enregistrée en NVS (nvs_commit) et relue au démarrage, avant de piloter la pompe.
Règle de sécurité : la pompe ne tourne QUE tant que la liaison MQTT est établie ; sans liaison elle est éteinte et le reste.

Exécutions (SCENARIOS), toutes avec un courtier valide, sauf j :
  a à f : les six exécutions de la phase 1 (régulation et capteur qui ment), rejouées avec la liaison : mêmes tolérances, même jugement.
  g : niveau 50 %. « salut » à 10 s (ignoré), {"high": 95} à 20 s et {"high": 30} à 25 s (refusées, journalisées), {"high": 40} à 30 s (acceptée :
      pompe éteinte), coupure de courant à 60 s : la consigne 40 est relue AVANT de piloter la pompe, qui ne se rallume pas ; {"high": 80} à 70 s
      (reçue seulement si le programme s'est réabonné après le redémarrage) : pompe allumée.
  h : niveau de départ 56 %, remplissage de 2,5 points par minute, évaporation de 0,4 : courtier coupé de 60 s à 200 s (pompe allumée au moment de la
      coupure : elle doit s'éteindre) ; {"high": 70} à 300 s (reçue seulement si le programme s'est réabonné) : arrêt vers 70 %. Le niveau vrai est rejoué.
  i : niveau 50 %. Wi-Fi coupé de 40 s à 80 s (la liaison MQTT tombe avec lui) ; {"high": 40} à 150 s.
  j : niveau 50 %, certificat du courtier expiré : le client ne se connecte JAMAIS (vérification maintenue), réessaie sans abandonner, journalise le code
      de l'erreur TLS ; la pompe reste éteinte.

Tolérances : pompe commutée au plus 2 s après une commande, au plus 2 s après une perte de liaison, au plus 8 s après le démarrage ; abonnement dans
les 5 s qui suivent chaque connexion ; connexion rétablie au plus 30 s après le retour du réseau ou du courtier ; télémétrie de 9 s à 11 s entre deux
messages d'une même connexion ; nvs_commit dans les 2 s de chaque écriture ; au moins 5 tentatives de connexion en 2 minutes dans j.
Format des lignes : « setpoint refused: high=N » (ESP_LOGW, tag « pool »), une seule fois par commande refusée ; l'échec TLS en ESP_LOGW ou
ESP_LOGE de tag « tls » avec le code esp_tls_last_esp_err (hexadécimal ou décimal).

Le contrôle lit aussi le texte du programme (commentaires et chaînes retirés) : aucune option qui réduit la vérification TLS, aucun identifiant
en clair (comme au TP 10).
"""
import json

from esp_trace import Trace, fmt_pct as _pct, fmt_s as _s, need, relay_states as _relay_states, load_check, topic_match as _match

es6 = load_check("es6-tp")
es9 = load_check("es9-tp")
es10 = load_check("es10-tp")
es7 = load_check("es7-tp")
p1 = load_check("esp_boss_p1")

PIN, CHANNEL = es6.PIN, es6.CHANNEL
BASE = p1.BASE
T_TELE, T_CMD = p1.T_TELE, p1.T_CMD
USER, PASS = p1.USER, p1.PASS
HIGH_DEFAULT, HIGH_MIN, HIGH_MAX, GAP = 80, 40, 80, 20
LEVEL = 50.0
LEVEL_TOL = 1.0
REACT_MS, SAFE_MS, BOOT_MS, SETUP_MS, COMMIT_MS, TELE_MS = 2_000, 2_000, 8_000, 5_000, 2_000, 1_000
RECONNECT_MS = 30_000
TELE_MIN_MS, TELE_MAX_MS = 9_000, 11_000
MIN_ATTEMPTS = 5
OUTPUT_MODES = es6.OUTPUT_MODES
MAX_OUT = 12_000_000  # la phase 1 dure 2 h (a) : le plafond est celui du TP es6

S_SAFE_START = es6.S_SAFE
S_SAFE, S_NEVER, S_CREDS, S_ERR, S_CLIENT = es10.S_SAFE, es10.S_NEVER, es10.S_CREDS, es10.S_ERR, es10.S_CLIENT
S_WIFI = es7.S_EVENTS
S_RECONNECT, S_SETPOINT, S_NVS, S_BOOT = es9.S_RECONNECT, es9.S_SETPOINT, es9.S_NVS, es9.S_BOOT


_tank, net = p1._tank, p1.net


G_IN = [(10_000, "salut"), (20_000, '{"high": 95}'), (25_000, '{"high":30}'), (30_000, '{"high": 40}'), (70_000, '{"high": 80}')]
REBOOTS = {**{k: [] for k in "abcdefhij"}, "g": [60_000]}  # les redémarrages du scénario ; une exécution absente d'ici (OTA, phase 3) les juge elle-même
OUTAGES = {"h": [(60_000, 200_000)], "i": [(40_000, 80_000)]}  # (début, fin) de la panne ; la liaison revient après
H_IN = [(300_000, '{"high": 70}')]
I_IN = [(150_000, '{"high": 40}')]
MAX_MS = {**{k: ms for k, (_, ms) in p1.SCENARIOS.items()}, "g": 100_000, "h": 700_000, "i": 200_000, "j": 120_000}
LEVEL_OF = {"g": LEVEL, "i": LEVEL}  # niveau constant : la télémétrie doit le dire
# (t_ms, consigne en vigueur à partir de t)
HIGH_AT = {"g": [(0, 80), (30_000, 40), (70_000, 80)], "h": [(0, 80), (300_000, 70)], "i": [(0, 80), (150_000, 40)]}

SCENARIOS = dict(p1.SCENARIOS)  # a à f : déjà avec le réseau
SCENARIOS["g"] = (net(_tank(LEVEL), G_IN, reboots=REBOOTS["g"]), MAX_MS["g"])
SCENARIOS["h"] = (net(_tank(56, es6.FILL_PER_MIN, es6.LOSS_PER_MIN), H_IN, broker_down=OUTAGES["h"]), MAX_MS["h"])
SCENARIOS["i"] = (net(_tank(LEVEL), I_IN, wifi_down=OUTAGES["i"]), MAX_MS["i"])
SCENARIOS["j"] = (net(_tank(LEVEL), cert_valid=False), MAX_MS["j"])
LABELS = {**p1.LABELS,
          "g": "scénario g (consigne par MQTT, refus, redémarrage à 60 s)",
          "h": "scénario h (courtier coupé de 60 s à 200 s, remplissage en cours)",
          "i": "scénario i (Wi-Fi coupé de 40 s à 80 s)",
          "j": "scénario j (certificat du courtier expiré)"}


# ---- la liaison et le relais, lus dans la trace ----

def _marks(trace: Trace) -> list[tuple[int, int]]:
    """Toutes les écritures sur la broche, dans l'ordre ; un redémarrage remet la broche à 0 avant l'écriture qui suit."""
    return es9._relay_marks(trace)


def _levels_in(marks, a: int, b: int, fresh: bool = False) -> set[int]:
    return es9._levels_in(marks, a, b, fresh)


def _changes(trace: Trace) -> list[tuple[int, int]]:
    return es9._relay_changes(trace)


def _connections(trace: Trace, end_ms: int) -> list[tuple[int, int, str]]:
    """[(début, fin, cause)] de chaque période de liaison ; cause : « lost » (déconnexion), « reboot » ou « end »."""
    marks = sorted((e["t_ms"], e["event"] if e["ev"] == "mqtt" else "reboot")
                   for e in trace.events("mqtt") + trace.events("reboot") if e["ev"] == "reboot" or e["event"] in ("connected", "disconnected"))
    out, start = [], None
    for t, what in marks:
        if what == "connected":
            start = t
        elif start is not None:
            out.append((start, t, "reboot" if what == "reboot" else "lost"))
            start = None
    if start is not None:
        out.append((start, end_ms, "end"))
    return out


def _relay_first(trace: Trace, label: str) -> None:
    """À chaque démarrage, le relais est configuré en sortie et éteint avant le Wi-Fi, la NVS, le capteur et MQTT."""
    evs = trace.all()
    cuts = [i + 1 for i, e in enumerate(evs) if e["ev"] == "reboot"]
    segs = [evs[a:b] for a, b in zip([0, *cuts], [*cuts, len(evs)])]
    for k, seg in enumerate(segs, 1):
        when = f"au démarrage n° {k}" if len(segs) > 1 else "au démarrage"
        cfg = next((i for i, e in enumerate(seg) if e["ev"] == "gpio_config" and e["pin"] == PIN and e["mode"] in OUTPUT_MODES), None)
        off = next((i for i, e in enumerate(seg) if e["ev"] == "gpio_set" and e["pin"] == PIN and e["level"] == 0), None)
        other = next((i for i, e in enumerate(seg) if e["ev"] in ("wifi", "mqtt", "adc_read", "nvs_set", "nvs_commit")), None)
        need(cfg is not None and off is not None,
             f"{label} : {when}, le relais (GPIO {PIN}) n'est pas configuré en sortie et mis à 0 (relire : « {S_SAFE_START} »)")
        need(other is None or max(cfg, off) < other,
             f"{label} : {when}, le relais n'est configuré et éteint qu'après « {seg[other]['ev']} » (le Wi-Fi, la NVS, le capteur ou MQTT ont déjà "
             f"démarré) : pendant ce temps il peut rester allumé ; faites-le en tout premier dans app_main (relire : « {S_SAFE_START} »)")


def _only_with_link(trace: Trace, name: str) -> None:
    label = LABELS[name]
    conns = _connections(trace, MAX_MS[name])
    for t, lv in _changes(trace):
        if lv == 1:
            need(any(a <= t <= b for a, b, _ in conns),
                 f"{label} : la pompe s'allume à {_s(t)} alors que la liaison MQTT n'est pas établie : sans liaison plus personne ne "
                 f"surveille ni ne commande la pompe, elle ne tourne que liaison établie (relire : « {S_SAFE} »)")


def _net_ok(trace: Trace, name: str) -> None:
    label = LABELS[name]
    reboots = [e["t_ms"] for e in trace.events("reboot")]
    want = REBOOTS.get(name)
    need(want is None or (reboots == want and all(e["reason"] == "scripted" for e in trace.events("reboot"))),
         f"{label} : redémarrage(s) inattendu(s) : {', '.join(_s(t) for t in reboots) or 'aucun'} au lieu de {', '.join(_s(t) for t in want or []) or 'aucun'} : "
         f"rien ne doit redémarrer la carte (esp_restart, watchdog, ESP_ERROR_CHECK qui échoue) (relire : « {S_ERR} »)")
    _relay_first(trace, label)
    need(any(e["pin"] == PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} de la pompe n'est pas configurée en sortie (relire : « {S_SAFE_START} »)")
    need(trace.events("wifi", event="got_ip"),
         f"{label} : le Wi-Fi n'obtient jamais d'adresse IP : esp_wifi_connect est appelée dans le gestionnaire d'événements, à WIFI_EVENT_STA_START "
         f"et à chaque WIFI_EVENT_STA_DISCONNECTED, et le programme attend l'adresse avant de démarrer MQTT (relire : « {S_WIFI} »)")
    hs = trace.events("tls_handshake")
    need(hs, f"{label} : aucune poignée de main TLS : l'adresse du courtier doit commencer par mqtts:// (relire : « {S_CLIENT} »)")
    need(not [e for e in hs if e["verify"] == "cn_skipped"],
         f"{label} : la vérification du nom du courtier est désactivée (skip_cert_common_name_check) : le client accepte un certificat au nom d'un "
         f"autre serveur (relire : « {S_NEVER} »)")
    connected = trace.events("mqtt", event="connected")
    need(connected, f"{label} : le client MQTT ne s'est jamais connecté : {es10._why_not_connected(trace)}")
    bad = [e for e in hs if e["verify"] != "ok" and e["t_ms"] < connected[0]["t_ms"] and name != "i"]
    need(not bad, f"{label} : la poignée de main TLS de {_s(bad[0]['t_ms'] if bad else 0)} n'est pas une vérification complète "
         f"({bad[0]['verify'] if bad else ''}) : {es10._why_not_connected(trace)}")
    for e in connected:
        user, pw = e.get("username"), e.get("password")
        need(user is not None and pw is not None, f"{label} : la connexion de {_s(e['t_ms'])} ne transmet pas d'identifiants : renseignez "
             f"credentials.username et credentials.authentication.password avec ce qui est lu en NVS (relire : « {S_CREDS} »)")
        need(user == USER and pw == PASS, f"{label} : les identifiants de la connexion de {_s(e['t_ms'])} ne sont pas ceux enregistrés en NVS : "
             f"lisez-les avec nvs_get_str, ne les écrivez pas dans le code (relire : « {S_CREDS} »)")
    times = [e["t_ms"] for e in connected]
    bounds = times[1:] + [MAX_MS[name] + 1]
    for tc, nxt in zip(times, bounds):
        subs = [e for e in trace.events("mqtt_subscribe") if tc <= e["t_ms"] <= min(tc + SETUP_MS, nxt) and _match(e["topic"], T_CMD)]
        need(subs, f"{label} : aucun abonnement à « {T_CMD} » dans les {_s(SETUP_MS)} qui suivent la connexion de {_s(tc)} : la session est propre, le "
             f"courtier a tout oublié : il faut s'abonner dans la réaction à MQTT_EVENT_CONNECTED, à chaque connexion (relire : « {S_RECONNECT} »)")
    _only_with_link(trace, name)
    _telemetry(trace, name)


def _high_at(name: str, t: int) -> set[int]:
    """Consignes admissibles à l'instant t (l'ancienne et la nouvelle pendant la seconde qui suit un changement)."""
    cur = prev = HIGH_DEFAULT
    for tc, v in HIGH_AT.get(name, [(0, HIGH_DEFAULT)]):
        if tc <= t:
            prev, cur = cur, v
            if t - tc <= TELE_MS:
                return {prev, cur}
    return {cur}


def _telemetry(trace: Trace, name: str) -> None:
    label = LABELS[name]
    pubs = trace.events("mqtt_publish", topic=T_TELE)
    need(pubs, f"{label} : aucun message sur « {T_TELE} » : la télémétrie se publie dès que le client est connecté (relire : « {S_SETPOINT} »)")
    changes = _changes(trace)
    for e in pubs:
        t, text = e["t_ms"], e["payload"]
        try:
            obj = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        except ValueError:
            need(False, f"{label} : le message de {_s(t)} n'est pas un JSON valide : « {text} » (relire : « {S_SETPOINT} »)")
        need(isinstance(obj, dict) and set(obj) == {"level", "relay", "high"},
             f"{label} : le message de {_s(t)} (« {text} ») doit avoir exactement les clés level, relay et high (relire : « {S_SETPOINT} »)")
        level, relay, high = obj["level"], obj["relay"], obj["high"]
        need(isinstance(level, (int, float)) and not isinstance(level, bool) and 0 <= level <= 100,
             f"{label} : niveau publié {level!r} à {_s(t)} : un nombre de 0 à 100 est attendu (relire : « {S_SETPOINT} »)")
        if name in LEVEL_OF:
            need(abs(level - LEVEL_OF[name]) <= LEVEL_TOL, f"{label} : niveau publié {level!r} à {_s(t)} alors que le niveau lu est de "
                 f"{_pct(LEVEL_OF[name])} % (relire : « {S_SETPOINT} »)")
        need(isinstance(relay, bool) and int(relay) in _relay_states(changes, t),
             f"{label} : le message de {_s(t)} annonce relay={str(relay).lower()}, ce n'est pas l'état réel de la pompe (relire : « {S_SAFE} »)")
        ok = _high_at(name, t)
        need(isinstance(high, int) and not isinstance(high, bool) and high in ok,
             f"{label} : le message de {_s(t)} annonce la consigne {high!r} % alors qu'elle vaut {' ou '.join(str(v) for v in sorted(ok))} % à cet "
             f"instant : une consigne refusée a-t-elle été acceptée, la consigne enregistrée a-t-elle été relue au démarrage, ou la commande "
             f"a-t-elle été appliquée ? (relire : « {S_SETPOINT} »)")
    times = [e["t_ms"] for e in pubs]
    # Une mise à jour OTA bloque la boucle principale le temps du téléchargement (2,1 s dans le simulateur) : la période s'allonge d'autant.
    ends = [e["t_ms"] for e in trace.events("ota_end")]
    quiet = [(b["t_ms"], min([t for t in ends if t >= b["t_ms"]], default=b["t_ms"] + 3_000) + TELE_MS) for b in trace.events("ota_begin")]
    for a, b, _ in _connections(trace, MAX_MS[name]):
        sel = [t for t in times if a <= t <= b]
        if b - a >= TELE_MAX_MS + 1_000:
            need(sel, f"{label} : aucune télémétrie pendant la connexion de {_s(a)} à {_s(b)} : elle reprend après chaque reconnexion (relire : « {S_ERR} »)")
            need(sel[0] - a <= TELE_MAX_MS, f"{label} : première télémétrie de la connexion de {_s(a)} à {_s(sel[0])} : il en faut une toutes les "
                 f"10 s (relire : « {S_ERR} »)")
            need(b - sel[-1] <= TELE_MAX_MS, f"{label} : plus de télémétrie après {_s(sel[-1])}, la connexion dure jusqu'à {_s(b)} (relire : « {S_ERR} »)")
        for x, y in zip(sel, sel[1:]):
            if x - a <= TELE_MS or any(x < qb and y > qa for qa, qb in quiet):
                continue
            need(TELE_MIN_MS <= y - x <= TELE_MAX_MS, f"{label} : {_s(y - x)} entre deux télémétries ({_s(x)} puis {_s(y)}) : la période est de "
                 f"10 s, de {_s(TELE_MIN_MS)} à {_s(TELE_MAX_MS)} acceptées (relire : « {S_ERR} »)")


# ---- g : la consigne ----

def _check_g(trace: Trace) -> None:
    label = LABELS["g"]
    marks = _marks(trace)
    # (t, état attendu, délai accordé, après un redémarrage ?) : à partir de t + délai et jusqu'à l'instant suivant.
    plan = [(0, 1, BOOT_MS, False), (30_000, 0, REACT_MS, False), (60_000, 0, 0, True), (70_000, 1, REACT_MS, False)]
    for i, (t, state, tol, fresh) in enumerate(plan):
        stop = plan[i + 1][0] if i + 1 < len(plan) else MAX_MS["g"]
        got = _levels_in(marks, t + tol, stop, fresh=fresh and t > 0)
        if got == {state}:
            continue
        if fresh:
            need(False, f"{label} : la pompe est allumée après le redémarrage de {_s(t)} alors que la consigne enregistrée (40 %) interdit de "
                 f"l'allumer à 50 % : enregistrez la consigne (nvs_set_i32 puis nvs_commit) et relisez-la en NVS AVANT de piloter la pompe, sans "
                 f"repasser par la valeur par défaut (80 %) (relire : « {S_BOOT} »)")
        if t == 0:
            need(False, f"{label} : la pompe n'est pas allumée dans les {_s(BOOT_MS)} qui suivent le démarrage alors que le niveau (50 %) est sous "
                 f"60 % et que la liaison est établie (relire : « {S_SAFE} »)")
        need(False, f"{label} : après la commande de {_s(t)}, la pompe devrait être {'allumée' if state else 'éteinte'} dans les {_s(REACT_MS)} "
             f"(niveau 50 %) : le programme est-il abonné (à chaque connexion, y compris après le redémarrage) et applique-t-il la consigne ? "
             f"(relire : « {S_RECONNECT} »)")
    refused = [e for e in trace.logs(tag="pool") if e["msg"].startswith("setpoint refused")]
    for t, text in ((20_000, "high=95"), (25_000, "high=30")):
        msg = f"setpoint refused: {text}"
        hit = [e for e in refused if e["msg"] == msg and e["level"] == "W" and t <= e["t_ms"] <= t + REACT_MS]
        near = f" (message trouvé : « {refused[0]['msg']} », niveau {refused[0]['level']})" if refused else ""
        need(hit, f"{label} : la consigne reçue à {_s(t)} doit être refusée par un ESP_LOGW de tag « pool » au format exact « {msg} »{near} "
             f"(bornes acceptées : {HIGH_MIN} à {HIGH_MAX} %) (relire : « {S_SETPOINT} »)")
    extra = [e for e in refused if not any(e["msg"] == f"setpoint refused: {x}" and t <= e["t_ms"] <= t + REACT_MS
                                           for t, x in ((20_000, "high=95"), (25_000, "high=30")))]
    need(not extra, f"{label} : la ligne « {extra[0]['msg'] if extra else ''} » à {_s(extra[0]['t_ms'] if extra else 0)} refuse une commande qui n'est "
         f"pas hors des bornes {HIGH_MIN}..{HIGH_MAX} % (ou la refuse deux fois) : seules les consignes hors bornes sont refusées, une ligne chacune ; "
         f"un texte qui n'est pas une commande est ignoré en silence (relire : « {S_SETPOINT} »)")
    sets = [e for e in trace.events("nvs_set") if e["ns"] != "mqtt"]
    need(any(e.get("value") == 40 for e in sets), f"{label} : la consigne acceptée (40 %) n'est jamais écrite en NVS : sans cela elle ne survit pas au "
         f"redémarrage (nvs_set_i32 puis nvs_commit) (relire : « {S_NVS} »)")
    commits = trace.events("nvs_commit")
    for e in sets:
        need(any(c["ns"] == e["ns"] and e["t_ms"] <= c["t_ms"] <= e["t_ms"] + COMMIT_MS for c in commits),
             f"{label} : l'écriture de « {e['key']} » à {_s(e['t_ms'])} n'est pas suivie de nvs_commit : sans lui rien n'est garanti après un "
             f"redémarrage (le simulateur, plus strict que la carte, perd l'écriture) (relire : « {S_NVS} »)")
        need(e.get("value") not in (95, 30), f"{label} : la valeur {e.get('value')} (refusée) est enregistrée en NVS à {_s(e['t_ms'])} : on ne "
             f"sauvegarde qu'une consigne acceptée (relire : « {S_SETPOINT} »)")


# ---- h et i : coupure de la liaison ----

def _check_outage(trace: Trace, name: str) -> None:
    label = LABELS[name]
    end = MAX_MS[name]
    conns = _connections(trace, end)
    marks = _marks(trace)
    for k, (a, b) in enumerate(OUTAGES[name]):
        lost = [c for c in conns if a <= c[1] <= a + SAFE_MS and c[2] == "lost"]
        need(lost, f"{label} : la liaison n'est pas signalée perdue à {_s(a)} (MQTT_EVENT_DISCONNECTED) : le client MQTT est-il démarré et "
             f"le gestionnaire reçoit-il tous les événements ? (relire : « {S_RECONNECT} »)")
        again = [c for c in conns if b <= c[0] <= b + RECONNECT_MS]
        need(again, f"{label} : la liaison n'est pas rétablie dans les {_s(RECONNECT_MS)} qui suivent le retour "
             f"{'du courtier' if name == 'h' else 'du Wi-Fi'} à {_s(b)} : le client ne doit jamais abandonner (la bibliothèque se reconnecte d'elle-même "
             f"toutes les 10 s ; en Wi-Fi, il faut aussi rappeler esp_wifi_connect après chaque WIFI_EVENT_STA_DISCONNECTED) (relire : « {S_RECONNECT} »)")
        back = again[0][0]
        got = _levels_in(marks, a + SAFE_MS, back)
        need(got == {0}, f"{label} : la pompe est encore allumée après la perte de la liaison à {_s(a)} (au plus {_s(SAFE_MS)} accordées) ou se "
             f"rallume avant son retour : sans liaison plus personne ne surveille la pompe, on l'éteint et on la laisse éteinte (relire : « {S_SAFE} »)")
        nxt = (H_IN if name == "h" else I_IN)[0][0]  # la commande suivante : jusque-là la pompe doit tourner
        got = _levels_in(marks, back + REACT_MS + 1_000, nxt)
        need(got == {1}, f"{label} : la liaison est revenue à {_s(back)} et la pompe ne repart pas (niveau sous 60 %) : la régulation reprend "
             f"d'elle-même quand la liaison revient (relire : « {S_SAFE} »)")


def _check_h(trace: Trace) -> None:
    label = LABELS["h"]
    _check_outage(trace, "h")
    segs = es6._segments(trace, 56, MAX_MS["h"])
    for seg in segs:
        if seg[4]:
            start, dur = es6._time_beyond(seg, 70 + es6.TOL, above=True)
            need(dur <= es6.REACT_MS, f"{label} : la pompe est restée allumée {_s(dur)} avec un niveau de plus de {70 + es6.TOL:.0f} % alors que la "
                 f"consigne reçue à 300 s est de 70 % : la commande n'a pas été prise en compte, le programme s'est-il réabonné après la coupure ? "
                 f"(relire : « {S_RECONNECT} »)")
    need(_changes(trace)[-1][1] == 0, f"{label} : la pompe est encore allumée à la fin alors que le niveau a dépassé la consigne de 70 % (relire : « {S_SETPOINT} »)")


def _check_i(trace: Trace) -> None:
    label = LABELS["i"]
    _check_outage(trace, "i")
    got = _levels_in(_marks(trace), 150_000 + REACT_MS, MAX_MS["i"])
    need(got == {0}, f"{label} : la commande {{\"high\": 40}} de {_s(150_000)} n'éteint pas la pompe (niveau 50 %) : le programme s'est-il réabonné "
         f"après le retour du Wi-Fi ? (relire : « {S_RECONNECT} »)")


# ---- j : certificat expiré ----

def _check_j(trace: Trace) -> None:
    label = LABELS["j"]
    hs = trace.events("tls_handshake")
    connected = trace.events("mqtt", event="connected")
    need(not connected, f"{label} : le client s'est connecté à {_s(connected[0]['t_ms'] if connected else 0)} alors que le certificat du courtier est "
         f"expiré : la vérification doit refuser cette connexion (relire : « {S_NEVER} »)")
    other = [e for e in hs if e["verify"] != "failed:expired"]
    need(not other, f"{label} : la poignée de main de {_s(other[0]['t_ms'] if other else 0)} échoue pour une autre raison "
         f"({other[0]['verify'] if other else ''}) que le certificat expiré : {es10._why_not_connected(trace)}")
    need(len(hs) >= MIN_ATTEMPTS, f"{label} : seulement {len(hs)} tentative(s) de connexion en {_s(MAX_MS['j'])} : après un échec le client "
         f"réessaie, il n'abandonne jamais (relire : « {S_ERR} »)")
    ons = [t for t, lv in _changes(trace) if lv == 1]
    need(not ons, f"{label} : la pompe s'allume à {_s(ons[0] if ons else 0)} alors que la liaison n'a jamais été établie : sans liaison sûre la pompe "
         f"reste éteinte (relire : « {S_SAFE} »)")
    need(not trace.events("mqtt_publish"), f"{label} : un message est publié alors que le client n'a jamais été connecté (relire : « {S_NEVER} »)")
    errors = [e for e in trace.events("mqtt", event="error") if e.get("esp_tls_last_esp_err")]
    need(errors, f"{label} : aucune erreur TLS signalée par le client : MQTT_EVENT_ERROR doit porter les codes d'esp-tls (relire : « {S_ERR} »)")
    code = errors[0]["esp_tls_last_esp_err"]
    forms = {f"{code:x}", str(code)}
    warned = [e for e in trace.logs(tag="tls") if e["level"] in ("W", "E") and any(f in e["msg"].lower() for f in forms)]
    need(warned, f"{label} : l'échec de la poignée de main n'est pas journalisé avec son code : écrivez un ESP_LOGW de tag « tls » dans la réaction à "
         f"MQTT_EVENT_ERROR, avec esp_tls_last_esp_err (en hexadécimal, %x, ou en décimal) (relire : « {S_ERR} »)")


def verify_runs(traces: dict) -> None:
    """Les dix exécutions, sans l'analyse du texte (la phase 3 la complète)."""
    for name in "abcdef":
        _net_ok(traces[name], name)
    p1.verify_regulation(traces)
    p1.verify_sensor(traces)
    for name in ("g", "h", "i"):
        _net_ok(traces[name], name)
    _check_g(traces["g"])
    _check_h(traces["h"])
    _check_i(traces["i"])
    _check_j(traces["j"])


def verify(traces: dict, source: str) -> None:
    es10._check_source(source)
    verify_runs(traces)
