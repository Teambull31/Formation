"""TP es12 : retour arrière et état sûr. Le programme (client MQTT/TLS d'es10, fourni) démarre ici avec une image toute neuve, à l'état
ESP_OTA_IMG_PENDING_VERIFY. L'apprenant écrit : le relais en état sûr tout au début d'app_main, la lecture de l'état de l'image,
l'auto-test (capteur lisible, MQTT connecté en moins de 60 s) et la conclusion (esp_ota_mark_app_valid_cancel_rollback si l'auto-test
réussit, esp_ota_mark_app_invalid_rollback_and_reboot sinon, jamais les deux).

Sept exécutions (SCENARIOS), niveau constant de 72,5 % sauf en b, versions 1.10.0 (nouvelle image) et 1.9.0 (précédente) :
  a : auto-test réussi (capteur lisible, courtier joignable) : une seule confirmation (valid=true), pas de retour arrière ; {"relay": true} à 30 s.
  b : capteur muet (valeur brute 0 : fil coupé) : retour arrière demandé (valid=false), redémarrage, la version 1.9.0 reprend le service.
  c : la nouvelle image n'atteint jamais le courtier (boot.self_test_fails) : retour arrière demandé vers 60 s (de 55 s à 70 s).
  d : coupure de courant à 5 s, pendant l'auto-test (courtier absent jusqu'à 20 s) : aucune décision n'a été prise, le démarrage suivant
      revient à 1.9.0 (événement rollback, raison not_validated), sans autre marquage.
  e : courtier joignable seulement à 41 s (< 60 s) : confirmation (valid=true) dès la connexion.
  f : carte flashée par câble : le simulateur la modélise sans entrée otadata (esp_ota_get_state_partition renvoie ESP_ERR_NOT_FOUND). Selon la
      table de partitions, ESP-IDF renvoie ESP_ERR_NOT_SUPPORTED (partition factory) ou ESP_OK avec l'état VALID (sans factory) : le même test
      (appel réussi ET état PENDING_VERIFY) convient aux trois. Pas d'auto-test, aucun marquage, le service tourne.
  g : le Wi-Fi n'arrive jamais (boot.first_boot_after_ota) : l'attente de l'adresse IP est bornée et le délai de 60 s est compté depuis le
      démarrage : retour arrière demandé vers 60 s (de 55 s à 70 s), sans service (le Wi-Fi reste coupé).

Le contrôle juge la trace : ordre des événements du relais et du Wi-Fi à chaque démarrage, décisions (événements ota_mark, rollback, reboot),
instants. Il lit aussi le texte d'app_main (commentaires et chaînes retirés) : le relais doit être initialisé avant les autres initialisations.
"""
import re

from esp_trace import Trace, need

PIN = 5
CHANNEL = 6
BASE = "home/devices/pool-ctl"
T_TELE, T_CMD = f"{BASE}/telemetry", f"{BASE}/command"
LEVEL = 72.5
V_NEW, V_OLD = "1.10.0", "1.9.0"
RAW_MIN_OK, RAW_MAX_OK = 300, 3900
OUTPUT_MODES = {"output", "input_output"}
REACT_MS = 1_000
DELAY_MS = 60_000
DECIDE_MS = 10_000  # au plus 10 s entre la connexion MQTT et la confirmation
REBOOT_MS = 5_000  # au plus 5 s entre l'appel de retour arrière et le redémarrage
EARLY_MS, LATE_MS = 55_000, 70_000  # scénario c : l'échec est décidé entre 55 s et 70 s
MAX_OUT = 4_000_000

# nom -> (durée, scénario partiel, instant de la commande {"relay": true} ou None, télémétrie attendue après)
PLAN = {
    "a": dict(max_ms=100_000, relay_on=30_000, relay_off=60_000, tele_after=70_000),
    "b": dict(max_ms=100_000, relay_on=30_000, relay_off=None, tele_after=70_000),
    "c": dict(max_ms=130_000, relay_on=90_000, relay_off=None, tele_after=110_000),
    "d": dict(max_ms=100_000, relay_on=60_000, relay_off=None, tele_after=70_000),
    "e": dict(max_ms=110_000, relay_on=80_000, relay_off=None, tele_after=90_000),
    "f": dict(max_ms=60_000, relay_on=30_000, relay_off=None, tele_after=40_000),
    "g": dict(max_ms=160_000, relay_on=30_000, relay_off=None, tele_after=0),
}
LABELS = {
    "a": "scénario a (auto-test réussi)",
    "b": "scénario b (capteur muet)",
    "c": "scénario c (MQTT jamais connecté)",
    "d": "scénario d (coupure de courant pendant l'auto-test)",
    "e": "scénario e (courtier joignable à 41 s)",
    "f": "scénario f (carte flashée par câble)",
    "g": "scénario g (le Wi-Fi n'arrive jamais)",
}


