"""TP es9 : robustesse. Consigne de niveau haut réglable par MQTT, enregistrée en NVS et relue après un redémarrage, réabonnement
après une coupure du courtier, watchdog de tâche alimenté, publication sans ESP_ERROR_CHECK.

Le programme pilote le relais GPIO 5 : allumé quand le niveau lu sur l'ADC (étalonnage d'es4 : brut 620 = 0 %, 3723 = 100 %) est
STRICTEMENT sous la consigne `haut` (60 % par défaut, bornée à 10..80 %, limite de sécurité d'es6). Il reçoit {"high": N} sur
home/devices/pool-ctl/command, publie toutes les 10 s sur .../telemetry {"level": 72.5, "relay": false, "high": 75}.
Le niveau est constant dans chaque exécution (remplissage et évaporation nuls) : le relais n'obéit donc qu'à la consigne.

Trois exécutions (SCENARIOS) :
  a : niveau 72,5 %. {"high": 55} à 30 s ; courtier coupé de 50 s à 110 s (60 s) ; {"high": 75} à 115 s (reçue seulement si le
      programme s'est réabonné à la reconnexion, vers 110,6 s) ; redémarrage (coupure de courant) à 120 s ; {"high": 65} à 150 s
      (reçue seulement si le programme s'est réabonné après le redémarrage). Après le redémarrage la consigne est relue de la NVS :
      75, pas la valeur par défaut 60 : le relais doit se rallumer.
  b : niveau 50 %. Valeur par défaut 60 : relais allumé ; {"high": 40} à 30 s : relais éteint ; redémarrage à 60 s : la consigne 40
      est relue AVANT de piloter le relais, qui ne s'allume donc jamais (ni brièvement) après le redémarrage.
  c : niveau 85,3 %. « salut » (10 s) : ignoré ; {"high": 95} (20 s) et {"high": 5} (40 s) : refusées et journalisées ;
      {"high": "abc"} (50 s) : ignorée ; {"high": 80} (55 s) et {"high": 10} (62 s) : bornes acceptées. Aucun redémarrage.

Le contrôle juge la trace, et lit aussi le texte du programme pour une seule chose : la présence des appels esp_task_wdt_add et
esp_task_wdt_reset (le simulateur ne trace pas l'abonnement au watchdog, et aucun scénario ne bloque le programme).
Tolérances : relais commuté au plus 2 s après une commande, au plus 5 s après un démarrage ; télémétrie de 8 s à 12 s entre deux
messages d'une même connexion ; abonnement dans les 5 s qui suivent chaque connexion ; nvs_commit dans les 2 s de chaque écriture.
"""
import json
import re

from esp_trace import Trace, need

PIN = 5
CHANNEL = 6
BASE = "home/devices/pool-ctl"
T_TELE, T_CMD = f"{BASE}/telemetry", f"{BASE}/command"
TAG = "robust"
DEFAULT_HIGH = 60
LEVELS = {"a": 72.5, "b": 50.0, "c": 85.3}
LEVEL_TOL = 1.0
MAX_MS = {"a": 180_000, "b": 100_000, "c": 80_000}
REACT_MS, BOOT_MS, SETUP_MS, COMMIT_MS, TELE_MS = 2_000, 5_000, 5_000, 2_000, 1_000
TELE_MIN_MS, TELE_MAX_MS = 8_000, 12_000
OUTPUT_MODES = {"output", "input_output"}
REFUSED_VALUES = {95, 5}

INCOMING = {
    "a": [(30_000, '{"high": 55}'), (115_000, '{"high":75}'), (150_000, '{"high": 65}')],
    "b": [(30_000, '{"high": 40}')],
    "c": [(10_000, "salut"), (20_000, '{"high": 95}'), (40_000, '{"high": 5}'), (50_000, '{"high": "abc"}'),
          (55_000, '{"high": 80}'), (62_000, '{"high": 10}')],
}
REBOOTS = {"a": [120_000], "b": [60_000], "c": []}
DOWN = {"a": (50_000, 110_000)}
# (t_ms, consigne en vigueur à partir de t) : la valeur par défaut au départ, puis chaque commande acceptée.
HIGH_AT = {"a": [(0, 60), (30_000, 55), (115_000, 75), (150_000, 65)], "b": [(0, 60), (30_000, 40)],
           "c": [(0, 60), (55_000, 80), (62_000, 10)]}
