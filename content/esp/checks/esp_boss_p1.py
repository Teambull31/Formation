"""Boss final, phase 1 : la régulation et la sécurité de la pompe (leçon es6), avec un capteur qui ment.

Le programme est celui du TP es6 : pompe sur le relais GPIO 5 (actif haut), niveau lu sur l'ADC1 canal 6 (étalonnage du TP 4 : brut 620 = 0 %,
3723 = 100 %), démarrage sous 60 %, arrêt au-dessus de 80 %, alarme verrouillée (ESP_LOGE, tag « pool », une seule ligne) après 10 minutes de
pompe sans hausse du niveau ou 10 minutes de valeur brute identique. Le contrôle reprend les quatre exécutions du TP es6 (a à d, mêmes tolérances,
même jugement : on importe sa vérification) et ajoute deux capteurs « qui mentent » que le TP ne testait pas :
  e : fil du capteur coupé : valeur brute 0 depuis le démarrage (le niveau lu serait « 0 % » : une pompe qui obéit remplirait le bassin sans fin).
      La pompe ne s'allume JAMAIS ; une seule alarme, dans les 12 s qui suivent la première lecture.
  f : le capteur est sain (valeur brute 2000, soit 44 %, la pompe démarre) puis passe en court-circuit vers l'alimentation à 30 s (valeur brute
      4095). Une seule alarme, entre 30 s et 42 s ; la pompe est éteinte au plus tard 1 s après la ligne d'alarme.
Une valeur brute est vraisemblable dans [300, 3900] ; en dehors, le capteur est en panne : alarme, pompe coupée, verrouillée.

Le simulateur offre aussi, à chaque exécution, un réseau que la phase 1 n'utilise pas : un courtier MQTT sur TLS valide (broker.local, certificat
"@generate") et les identifiants en NVS (espace « mqtt », clés « user » et « pass »). Un programme de la phase 1 les ignore ; les phases 2 et 3 s'en servent,
et leur programme (qui ne fait tourner la pompe que liaison établie) doit passer ces six exécutions aussi : chaque phase est jugée sur le programme final,
les contrôles sont cumulatifs (verify_regulation et verify_sensor sont appelés par les phases suivantes).
"""
from esp_trace import Trace, need, load_check, relay_changes

es6 = load_check("es6-tp")
es10 = load_check("es10-tp")

PIN, CHANNEL = es6.PIN, es6.CHANNEL
TAG = es6.TAG
RAW_MIN_OK, RAW_MAX_OK = 300, 3900
FIRST_ALARM_MS = 12_000  # e : l'alarme au plus 12 s après la première lecture
SHORT_AT_MS, SHORT_ALARM_MAX_MS = 30_000, 42_000
OFF_AFTER_ALARM_MS = 1_000
MAX_OUT = es6.MAX_OUT
MAX_E, MAX_F = 120_500, 120_500


BASE = "home/devices/pool-ctl"
T_TELE, T_CMD = f"{BASE}/telemetry", f"{BASE}/command"
USER, PASS = es10.USER, es10.PASS  # NVS d'essai : jamais montrés à l'apprenant


def _tank(level0: float, fill: float = 0.0, loss: float = 0.0) -> dict:
    return {"plant": {"tank": {"level_pct0": level0, "fill_pct_per_min": fill, "loss_pct_per_min": loss, "relay_pin": PIN,
                               "adc_channel": CHANNEL, "raw_at_0": es6.RAW_0, "raw_at_100": es6.RAW_100}}}


def net(base: dict, incoming=(), broker_down=(), reboots=(), wifi_down=(), cert_valid: bool = True) -> dict:
    """Le scénario `base` (capteur, réservoir) avec le réseau : courtier TLS, identifiants en NVS, commandes, pannes."""
    mqtt: dict = {"incoming": [{"t_ms": t, "topic": T_CMD, "payload": p} for t, p in incoming]}
    if broker_down:
        mqtt["broker_down"] = [{"from_ms": a, "to_ms": b} for a, b in broker_down]
    tls: dict = {"server_cert": "@generate"}
    if not cert_valid:
        tls["server_cert_valid"] = False
    sc = {**base, "mqtt": mqtt, "tls": tls, "nvs": {"mqtt": {"user": USER, "pass": PASS}}}
    if reboots:
        sc["reboots_at_ms"] = list(reboots)
    if wifi_down:
        sc["wifi"] = {"down": [{"from_ms": a, "to_ms": b} for a, b in wifi_down]}
    return sc


def _adc(points: list[tuple[int, int]]) -> dict:
    return {"adc": [{"t_ms": t, "channel": CHANNEL, "raw": raw} for t, raw in points]}