def _scenario(name: str) -> dict:
    p = PLAN[name]
    incoming = [(p["relay_on"], '{"relay": true}')]
    if p["relay_off"]:
        incoming.append((p["relay_off"], '{"relay": false}'))
    mqtt: dict = {"incoming": [{"t_ms": t, "topic": T_CMD, "payload": x} for t, x in incoming]}
    sc: dict = {"mqtt": mqtt, "tls": {"server_cert": "@generate"}, "nvs": {"mqtt": {"user": "piscine-ctl-07", "pass": "Pz9-ke4N-77qL"}},
                "ota": {"images": [], "running_version": V_NEW if name != "f" else V_OLD, "previous_version": V_OLD}}
    if name == "b":
        sc["adc"] = [{"t_ms": 0, "channel": CHANNEL, "raw": 0}]
    else:
        sc["plant"] = {"tank": {"level_pct0": LEVEL, "fill_pct_per_min": 0, "loss_pct_per_min": 0, "relay_pin": PIN, "adc_channel": CHANNEL,
                                "raw_at_0": 620, "raw_at_100": 3723}}
    if name != "f":
        sc["boot"] = {"first_boot_after_ota": True, "self_test_fails": name == "c"}
    if name == "d":
        mqtt["broker_down"] = [{"from_ms": 0, "to_ms": 20_000}]
        sc["reboots_at_ms"] = [5_000]
    if name == "g":
        sc["wifi"] = {"down": [{"from_ms": 0, "to_ms": 10_000_000}]}
    if name == "e":
        mqtt["broker_down"] = [{"from_ms": 0, "to_ms": 40_000}]
    return sc


SCENARIOS = {name: (_scenario(name), PLAN[name]["max_ms"]) for name in PLAN}

S_ROLLBACK = "Le retour arrière : ce que fait le démarrage"
S_STATE = "Lire l'état de l'image au démarrage"
S_TEST = "L'auto-test : capteur et MQTT en moins de 60 s"
S_DECIDE = "Valider ou annuler : jamais les deux"
S_RELAY = "Le relais d'abord : état sûr avant toute autre initialisation"
S_POWER = "Coupure de courant en plein démarrage"


def _s(ms: float) -> str:
    return f"{ms / 1000:g}".replace(".", ",") + " s"


# ---- analyse du texte du programme ----

def _code(source: str) -> str:
    """Le texte sans commentaires ni chaînes littérales."""
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"', " ", source, flags=re.S)


def _app_main_body(code: str) -> str | None:
    m = re.search(r"\bapp_main\s*\([^)]*\)\s*\{", code)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += {"{": 1, "}": -1}.get(code[i], 0)
        i += 1
    return code[m.end():i]


RELAY_TOKENS = re.compile(r"\b(?:init_relais|gpio_set_level|gpio_config)\b")
OTHER_INITS = re.compile(r"\b(?:init_adc|init_nvs|nvs_flash_init|wifi_connecter|esp_wifi_\w+|esp_netif_init|esp_event_loop_create_default|"
                         r"demarrer_mqtt|charger_identifiants|adc_oneshot_new_unit)\b")


def _check_source(source: str) -> None:
    body = _app_main_body(_code(source))
    if body is None:
        return
    other = OTHER_INITS.search(body)
    relay = RELAY_TOKENS.search(body)
    if other and (relay is None or other.start() < relay.start()):
        need(False, f"dans app_main, « {other.group(0)} » vient avant l'initialisation du relais : le relais doit être configuré et éteint "
             f"tout au début, avant toute autre initialisation (relire : « {S_RELAY} »)")


# ---- lecture de la trace ----

def _levels_in(marks: list[tuple[int, int]], a: int, b: int) -> set[int]:
    cur = 0
    for t, lv in marks:
        if t <= a:
            cur = lv
    return {cur} | {lv for t, lv in marks if a < t < b}


def _segments(trace: Trace) -> list[list[dict]]:
    evs = trace.all()
    cuts = [i + 1 for i, e in enumerate(evs) if e["ev"] == "reboot"]
    return [evs[a:b] for a, b in zip([0, *cuts], [*cuts, len(evs)])]


def _first(seg: list[dict], pred) -> int | None:
    return next((i for i, e in enumerate(seg) if pred(e)), None)