# Refus attendus : (t_ms de la commande, fin du message « setpoint refused: ... »).
REFUSALS = {"c": [(20_000, "high=95"), (40_000, "high=5")]}


def _scenario(name: str) -> dict:
    mqtt = {"incoming": [{"t_ms": t, "topic": T_CMD, "payload": p} for t, p in INCOMING[name]]}
    if name in DOWN:
        mqtt["broker_down"] = [{"from_ms": DOWN[name][0], "to_ms": DOWN[name][1]}]
    tank = {"level_pct0": LEVELS[name], "fill_pct_per_min": 0, "loss_pct_per_min": 0, "relay_pin": PIN,
            "adc_channel": CHANNEL, "raw_at_0": 620, "raw_at_100": 3723}
    sc = {"plant": {"tank": tank}, "mqtt": mqtt}
    if REBOOTS[name]:
        sc["reboots_at_ms"] = REBOOTS[name]
    return sc


SCENARIOS = {name: (_scenario(name), MAX_MS[name]) for name in ("a", "b", "c")}
LABELS = {"a": "scénario a (niveau 72,5 %, coupure du courtier de 60 s, redémarrage à 120 s)",
          "b": "scénario b (niveau 50 %, redémarrage à 60 s)",
          "c": "scénario c (niveau 85 %, consignes refusées ou ignorées)"}

S_RECONNECT = "Reprendre après une coupure du courtier"
S_SETPOINT = "La consigne : un JSON de commande, des bornes de sécurité"
S_NVS = "Sauvegarder en NVS : ouvrir, écrire, valider"
S_BOOT = "Restaurer au démarrage, avant d'allumer le relais"
S_WDT = "Le watchdog de tâche : surveiller la boucle"
S_ERR = "Gérer l'erreur au lieu d'abandonner : ESP_ERROR_CHECK"


def _s(ms: float) -> str:
    return f"{ms / 1000:g}".replace(".", ",") + " s"


