"""TP es8 : MQTT, la télémétrie, le statut avec testament, et les commandes bornées par la limite de sécurité d'es6.

Le programme publie sur home/devices/pool-ctl/telemetry un JSON {"level": 72.5, "relay": false} toutes les 10 s, annonce
« online » (retenu) sur .../status à chaque connexion avec un testament « offline » (retenu), s'abonne à .../command et
exécute {"relay": true} / {"relay": false} sur le relais GPIO 5, sauf si le niveau lu sur l'ADC (étalonnage d'es4 : brut
620 = 0 %, 3723 = 100 %) dépasse 80 % : la commande est alors refusée et journalisée.

Trois exécutions du même programme (SCENARIOS). Le réservoir ne change pas de niveau (remplissage et évaporation nuls) : le
niveau vrai est la constante LEVEL du scénario, ce qui rend le contrôle de la télémétrie exact.
  a : niveau 72,5 %. Commandes : {"relay": true} à 30 s (acceptée), « salut » à 50 s (pas une commande : ignorée),
      {"relay":false} à 70 s (sans espace : le JSON laisse les espaces libres). Télémétrie toutes les 10 s.
  b : niveau 85,3 % (85 % en entier, tronqué ou arrondi). {"relay": true} à 30 s : refusée, ESP_LOGW de tag « mqtt »,
      message exact « command refused: level=85% », relais jamais allumé.
  c : niveau 72,5 %. {"relay": true} à 25 s ; courtier coupé de 50 s à 75 s (le simulateur reconnecte tout seul, vers
      80 s) ; {"relay": false} à 95 s, reçue seulement si le programme s'est réabonné après la reconnexion.

Tolérances, annoncées dans l'énoncé :
  - période de télémétrie : 10 s, de 9 s à 11 s entre deux messages (exécution a, et avant la coupure de c) ; après la
    reconnexion de c, au plus 11 s entre deux messages (un message mis en file d'attente pendant la coupure peut partir
    d'un coup à la reconnexion) ;
  - niveau publié : à 1 point près du niveau vrai ; relais publié : l'état de la broche 5 à l'instant du message ;
  - « online » dans les 5 s qui suivent chaque connexion, abonnement dans les 5 s aussi ;
  - relais commuté au plus 1 s après la commande.
Le contrôle ne lit pas le texte du programme : tout se juge sur la trace.
"""
import json
import re

from esp_trace import fmt_pct as _pct, fmt_s as _s, need, relay_changes, relay_states as _relay_states, topic_match as _match, Trace

PIN = 5
CHANNEL = 6
RAW_0, RAW_100 = 620, 3723
BASE = "home/devices/pool-ctl"
T_TELE, T_STATUS, T_CMD = f"{BASE}/telemetry", f"{BASE}/status", f"{BASE}/command"
PERIOD_MS, PERIOD_UNDER_MS, PERIOD_OVER_MS = 10_000, 1_000, 1_000
SETUP_MS = 5_000
REACT_MS = 1_000
LEVEL_TOL = 1.0
LEVELS = {"a": 72.5, "b": 85.3, "c": 72.5}
LIMIT = 80
REFUSED = "command refused: level=85%"
TAG = "mqtt"
OUTPUT_MODES = {"output", "input_output"}

CMD_ON, CMD_OFF = '{"relay": true}', '{"relay":false}'
# nom -> (instants t_ms de l'arrivée des commandes, charge utile) ; le courtier de c est coupé de 50 s à 75 s.
INCOMING = {
    "a": [(30_000, CMD_ON), (50_000, "salut"), (70_000, CMD_OFF)],
    "b": [(30_000, CMD_ON)],
    "c": [(25_000, CMD_ON), (95_000, CMD_OFF)],
}
DOWN = (50_000, 75_000)
MAX_MS = {"a": 120_000, "b": 60_000, "c": 140_000}


def _scenario(name: str) -> dict:
    mqtt = {"incoming": [{"t_ms": t, "topic": T_CMD, "payload": p} for t, p in INCOMING[name]]}
    if name == "c":
        mqtt["broker_down"] = [{"from_ms": DOWN[0], "to_ms": DOWN[1]}]
    tank = {"level_pct0": LEVELS[name], "fill_pct_per_min": 0, "loss_pct_per_min": 0, "relay_pin": PIN,
            "adc_channel": CHANNEL, "raw_at_0": RAW_0, "raw_at_100": RAW_100}
    return {"plant": {"tank": tank}, "mqtt": mqtt}


SCENARIOS = {name: (_scenario(name), MAX_MS[name]) for name in ("a", "b", "c")}
LABELS = {"a": "scénario a (niveau 72,5 %, commandes acceptées)", "b": "scénario b (niveau 85 %, commande refusée)",
          "c": "scénario c (coupure du courtier de 50 s à 75 s)"}