def _relay_first(trace: Trace, label: str) -> None:
    for k, seg in enumerate(_segments(trace), 1):
        when = f"au démarrage n° {k}" if len(_segments(trace)) > 1 else "au démarrage"
        cfg = _first(seg, lambda e: e["ev"] == "gpio_config" and e["pin"] == PIN and e["mode"] in OUTPUT_MODES)
        off = _first(seg, lambda e: e["ev"] == "gpio_set" and e["pin"] == PIN and e["level"] == 0)
        other = _first(seg, lambda e: e["ev"] in ("wifi", "mqtt", "adc_read", "nvs_set", "nvs_commit"))
        need(cfg is not None and off is not None,
             f"{label} : {when}, le relais (GPIO {PIN}) n'est pas configuré en sortie et mis à 0 (relire : « {S_RELAY} »)")
        need(other is None or max(cfg, off) < other,
             f"{label} : {when}, le relais n'est configuré et éteint qu'après « {seg[other]['ev']} » (le Wi-Fi, la NVS, le capteur ou MQTT ont déjà "
             f"démarré) : pendant ce temps il peut rester allumé ; faites-le en tout premier dans app_main (relire : « {S_RELAY} »)")


def _marks(trace: Trace) -> list[dict]:
    return trace.events("ota_mark")


def _versions(trace: Trace) -> list[str]:
    return [e["msg"].removeprefix("démarrage, version ") for e in trace.logs(tag="autotest") if e["msg"].startswith("démarrage, version ")]


def _early(trace: Trace, name: str) -> None:
    label = LABELS[name]
    _relay_first(trace, label)
    need(len(_marks(trace)) <= 1, f"{label} : {len(_marks(trace))} appels de marquage (esp_ota_mark_app_valid_cancel_rollback ou "
         f"esp_ota_mark_app_invalid_rollback_and_reboot) : un seul des deux, une seule fois, et seulement sur une image à confirmer "
         f"(après un retour arrière la carte tourne sur l'ancienne image, déjà confirmée : pas d'auto-test à refaire) (relire : « {S_DECIDE} »)")


def _service(trace: Trace, name: str) -> None:
    label, p = LABELS[name], PLAN[name]
    need(trace.events("mqtt", event="connected"), f"{label} : le client MQTT n'a jamais pu se connecter : le client du TP 10 est fourni, "
         f"n'y touchez pas (relire : « {S_TEST} »)")
    pubs = [e for e in trace.events("mqtt_publish", topic=T_TELE) if e["t_ms"] > p["tele_after"]]
    need(pubs, f"{label} : plus aucune télémétrie après {_s(p['tele_after'])} : le service doit continuer (ou reprendre après le redémarrage) ; "
         f"l'auto-test ne doit pas bloquer le programme plus que son délai (relire : « {S_TEST} »)")
    marks = trace.gpio_levels(PIN)
    if name != "b":  # en b le capteur est muet : le code fourni refuse d'allumer la pompe
        until = p["relay_off"] or p["max_ms"]
        need(_levels_in(marks, p["relay_on"] + REACT_MS, until) == {1},
             f"{label} : la commande {{\"relay\": true}} de {_s(p['relay_on'])} n'allume pas le relais : le service doit tourner (ou reprendre) "
             f"(relire : « {S_POWER} »)")
    if p["relay_off"]:
        need(_levels_in(marks, p["relay_off"] + REACT_MS, p["max_ms"]) == {0},
             f"{label} : la commande {{\"relay\": false}} de {_s(p['relay_off'])} n'éteint pas le relais (relire : « {S_POWER} »)")


def _no_decision(trace: Trace, label: str, section: str) -> None:
    need(not _marks(trace), f"{label} : un marquage de l'image (ota_mark) a eu lieu alors qu'aucune décision n'était à prendre (relire : « {section} »)")
    need(not trace.events("rollback"),
         f"{label} : un retour arrière a eu lieu (relire : « {section} »)")


def _failure_logged(trace: Trace, label: str, mark: dict) -> None:
    need([e for e in trace.logs(tag="autotest") if e["level"] in ("W", "E") and e["t_ms"] <= mark["t_ms"]],
         f"{label} : l'échec n'est pas journalisé avant l'appel de retour arrière : écrivez un ESP_LOGW ou ESP_LOGE de tag « autotest » qui dit "
         f"pourquoi (le redémarrage efface tout) (relire : « {S_DECIDE} »)")