def _pct(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _match(flt: str, topic: str) -> bool:
    f, t = flt.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(f) == len(t)


def _code(source: str) -> str:
    """Le texte du programme sans commentaires (les chaînes restent : on n'y cherche que des noms de fonctions)."""
    return re.sub(r"//[^\n]*|/\*.*?\*/", " ", source, flags=re.S)


def _relay_changes(trace: Trace) -> list[tuple[int, int]]:
    """Changements du relais ; un redémarrage remet la broche à 0 (la puce se réinitialise)."""
    marks = [(t, lv, 1) for t, lv in trace.gpio_levels(PIN)] + [(e["t_ms"], 0, 0) for e in trace.events("reboot")]
    out, level = [], 0
    for t, lv, _ in sorted(marks, key=lambda m: (m[0], m[2])):
        if lv != level:
            out.append((t, lv))
            level = lv
    return out


def _relay_marks(trace: Trace) -> list[tuple[int, int]]:
    """Toutes les écritures sur la broche, dans l'ordre, sans fusionner les répétitions ni les changements d'une même milliseconde
    (une impulsion à l'instant du démarrage compte) ; un redémarrage remet la broche à 0 avant l'écriture qui suit."""
    marks = [(t, 1, lv) for t, lv in trace.gpio_levels(PIN)] + [(e["t_ms"], 0, 0) for e in trace.events("reboot")]
    return [(t, lv) for t, _, lv in sorted(marks, key=lambda m: (m[0], m[1]))]


def _levels_in(marks: list[tuple[int, int]], a: int, b: int, fresh: bool = False) -> set[int]:
    """Niveaux pris par la broche dans [a, b[ ; `fresh` : a est un redémarrage, l'état d'avant est sans objet."""
    cur = 0
    for t, lv in marks:
        if t < a:
            cur = lv
    out = set() if fresh else {cur}
    out.update(lv for t, lv in marks if a <= t < b)
    return out


def _relay_states(changes: list[tuple[int, int]], t: int) -> set[int]:
    before = after = 0
    for tc, lv in changes:
        if tc < t:
            before = after = lv
        elif tc == t:
            after = lv
    return {before, after}


def _high_at(name: str, t: int) -> set[int]:
    """Consignes admissibles à l'instant t (l'ancienne et la nouvelle pendant la seconde qui suit un changement)."""
    cur = prev = DEFAULT_HIGH
    for tc, v in HIGH_AT[name]:
        if tc <= t:
            prev, cur = cur, v
            if t - tc <= TELE_MS:
                return {prev, cur}
    return {cur}


def _timeline(name: str) -> list[tuple[int, int, str]]:
    """[(t_ms, relais attendu, nature)] : chaque instant où l'état attendu du relais est susceptible de changer."""
    level = LEVELS[name]
    events = [(0, "boot")] + [(t, "cmd") for t, _ in HIGH_AT[name][1:]] + [(t, "boot") for t in REBOOTS[name]]
    out = []
    for t, kind in sorted(events):
        high = [v for tc, v in HIGH_AT[name] if tc <= t][-1]
        out.append((t, int(level < high), kind))
    return out


def _check_relay(trace: Trace, name: str) -> None:
    label = LABELS[name]
    marks = _relay_marks(trace)
    tl = _timeline(name)
    end = MAX_MS[name]
    prev_state = 0
    for i, (t, state, kind) in enumerate(tl):
        stop = tl[i + 1][0] if i + 1 < len(tl) else end
        # après un redémarrage la broche est à 0 : on part de là ; sinon de l'état attendu juste avant
        before = 0 if kind == "boot" else prev_state
        tol = (BOOT_MS if kind == "boot" else REACT_MS) if state != before else 0
        got = _levels_in(marks, t + tol, stop, fresh=kind == "boot" and tol == 0 and t > 0)
        if got != {state}:
            bad = sorted(got - {state})
            if state == 0 and kind == "boot" and t > 0:
                need(False, f"{label} : le relais est allumé après le redémarrage de {_s(t)} alors que la consigne enregistrée "
                     f"({max(v for tc, v in HIGH_AT[name] if tc <= t)} %) interdit de l'allumer à ce niveau : relisez la consigne en NVS AVANT de piloter le relais "
                     f"(et ne l'allumez pas « par défaut » au démarrage) (relire : « {S_BOOT} »)")
            if kind == "boot" and t > 0:
                need(False, f"{label} : après le redémarrage de {_s(t)}, le relais n'est pas "
                     f"{'allumé' if state else 'éteint'} comme le veut la consigne enregistrée en NVS "
                     f"({max(v for tc, v in HIGH_AT[name] if tc <= t)} %, niveau {_pct(LEVELS[name])} %) : la consigne a-t-elle été "
                     f"enregistrée (nvs_commit) puis relue au démarrage ? (relire : « {S_BOOT} »)")
            if kind == "boot":
                need(False, f"{label} : le relais n'est pas {'allumé' if state else 'éteint'} au démarrage, alors que le niveau "
                     f"{'est sous' if state else 'n’est pas sous'} la consigne par défaut de {DEFAULT_HIGH} % (relire : « {S_BOOT} »)")
            need(False, f"{label} : après la commande de {_s(t)}, le relais devrait être {'allumé' if state else 'éteint'} "
                 f"(niveau {_pct(LEVELS[name])} %, consigne {[v for tc, v in HIGH_AT[name] if tc <= t][-1]} %) dans les {_s(REACT_MS)} : "
                 f"le programme est-il abonné (à chaque connexion), compare-t-il le sujet avec topic_len, lit-il la consigne dans le JSON, "
                 f"et pilote-t-il le relais ? "
                 f"(relire : « {S_RECONNECT} »)")
        prev_state = state


def _check_telemetry(trace: Trace, name: str) -> list[tuple[int, dict]]:
    label = LABELS[name]
    pubs = trace.events("mqtt_publish", topic=T_TELE)
    need(pubs, f"{label} : aucun message sur « {T_TELE} » : le programme publie sur ce sujet, hors connexion la publication "
         f"est refusée et on continue (relire : « {S_ERR} »)")
    changes = _relay_changes(trace)
    out = []
    for e in pubs:
        t, text = e["t_ms"], e["payload"]
        try:
            obj = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        except ValueError:
            need(False, f"{label} : le message de {_s(t)} n'est pas un JSON valide : « {text} » : utilisez la fonction "
                 f"construire_json fournie (relire : « {S_SETPOINT} »)")
        need(isinstance(obj, dict) and set(obj) == {"level", "relay", "high"},
             f"{label} : le message de {_s(t)} (« {text} ») doit avoir exactement les clés level, relay et high : utilisez "
             f"construire_json (relire : « {S_SETPOINT} »)")
        level, relay, high = obj["level"], obj["relay"], obj["high"]
        need(isinstance(level, (int, float)) and not isinstance(level, bool) and abs(level - LEVELS[name]) <= LEVEL_TOL,
             f"{label} : niveau publié {level!r} à {_s(t)} alors que le niveau lu est de {_pct(LEVELS[name])} % : passez "
             f"lire_niveau() à construire_json (relire : « {S_SETPOINT} »)")
        need(isinstance(relay, bool) and int(relay) in _relay_states(changes, t),
             f"{label} : le message de {_s(t)} annonce relay={str(relay).lower()}, ce n'est pas l'état réel du relais : "
             f"passez la variable relais à construire_json (relire : « {S_SETPOINT} »)")
        ok = _high_at(name, t)
        if not (isinstance(high, int) and not isinstance(high, bool) and high in ok):
            expected = " ou ".join(str(v) for v in sorted(ok))
            if not isinstance(high, int) or not 10 <= high <= 80:
                why = (f"une valeur hors des bornes 10..80 % est publiée : une consigne refusée a-t-elle été acceptée, ou la "
                       f"valeur par défaut (60 %) a-t-elle été oubliée ? (relire : « {S_SETPOINT} »)")
            elif any(e["t_ms"] < t for e in trace.events("reboot")):
                why = (f"la consigne relue après un redémarrage doit être celle enregistrée, pas la valeur par défaut "
                       f"(relire : « {S_BOOT} »)")
            else:
                why = f"la commande a-t-elle été appliquée à la variable haut ? (relire : « {S_SETPOINT} »)"
            need(False, f"{label} : le message de {_s(t)} annonce la consigne {high!r} % alors qu'elle vaut {expected} % à cet "
                 f"instant : {why}")
        out.append((t, obj))
    return out


def _connections(trace: Trace, name: str) -> list[tuple[int, int]]:
    """[(début, fin)] de chaque période de connexion : jusqu'à la déconnexion, au redémarrage ou à la fin de l'exécution."""
    marks = sorted((e["t_ms"], e["event"] if e["ev"] == "mqtt" else "reboot")
                   for e in trace.events("mqtt") + trace.events("reboot") if e["ev"] == "reboot" or e["event"] in ("connected", "disconnected"))
    out, start = [], None
    for t, what in marks:
        if what == "connected":
            start = t
        elif start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, MAX_MS[name]))
    return out