S_CLIENT = "Le client ESP-IDF : configuration et démarrage"
S_EVENTS = "Les événements MQTT : qui les appelle, dans quelle tâche"
S_PUBLISH = "Publier : la fonction, le QoS et le drapeau retain"
S_SUBSCRIBE = "S'abonner, et se réabonner après une coupure"
S_STATUS = "Le statut et le testament"
S_JSON = "Construire un JSON valide sans bibliothèque"
S_DATA = "Recevoir une commande : topic et data ne sont pas des chaînes C"
S_SAFE = "Exécuter la commande sans dépasser la limite de sécurité"
S_TELE = "La télémétrie toutes les 10 secondes"


def _telemetry(trace: Trace, name: str) -> list[tuple[int, dict]]:
    """[(t_ms, objet JSON)] des messages du topic de télémétrie, validés un à un."""
    label = LABELS[name]
    pubs = trace.events("mqtt_publish", topic=T_TELE)
    others = sorted({e["topic"] for e in trace.events("mqtt_publish") if e["topic"] not in (T_TELE, T_STATUS)})
    need(pubs, f"{label} : aucun message sur le topic « {T_TELE} » : la télémétrie est publiée avec esp_mqtt_client_publish "
         f"sur exactement ce topic" + (f" (topic trouvé : « {others[0]} »)" if others else "")
         + f" (relire : « {S_TELE} »)")
    changes = relay_changes(trace)
    out = []
    for e in pubs:
        t, text = e["t_ms"], e["payload"]
        try:
            obj = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        except ValueError:
            need(False, f"{label} : le message de télémétrie de {_s(t)} n'est pas un JSON valide : « {text} ». Les clés "
                 f"s'écrivent entre guillemets doubles, les valeurs true et false sans guillemets, et le niveau est un "
                 f"nombre fini (relire : « {S_JSON} »)")
        need(isinstance(obj, dict) and set(obj) == {"level", "relay"},
             f"{label} : le message de {_s(t)} (« {text} ») doit être un objet JSON avec exactement les clés « level » et "
             f"« relay » (relire : « {S_JSON} »)")
        level, relay = obj["level"], obj["relay"]
        need(isinstance(level, (int, float)) and not isinstance(level, bool),
             f"{label} : « level » doit être un nombre, pas {text!r} (relire : « {S_JSON} »)")
        need(isinstance(relay, bool), f"{label} : « relay » doit être true ou false sans guillemets : « {text} » "
             f"(relire : « {S_JSON} »)")
        need(abs(level - LEVELS[name]) <= LEVEL_TOL,
             f"{label} : niveau publié {_pct(level)} % à {_s(t)} alors que le niveau lu sur l'ADC est de {_pct(LEVELS[name])} % "
             f"(à {_pct(LEVEL_TOL)} point près) : lisez le capteur à chaque message, avec l'étalonnage du TP 4 "
             f"(relire : « {S_JSON} »)")
        states = _relay_states(changes, t)
        need(int(relay) in states, f"{label} : le message de {_s(t)} annonce relay={str(relay).lower()} alors que le relais est "
             f"{'allumé' if 1 in states else 'éteint'} : publiez l'état réel du relais (relire : « {S_JSON} »)")
        out.append((t, obj))
    return out


def _cadence(label: str, times: list[int], start: int, end: int, exact: bool, what: str) -> None:
    """Un message au plus PERIOD+OVER après `start`, jamais plus de PERIOD+OVER entre deux, et (exact) pas moins de
    PERIOD-UNDER ; le dernier au plus PERIOD+OVER avant `end`."""
    hi, lo = PERIOD_MS + PERIOD_OVER_MS, PERIOD_MS - PERIOD_UNDER_MS
    what = f" {what}" if what else ""
    sel =[t for t in times if start <= t <= end]
    need(sel, f"{label} : aucun message de télémétrie{what} (relire : « {S_TELE} »)")
    need(sel[0] - start <= hi, f"{label} : premier message de télémétrie{what} à {_s(sel[0])}, {_s(sel[0] - start)} après "
         f"{_s(start)} : il en faut un toutes les 10 s (relire : « {S_TELE} »)")
    for a, b in zip(sel, sel[1:]):
        need(b - a <= hi, f"{label} : {_s(b - a)} entre deux messages de télémétrie ({_s(a)} puis {_s(b)}){what} : "
             f"il en faut un toutes les 10 s (relire : « {S_TELE} »)")
        need(not exact or b - a >= lo, f"{label} : seulement {_s(b - a)} entre deux messages de télémétrie ({_s(a)} puis "
             f"{_s(b)}) : la période est de 10 s (de {_s(lo)} à {_s(hi)} acceptées) (relire : « {S_TELE} »)")
    need(end - sel[-1] <= hi, f"{label} : plus aucun message de télémétrie{what} après {_s(sel[-1])} (relire : « {S_TELE} »)")