SCENARIOS = {name: (net(sc), ms) for name, (sc, ms) in {
    **es6.SCENARIOS,
    "e": (_adc([(0, 0)]), MAX_E),
    "f": (_adc([(0, 2000), (SHORT_AT_MS, 2000), (SHORT_AT_MS + 1, 4095)]), MAX_F),
}.items()}
LABELS = {**es6.LABELS, "e": "scénario e (fil du capteur coupé : valeur brute 0)",
          "f": "scénario f (capteur en court-circuit vers l'alimentation à 30 s : valeur brute 4095)"}
S_SAFE, S_STATE, S_FROZEN, S_HYST = es6.S_SAFE, es6.S_STATE, es6.S_FROZEN, es6.S_HYST


def _dur(ms: float) -> str:
    return es6._dur(ms)


def _bounds(trace: Trace, name: str) -> int:
    """Pompe configurée en sortie et éteinte avant la première lecture. Renvoie l'instant de la première lecture."""
    label = LABELS[name]
    reads = [e for e in trace.events("adc_read") if e["channel"] == CHANNEL]
    need(reads, f"{label} : aucune lecture du canal {CHANNEL} de l'ADC1 (relire : « {S_SAFE} »)")
    need(any(e["pin"] == PIN and e["mode"] in es6.OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} de la pompe n'est pas configurée en sortie (relire : « {S_SAFE} »)")
    first = min(e["t_ms"] for e in reads)
    sets = trace.gpio_levels(PIN)
    need(sets and sets[0][1] == 0 and sets[0][0] <= first,
         f"{label} : la pompe n'est pas mise à l'état sûr (niveau 0) avant la première lecture du capteur (relire : « {S_SAFE} »)")
    return first


def _one_alarm(trace: Trace, name: str, lo: int, hi: int, what: str) -> int:
    label = LABELS[name]
    alarms = trace.logs(tag=TAG, level="E")
    need(alarms, f"{label} : aucune alarme : {what} ; il faut un ESP_LOGE de tag « {TAG} » (relire : « {S_FROZEN} »)")
    need(len(alarms) == 1, f"{label} : {len(alarms)} lignes d'alarme (ESP_LOGE, tag « {TAG} ») au lieu d'une : l'alarme est un état, on "
         f"l'annonce une seule fois en y entrant (relire : « {S_STATE} »)")
    t = alarms[0]["t_ms"]
    need(lo <= t <= hi, f"{label} : alarme à {_dur(t)}, attendue entre {_dur(lo)} et {_dur(hi)} (relire : « {S_FROZEN} »)")
    return t


def _check_wire(trace: Trace) -> None:
    label = LABELS["e"]
    first = _bounds(trace, "e")
    ons = [t for t, lv in relay_changes(trace) if lv == 1]
    need(not ons, f"{label} : la pompe s'allume à {_dur(ons[0] if ons else 0)} alors que la valeur brute lue est 0 (fil coupé) : 0 n'est pas un "
         f"niveau de 0 %, c'est une lecture invraisemblable (hors de [{RAW_MIN_OK}, {RAW_MAX_OK}]) ; sans mesure fiable on ne remplit pas : "
         f"alarme et pompe éteinte (relire : « {S_SAFE} »)")
    _one_alarm(trace, "e", first, first + FIRST_ALARM_MS, f"la valeur brute 0 est hors de [{RAW_MIN_OK}, {RAW_MAX_OK}] (fil coupé)")


def _check_short(trace: Trace) -> None:
    label = LABELS["f"]
    first = _bounds(trace, "f")
    changes = relay_changes(trace)
    need(changes and changes[0][1] == 1 and changes[0][0] <= es6.REACT_MS,
         f"{label} : la pompe n'a pas démarré alors que le capteur est sain (valeur brute 2000, 44 %, sous 60 %) (relire : « {S_HYST} »)")
    t = _one_alarm(trace, "f", SHORT_AT_MS, SHORT_ALARM_MAX_MS,
                   f"la valeur brute 4095 est hors de [{RAW_MIN_OK}, {RAW_MAX_OK}] (capteur en court-circuit vers l'alimentation)")
    offs = [tc for tc, lv in changes if lv == 0 and tc >= SHORT_AT_MS]
    need(offs and offs[0] <= t + OFF_AFTER_ALARM_MS, f"{label} : la pompe n'est pas coupée avec l'alarme de {_dur(t)} : alarme() éteint la pompe d'abord, "
         f"puis verrouille (relire : « {S_STATE} »)")
    need(changes[-1][1] == 0, f"{label} : la pompe est encore allumée à la fin (relire : « {S_SAFE} »)")


def verify_regulation(traces: dict) -> None:
    """Les quatre exécutions du TP es6 (clés a à d) : le jugement du TP, tel quel."""
    es6.verify({k: traces[k] for k in "abcd"}, "")


def verify_sensor(traces: dict) -> None:
    """Les deux capteurs qui mentent (clés e et f)."""
    _check_wire(traces["e"])
    _check_short(traces["f"])


def verify(traces: dict, source: str) -> None:
    verify_regulation(traces)
    verify_sensor(traces)