def _check_cadence(trace: Trace, name: str, tele: list[int]) -> None:
    label = LABELS[name]
    for a, b in _connections(trace, name):
        sel = [t for t in tele if a <= t <= b]
        if b - a >= TELE_MAX_MS:
            need(sel, f"{label} : aucune télémétrie pendant la connexion de {_s(a)} à {_s(b)} : elle reprend d'elle-même après "
                 f"une coupure, sans que l'échec d'une publication arrête la boucle (relire : « {S_ERR} »)")
            need(sel[0] - a <= TELE_MAX_MS, f"{label} : première télémétrie de la connexion de {_s(a)} à {_s(sel[0])} : "
                 f"il en faut une toutes les 10 s (relire : « {S_ERR} »)")
            need(b - sel[-1] <= TELE_MAX_MS or b == MAX_MS[name] and b - sel[-1] <= TELE_MAX_MS,
                 f"{label} : plus de télémétrie après {_s(sel[-1])}, la connexion dure jusqu'à {_s(b)} (relire : « {S_ERR} »)")
        for x, y in zip(sel, sel[1:]):
            if x - a <= TELE_MS:  # messages mis en file pendant la coupure (QoS 1) : envoyés d'un coup à la reconnexion
                continue
            need(TELE_MIN_MS <= y - x <= TELE_MAX_MS, f"{label} : {_s(y - x)} entre deux télémétries ({_s(x)} puis {_s(y)}) : "
                 f"la période est de 10 s (de {_s(TELE_MIN_MS)} à {_s(TELE_MAX_MS)} acceptées) (relire : « {S_ERR} »)")