def _check_a(trace: Trace) -> None:
    label = LABELS["a"]
    marks = _marks(trace)
    need(marks, f"{label} : l'image n'est jamais confirmée : après un auto-test réussi, appelez esp_ota_mark_app_valid_cancel_rollback ; sans "
         f"cela la carte reviendra à l'ancienne version au prochain redémarrage (relire : « {S_DECIDE} »)")
    m = marks[0]
    need(m["valid"], f"{label} : l'auto-test a réussi mais l'image est marquée invalide (relire : « {S_DECIDE} »)")
    connected = trace.events("mqtt", event="connected")[0]["t_ms"]
    need(m["t_ms"] >= connected, f"{label} : l'image est confirmée à {_s(m['t_ms'])}, avant la connexion MQTT de {_s(connected)} : "
         f"l'auto-test n'a pas attendu MQTT (relire : « {S_TEST} »)")
    need(m["t_ms"] <= connected + DECIDE_MS, f"{label} : l'image est confirmée à {_s(m['t_ms'])}, plus de {_s(DECIDE_MS)} après la connexion MQTT "
         f"({_s(connected)}) : confirmez dès que l'auto-test a réussi (relire : « {S_TEST} »)")
    need([e for e in trace.events("adc_read", channel=CHANNEL) if e["t_ms"] <= m["t_ms"] and RAW_MIN_OK <= e["raw"] <= RAW_MAX_OK],
         f"{label} : le capteur n'a pas été lu avant la confirmation : l'auto-test doit lire le capteur (relire : « {S_TEST} »)")
    need(not trace.events("rollback") and not trace.events("reboot"),
         f"{label} : retour arrière ou redémarrage alors que l'auto-test a réussi (relire : « {S_DECIDE} »)")
    need(_versions(trace) == [V_NEW], f"{label} : versions annoncées {_versions(trace)} au lieu de [{V_NEW}] (relire : « {S_DECIDE} »)")


def _rolled_back(trace: Trace, label: str, mark: dict) -> None:
    need(not mark["valid"], f"{label} : l'auto-test a échoué mais l'image est confirmée (valid) : une image qui échoue à son auto-test ne doit "
         f"jamais être validée (relire : « {S_DECIDE} »)")
    rb = trace.events("rollback")
    need(len(rb) == 1 and rb[0]["why"] == "marked_invalid" and rb[0]["from"] == V_NEW and rb[0]["to"] == V_OLD,
         f"{label} : le retour arrière vers {V_OLD} n'a pas eu lieu comme prévu : l'appel de retour arrière marque l'image invalide puis redémarre "
         f"sur l'emplacement précédent (relire : « {S_ROLLBACK} »)")
    reboots = trace.events("reboot")
    need(len(reboots) == 1 and reboots[0]["reason"] == "sw" and mark["t_ms"] <= reboots[0]["t_ms"] <= mark["t_ms"] + REBOOT_MS,
         f"{label} : {len(reboots)} redémarrage(s) : le retour arrière redémarre la carte une seule fois (relire : « {S_DECIDE} »)")
    need(_versions(trace) == [V_NEW, V_OLD], f"{label} : après le retour arrière la carte devrait annoncer la version {V_OLD} (versions annoncées : "
         f"{_versions(trace)}) (relire : « {S_DECIDE} »)")
    _failure_logged(trace, label, mark)


def _check_b(trace: Trace) -> None:
    label = LABELS["b"]
    marks = _marks(trace)
    need(marks, f"{label} : le capteur ne répond pas de façon plausible (valeur brute 0, hors de [{RAW_MIN_OK}, {RAW_MAX_OK}]) mais aucun retour "
         f"arrière n'est demandé : appelez esp_ota_mark_app_invalid_rollback_and_reboot quand l'auto-test échoue (relire : « {S_DECIDE} »)")
    m = marks[0]
    need(m["valid"] is False, f"{label} : l'image est confirmée alors que le capteur est muet : l'auto-test ignore-t-il le capteur ? "
         f"(relire : « {S_TEST} »)")
    need(m["t_ms"] <= LATE_MS, f"{label} : décision à {_s(m['t_ms'])} : l'auto-test dure au plus {_s(DELAY_MS)} (relire : « {S_TEST} »)")
    _rolled_back(trace, label, m)
    need(_levels_in(trace.gpio_levels(PIN), 0, PLAN["b"]["max_ms"]) == {0},
         f"{label} : le relais s'est allumé alors que le capteur est muet : ne modifiez pas le code fourni (relire : « {S_RELAY} »)")