def _common(trace: Trace, name: str) -> list[int]:
    """Vérifications valables pour chaque exécution. Renvoie les instants des connexions."""
    label = LABELS[name]
    reboots = trace.events("reboot")
    need(not reboots, f"{label} : la carte a redémarré à {_s(reboots[0]['t_ms'] if reboots else 0)} : rien dans ce TP ne doit "
         f"redémarrer la carte (relire : « {S_CLIENT} »)")
    ev = trace.events("mqtt")
    need(ev, f"{label} : aucun événement MQTT : le client n'a jamais démarré. Il faut esp_mqtt_client_init, "
         f"esp_mqtt_client_register_event puis esp_mqtt_client_start (relire : « {S_CLIENT} »)")
    need(any(e["event"] == "before_connect" for e in ev),
         f"{label} : esp_mqtt_client_start n'a jamais lancé de connexion (relire : « {S_CLIENT} »)")
    connected = [e for e in ev if e["event"] == "connected"]
    errors = [e for e in ev if e["event"] == "error"]
    need(connected, f"{label} : le client n'a jamais pu se connecter au courtier ({len(errors)} erreur(s) de connexion) : "
         f"l'adresse du courtier est-elle donnée à broker.address.uri, et le Wi-Fi est-il connecté avant le démarrage du "
         f"client ? (relire : « {S_CLIENT} »)")
    need(any(e["channel"] == CHANNEL for e in trace.events("adc_read")),
         f"{label} : aucune lecture du canal {CHANNEL} de l'ADC1 : le niveau se lit sur le capteur (relire : « {S_JSON} »)")
    need(any(e["pin"] == PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} du relais n'est pas configurée en sortie (relire : « {S_SAFE} »)")
    times = [e["t_ms"] for e in connected]
    bounds = times[1:] + [MAX_MS[name] + 1]
    for e in connected:
        lt, lm = e.get("lwt_topic"), e.get("lwt_msg")
        need(lt is not None, f"{label} : la connexion de {_s(e['t_ms'])} n'a aucun testament : renseignez "
             f"session.last_will.topic, msg, qos et retain avant esp_mqtt_client_init (relire : « {S_STATUS} »)")
        need(lt == T_STATUS, f"{label} : le testament est publié sur « {lt} » au lieu de « {T_STATUS} » (relire : « {S_STATUS} »)")
        need(lm == "offline", f"{label} : le message du testament est « {lm} » au lieu de « offline » (relire : « {S_STATUS} »)")
        need(e.get("lwt_retain") is True, f"{label} : le testament n'est pas retenu (session.last_will.retain = true) : un "
             f"abonné qui arrive après la panne verrait encore « online » (relire : « {S_STATUS} »)")
    status = trace.events("mqtt_publish", topic=T_STATUS)
    need(all(e["retain"] for e in status if e["payload"] == "online"),
         f"{label} : un message « online » est publié sans le drapeau retain : le statut doit être retenu, sinon un abonné "
         f"qui arrive plus tard ne le voit jamais (relire : « {S_STATUS} »)")
    for tc, nxt in zip(times, bounds):
        mine = [e for e in status if tc <= e["t_ms"] <= min(tc + SETUP_MS, nxt)]
        need(mine, f"{label} : aucun statut publié sur « {T_STATUS} » dans les {_s(SETUP_MS)} qui suivent la connexion de "
             f"{_s(tc)} : il se publie dans la réaction à MQTT_EVENT_CONNECTED, à chaque connexion, reconnexions "
             f"comprises (relire : « {S_STATUS} »)")
        need(any(e["payload"] == "online" for e in mine),
             f"{label} : le statut publié à la connexion de {_s(tc)} est « {mine[0]['payload']} » au lieu de « online » "
             f"(relire : « {S_STATUS} »)")
        subs = [e for e in trace.events("mqtt_subscribe") if tc <= e["t_ms"] <= min(tc + SETUP_MS, nxt) and _match(e["topic"], T_CMD)]
        need(subs, f"{label} : aucun abonnement à « {T_CMD} » dans les {_s(SETUP_MS)} qui suivent la connexion de {_s(tc)} : la session est propre, le "
             f"courtier oublie les abonnements à chaque connexion, il faut s'abonner dans la réaction à "
             f"MQTT_EVENT_CONNECTED (relire : « {S_SUBSCRIBE} »)")
    return times


def _expect_relay(trace: Trace, name: str, expected: list[tuple[int, int]]) -> None:
    """Les changements du relais sont exactement `expected` : [(instant de la commande, niveau)], à REACT_MS près."""
    label = LABELS[name]
    changes = relay_changes(trace)
    ask = f"le programme s'est-il abonné, lit-il topic_len et data_len, et comprend-il le JSON avec ou sans espace ? (relire : « {S_DATA} »)"
    i = 0  # prochaine commande attendue
    for tc, lv in changes:
        if i < len(expected) and lv == expected[i][1] and tc >= expected[i][0]:
            t0 = expected[i][0]
            need(tc <= t0 + REACT_MS, f"{label} : la commande reçue à {_s(t0)} n'a changé le relais qu'à {_s(tc)} : il faut "
                 f"agir dans la seconde, sans bloquer le gestionnaire MQTT (relire : « {S_DATA} »)")
            i += 1
        else:
            need(False, f"{label} : le relais passe à {lv} à {_s(tc)} sans commande valide à cet instant : un message qui n'est "
                 f"pas une commande est ignoré, le relais ne change que sur {{\"relay\": true}} ou {{\"relay\": false}} "
                 f"(relire : « {S_DATA} »)")
    need(i == len(expected), f"{label} : la commande reçue à {_s(expected[min(i, len(expected) - 1)][0])} devait "
         f"{'allumer' if expected[min(i, len(expected) - 1)][1] else 'éteindre'} le relais (broche {PIN}) dans la seconde : {ask}")


def _check_a(trace: Trace) -> None:
    label = LABELS["a"]
    times = [t for t, _ in _telemetry(trace, "a")]
    first = trace.events("mqtt", event="connected")[0]["t_ms"]
    _cadence(label, times, first, MAX_MS["a"], True, "")
    _expect_relay(trace, "a", [(30_000, 1), (70_000, 0)])
    need(not any("command refused" in e["msg"] for e in trace.logs(tag=TAG)),
         f"{label} : une commande est journalisée comme refusée alors que le niveau est de 72,5 %, sous la limite de "
         f"{LIMIT} % (relire : « {S_SAFE} »)")


def _check_b(trace: Trace) -> None:
    label = LABELS["b"]
    _telemetry(trace, "b")
    on = [t for t, lv in relay_changes(trace) if lv == 1]
    need(not on, f"{label} : le relais est allumé à {_s(on[0] if on else 0)} alors que le niveau est de 85 %, au-dessus de "
         f"la limite de sécurité de {LIMIT} % : la commande {{\"relay\": true}} doit être refusée, le niveau se lit au moment "
         f"de la commande (relire : « {S_SAFE} »)")
    logs = [e for e in trace.logs(tag=TAG) if "refus" in e["msg"].lower() or "refused" in e["msg"].lower()]
    exact = [e for e in logs if e["msg"] == REFUSED and e["level"] == "W"]
    near = f" (message trouvé : « {logs[0]['msg']} », niveau {logs[0]['level']})" if logs else ""
    need(exact, f"{label} : le refus n'est pas journalisé comme demandé : il faut un ESP_LOGW de tag « {TAG} » au format "
         f"exact « {REFUSED} »{near} (relire : « {S_SAFE} »)")
    need(len(exact) == 1, f"{label} : {len(exact)} lignes de refus pour une seule commande refusée (relire : « {S_SAFE} »)")
    need(30_000 <= exact[0]["t_ms"] <= 30_000 + REACT_MS, f"{label} : refus journalisé à {_s(exact[0]['t_ms'])}, la commande est "
         f"arrivée à 30 s (relire : « {S_SAFE} »)")


def _check_c(trace: Trace, times: list[int]) -> None:
    label = LABELS["c"]
    need(len(times) >= 2, f"{label} : une seule connexion : après la coupure du courtier (50 s à 75 s) le client doit se "
         f"reconnecter tout seul, sans que le programme appelle esp_mqtt_client_stop ni désactive la reconnexion "
         f"automatique (relire : « {S_CLIENT} »)")
    tele = [t for t, _ in _telemetry(trace, "c")]
    _cadence(label, tele, times[0], DOWN[0], True, "avant la coupure")
    _cadence(label, tele, times[-1], MAX_MS["c"], False, "après la reconnexion")
    _expect_relay(trace, "c", [(25_000, 1), (95_000, 0)])


def verify(traces: dict, source: str) -> None:
    # Chaque exécution est jugée en entier avant la suivante : le premier message nomme le premier scénario en faute.
    _common(traces["a"], "a")
    _check_a(traces["a"])
    _common(traces["b"], "b")
    _check_b(traces["b"])
    _check_c(traces["c"], _common(traces["c"], "c"))