def _check_subscriptions(trace: Trace, name: str) -> None:
    label = LABELS[name]
    connected = [e["t_ms"] for e in trace.events("mqtt", event="connected")]
    need(connected, f"{label} : le client MQTT ne s'est jamais connecté (relire : « {S_RECONNECT} »)")
    bounds = connected[1:] + [MAX_MS[name] + 1]
    reboots = [e["t_ms"] for e in trace.events("reboot")]
    for tc, nxt in zip(connected, bounds):
        subs = [e for e in trace.events("mqtt_subscribe") if tc <= e["t_ms"] <= min(tc + SETUP_MS, nxt) and _match(e["topic"], T_CMD)]
        why = "après le redémarrage" if any(r < tc and (not any(r < c < tc for c in connected)) for r in reboots) and tc > 0 \
            and any(abs(tc - r) < 5_000 for r in reboots) else "après la reconnexion" if tc > connected[0] else "à la connexion"
        need(subs, f"{label} : aucun abonnement à « {T_CMD} » dans les {_s(SETUP_MS)} qui suivent la connexion de {_s(tc)} "
             f"({why}) : la session est propre, le courtier a tout oublié : il faut s'abonner dans la réaction à "
             f"MQTT_EVENT_CONNECTED, à chaque connexion (relire : « {S_RECONNECT} »)")


def _check_nvs_written(trace: Trace, name: str) -> None:
    label = LABELS[name]
    if name in ("a", "b"):
        need(trace.events("nvs_set"), f"{label} : aucune écriture en NVS : la consigne reçue doit être enregistrée (nvs_set_i32 puis "
             f"nvs_commit) pour survivre au redémarrage (relire : « {S_NVS} »)")


def _check_nvs(trace: Trace, name: str) -> None:
    label = LABELS[name]
    sets = trace.events("nvs_set")
    commits = trace.events("nvs_commit")
    for e in sets:
        need(any(c["ns"] == e["ns"] and e["t_ms"] <= c["t_ms"] <= e["t_ms"] + COMMIT_MS for c in commits),
             f"{label} : l'écriture de « {e['key']} » à {_s(e['t_ms'])} n'est pas suivie de nvs_commit : sans lui rien n'est "
             f"garanti après un redémarrage (le simulateur, plus strict que la carte, perd l'écriture) (relire : « {S_NVS} »)")
        need(e.get("value") not in REFUSED_VALUES, f"{label} : la valeur {e.get('value')} (refusée) est enregistrée en NVS à "
             f"{_s(e['t_ms'])} : on ne sauvegarde qu'une consigne acceptée (relire : « {S_SETPOINT} »)")