def _check_c(trace: Trace) -> None:
    label = LABELS["c"]
    marks = _marks(trace)
    need(marks, f"{label} : MQTT ne s'est jamais connecté mais aucune décision n'est prise : l'attente doit avoir un délai fini "
         f"({_s(DELAY_MS)}), puis retour arrière (relire : « {S_TEST} »)")
    m = marks[0]
    need(m["valid"] is False, f"{label} : l'image est confirmée alors que MQTT n'a jamais fonctionné (relire : « {S_DECIDE} »)")
    need(EARLY_MS <= m["t_ms"] <= LATE_MS, f"{label} : décision à {_s(m['t_ms'])} : le délai de l'auto-test est de {_s(DELAY_MS)} "
         f"(le contrôle accepte de {_s(EARLY_MS)} à {_s(LATE_MS)}) (relire : « {S_TEST} »)")
    _rolled_back(trace, label, m)


def _check_d(trace: Trace) -> None:
    label = LABELS["d"]
    need(not _marks(trace), f"{label} : un marquage de l'image a eu lieu (à {_s(_marks(trace)[0]['t_ms'] if _marks(trace) else 0)}) : avant la "
         f"coupure l'auto-test n'était pas fini (courtier absent), et après elle la carte tourne sur l'ancienne image, déjà confirmée : "
         f"aucun appel n'est à faire (relire : « {S_POWER} »)")
    rb = trace.events("rollback")
    need(len(rb) == 1 and rb[0]["why"] == "not_validated" and rb[0]["from"] == V_NEW and rb[0]["to"] == V_OLD,
         f"{label} : le démarrage suivant devait revenir de {V_NEW} à {V_OLD} (image jamais confirmée) (relire : « {S_POWER} »)")
    need(_versions(trace) == [V_NEW, V_OLD], f"{label} : versions annoncées {_versions(trace)} au lieu de [{V_NEW}, {V_OLD}] (relire : « {S_POWER} »)")


def _check_e(trace: Trace) -> None:
    label = LABELS["e"]
    marks = _marks(trace)
    need(marks and marks[0]["valid"], f"{label} : le courtier est joignable à 41 s, bien avant la fin des {_s(DELAY_MS)} : l'auto-test aurait dû "
         f"réussir et confirmer l'image ; le délai est-il trop court, ou la tentative n'est-elle pas relancée ? (relire : « {S_TEST} »)")
    connected = trace.events("mqtt", event="connected")[0]["t_ms"]
    need(marks[0]["t_ms"] >= connected and marks[0]["t_ms"] <= connected + DECIDE_MS,
         f"{label} : confirmation à {_s(marks[0]['t_ms'])}, connexion MQTT à {_s(connected)} : confirmez dès la connexion, pas avant, pas bien après "
         f"(relire : « {S_TEST} »)")
    need(not trace.events("rollback") and not trace.events("reboot"),
         f"{label} : retour arrière ou redémarrage alors que l'auto-test a réussi (relire : « {S_DECIDE} »)")


def _check_f(trace: Trace) -> None:
    label = LABELS["f"]
    _no_decision(trace, label, S_STATE)
    need(not trace.events("reboot"), f"{label} : la carte a redémarré : une carte flashée par câble n'a ni auto-test ni retour arrière "
         f"(relire : « {S_STATE} »)")
    need(_versions(trace) == [V_OLD], f"{label} : versions annoncées {_versions(trace)} (relire : « {S_STATE} »)")


def _check_g(trace: Trace) -> None:
    label = LABELS["g"]
    marks = _marks(trace)
    need(marks, f"{label} : l'image reste à l'essai sans jamais décider : le programme est bloqué quelque part. Toute attente doit avoir un délai fini, "
         f"y compris l'attente de l'adresse IP du code fourni (portMAX_DELAY interdit) (relire : « {S_TEST} »)")
    m = marks[0]
    need(m["valid"] is False, f"{label} : l'image est confirmée alors que le réseau n'a jamais fonctionné (relire : « {S_DECIDE} »)")
    need(EARLY_MS <= m["t_ms"] <= LATE_MS, f"{label} : décision à {_s(m['t_ms'])} : l'essai dure {_s(DELAY_MS)} au plus, comptées depuis le démarrage de "
         f"la carte (l'attente du Wi-Fi en a déjà consommé une partie : esp_timer_get_time) (le contrôle accepte de {_s(EARLY_MS)} à {_s(LATE_MS)}) "
         f"(relire : « {S_TEST} »)")
    _rolled_back(trace, label, m)


CHECKS = (("a", _check_a), ("b", _check_b), ("c", _check_c), ("d", _check_d), ("e", _check_e), ("f", _check_f), ("g", _check_g))


def verify(traces: dict, source: str) -> None:
    _check_source(source)
    for name, fn in CHECKS:
        _early(traces[name], name)
        fn(traces[name])
        if name != "g":  # en g le Wi-Fi reste coupé : pas de service à juger
            _service(traces[name], name)