def _check_logs(trace: Trace, name: str) -> None:
    label = LABELS[name]
    refused = [e for e in trace.logs(tag=TAG) if "refus" in e["msg"].lower() or "refused" in e["msg"].lower()]
    want = REFUSALS.get(name, [])
    for t, text in want:
        msg = f"setpoint refused: {text}"
        hit = [e for e in refused if e["msg"] == msg and e["level"] == "W" and t <= e["t_ms"] <= t + REACT_MS]
        near = f" (message trouvé : « {refused[0]['msg']} », niveau {refused[0]['level']})" if refused else ""
        need(hit, f"{label} : la consigne reçue à {_s(t)} doit être refusée par un ESP_LOGW de tag « {TAG} » au format exact "
             f"« {msg} »{near} (relire : « {S_SETPOINT} »)")
    extra = [e for e in refused if not any(e["msg"] == f"setpoint refused: {text}" and t <= e["t_ms"] <= t + REACT_MS for t, text in want)]
    need(not extra, f"{label} : la ligne « {extra[0]['msg'] if extra else ''} » à {_s(extra[0]['t_ms'] if extra else 0)} refuse une "
         f"commande qui n'est pas hors des bornes 10..80 % (ou la refuse deux fois) : seules les consignes hors bornes sont "
         f"refusées, une ligne chacune ; un texte qui n'est pas une commande est ignoré en silence (relire : « {S_SETPOINT} »)")


def _check_common(trace: Trace, name: str) -> None:
    label = LABELS[name]
    wdt = trace.events("wdt_reset")
    need(not wdt, f"{label} : le watchdog de tâche s'est déclenché à {_s(wdt[0]['t_ms'] if wdt else 0)} : la tâche « "
         f"{wdt[0]['tasks'] if wdt else ''} » ne l'a pas alimenté à temps : appelez esp_task_wdt_reset à chaque tour de la boucle "
         f"(relire : « {S_WDT} »)")
    want = REBOOTS[name]
    got = trace.events("reboot")
    need(all(e["reason"] == "scripted" for e in got) and [e["t_ms"] for e in got] == want,
         f"{label} : redémarrage(s) inattendu(s) : " + (", ".join(f"{_s(e['t_ms'])} ({e['reason']})" for e in got) or "aucun")
         + f" au lieu de {', '.join(_s(t) for t in want) or 'aucun'} : rien dans ce TP ne doit redémarrer la carte (esp_restart, "
         f"watchdog, ESP_ERROR_CHECK qui échoue) : la coupure de courant est celle du scénario (relire : « {S_WDT} »)")
    need(any(e["channel"] == CHANNEL for e in trace.events("adc_read")),
         f"{label} : aucune lecture du canal {CHANNEL} de l'ADC1 : le niveau se lit sur le capteur (relire : « {S_BOOT} »)")
    need(any(e["pin"] == PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} du relais n'est pas configurée en sortie (relire : « {S_BOOT} »)")
    errors = [e for e in trace.logs(level="E") if e["tag"] == "task_wdt"]
    need(not errors, f"{label} : le watchdog signale une tâche qui ne l'alimente pas (relire : « {S_WDT} »)")


def _check_source(source: str) -> None:
    code = _code(source)
    need(re.search(r"\besp_task_wdt_add\s*\(", code),
         f"aucun appel à esp_task_wdt_add : la boucle principale doit s'abonner au watchdog de tâche (le contrôle lit le texte du "
         f"programme pour cela : le simulateur ne trace pas l'abonnement) (relire : « {S_WDT} »)")
    need(re.search(r"\besp_task_wdt_reset\s*\(", code),
         f"aucun appel à esp_task_wdt_reset : une tâche abonnée doit alimenter le watchdog à chaque tour de boucle "
         f"(relire : « {S_WDT} »)")


def verify(traces: dict, source: str) -> None:
    # Chaque exécution est jugée en entier avant la suivante : le premier message nomme le premier scénario en faute.
    for name in ("a", "b", "c"):
        t = traces[name]
        _check_common(t, name)
        _check_subscriptions(t, name)
        _check_logs(t, name)
        _check_nvs(t, name)
        _check_relay(t, name)
        _check_nvs_written(t, name)
        tele = _check_telemetry(t, name)
        _check_cadence(t, name, [x for x, _ in tele])
    _check_source(source)
