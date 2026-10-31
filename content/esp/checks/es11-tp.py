"""TP es11 : mises à jour OTA. Le client MQTT/TLS d'es10 (fourni) reçoit {"ota": "<url>"} sur home/devices/pool-ctl/command. L'apprenant écrit
la comparaison de versions (version_plus_recente), le gestionnaire (drapeau BIT_OTA, rien de bloquant) et mettre_a_jour : refuser une adresse
qui n'est pas en https:// ou une version qui n'est pas strictement plus récente, éteindre le relais, esp_https_ota avec le certificat du serveur,
journaliser l'échec, et ne redémarrer qu'après un succès.

Sept exécutions (SCENARIOS), niveau constant de 72,5 % ; le serveur de micrologiciels est broker.local (certificat "@generate") ; les adresses
sont https://broker.local:8443/firmware/pool-ctl-<version>.bin. {"relay": true} à 20 s, {"ota": adresse} à 40 s, puis {"relay": true} de nouveau
à 41 s (pendant le téléchargement, s'il a lieu : le relais doit rester éteint), 100 s en tout :
  a : version courante 1.9.0, image 1.10.0 valide : mise à jour puis redémarrage ; {"relay": true} à 70 s.
  b : courante 1.4.2, image 2.0.0 corrompue (ESP_ERR_OTA_VALIDATE_FAILED) : échec journalisé, pas de redémarrage ; {"relay": true} à 70 s.
  c : courante 1.2.0, image 1.2.0 : version identique, aucune mise à jour ; {"relay": false} à 80 s.
  d : courante 1.0.0, image 1.0.1 coupée à 60 % (ESP_FAIL) : échec journalisé, pas de redémarrage ; {"relay": true} à 70 s.
  e : courante 1.10.0, image 1.9.9 : version plus ancienne, aucune mise à jour ; {"relay": false} à 80 s.
  f : courante 1.0.0, adresse en http:// : refusée (aucun téléchargement en clair) ; {"relay": false} à 80 s.
  g : courante 1.0.0, image « 1.2.3a » : version qui n'a pas la forme x.y.z, refusée ; {"relay": false} à 80 s.

Le contrôle juge la trace et lit le texte du programme pour deux choses : aucune option qui réduit la vérification (comme au TP 10) et aucun
ESP_ERROR_CHECK autour de esp_https_ota. Commentaires et chaînes sont retirés avant la recherche.

Tolérances : le téléchargement commence au plus 10 s après la commande ; le redémarrage a lieu au plus 10 s après la fin d'une mise à jour réussie ;
relais commuté au plus 1 s après une commande.
"""
import json
import re

from esp_trace import Trace, need

PIN = 5
CHANNEL = 6
BASE = "home/devices/pool-ctl"
T_TELE, T_CMD = f"{BASE}/telemetry", f"{BASE}/command"
LEVEL = 72.5
FW = "https://broker.local:8443/firmware/pool-ctl-{}.bin"
HTTP_FW = "http://broker.local:8080/firmware/pool-ctl-1.1.0.bin"
MAX_OUT = 4_000_000
MAX_MS = 100_000
T_ON, T_OTA, T_PUSH, T_NEXT = 20_000, 40_000, 41_000, 70_000
T_OFF = 80_000
REACT_MS, START_MS, RESTART_MS = 1_000, 10_000, 10_000
OUTPUT_MODES = {"output", "input_output"}

# nom -> (version courante, version de l'image, valide, coupure %, adresse de la commande, True : {"relay": true} à 70 s, sinon {"relay": false} à 80 s)
CASES = {
    "a": ("1.9.0", "1.10.0", True, None, FW.format("1.10.0"), True),
    "b": ("1.4.2", "2.0.0", False, None, FW.format("2.0.0"), True),
    "c": ("1.2.0", "1.2.0", True, None, FW.format("1.2.0"), False),
    "d": ("1.0.0", "1.0.1", True, 60, FW.format("1.0.1"), True),
    "e": ("1.10.0", "1.9.9", True, None, FW.format("1.9.9"), False),
    "f": ("1.0.0", "1.1.0", True, None, HTTP_FW, False),
    "g": ("1.0.0", "1.2.3a", True, None, FW.format("1.2.3a"), False),
}
UPDATES = ("a", "b", "d")  # l'adresse est acceptée : le téléchargement doit avoir lieu
REFUSED = ("c", "e", "f", "g")
LABELS = {
    "a": "scénario a (image 1.10.0 plus récente que 1.9.0)",
    "b": "scénario b (image corrompue)",
    "c": "scénario c (version identique)",
    "d": "scénario d (connexion coupée à 60 %)",
    "e": "scénario e (version plus ancienne)",
    "f": "scénario f (adresse en http://)",
    "g": "scénario g (version 1.2.3a qui n'est pas de la forme x.y.z)",
}
EXPECTED_ERR = {"b": "ESP_ERR_OTA_VALIDATE_FAILED", "d": "ESP_FAIL"}


def _scenario(name: str) -> dict:
    running, version, valid, drop, url, relay_after = CASES[name]
    incoming = [(T_ON, '{"relay": true}'), (T_OTA, json.dumps({"ota": url})), (T_PUSH, '{"relay": true}')]
    incoming.append((T_NEXT, '{"relay": true}') if relay_after else (T_OFF, '{"relay": false}'))
    tank = {"level_pct0": LEVEL, "fill_pct_per_min": 0, "loss_pct_per_min": 0, "relay_pin": PIN, "adc_channel": CHANNEL,
            "raw_at_0": 620, "raw_at_100": 3723}
    image = {"url": url, "version": version, "valid": valid, "drop_at_pct": drop}
    return {"plant": {"tank": tank}, "mqtt": {"incoming": [{"t_ms": t, "topic": T_CMD, "payload": p} for t, p in incoming]},
            "tls": {"server_cert": "@generate"}, "nvs": {"mqtt": {"user": "piscine-ctl-07", "pass": "Pz9-ke4N-77qL"}},
            "ota": {"images": [image], "running_version": running}}


SCENARIOS = {name: (_scenario(name), MAX_MS) for name in CASES}

S_SLOTS = "Deux slots et la table de partitions"
S_OTA = "esp_https_ota : mettre à jour en une fonction"
S_VERIF = "Vérifier le serveur, et jamais en clair"
S_VERSION = "Comparer les versions"
S_IMAGE = "Valider l'image : signature et erreurs"
S_FAIL = "Un échec ne doit rien casser"
S_RESTART = "Quand redémarrer, et ce qui suit"
S_FLOW = "Ne pas bloquer le gestionnaire MQTT"


def _s(ms: float) -> str:
    return f"{ms / 1000:g}".replace(".", ",") + " s"


# ---- analyse du texte du programme ----

def _code(source: str) -> str:
    """Le texte sans commentaires ni chaînes littérales."""
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"', " ", source, flags=re.S)


SKIP_CN = re.compile(r"\bskip_cert_common_name_check\b(?!\s*=\s*(?:\(\s*bool\s*\)\s*)?(?:false|0)\s*[;,})])")
BYPASS = re.compile(r"\b(?:CONFIG_ESP_TLS_INSECURE|CONFIG_ESP_TLS_SKIP_SERVER_CERT_VERIFY|skip_server_cert_verify|skip_common_name)\b")
CHECKED_OTA = re.compile(r"\bESP_ERROR_CHECK\s*\(\s*esp_https_ota\s*\(")


def _check_source(source: str) -> None:
    code = _code(source)
    need(not SKIP_CN.search(code), "le programme touche à skip_cert_common_name_check : cette option supprime la vérification du nom du serveur "
         f"(relire : « {S_VERIF} »)")
    m = BYPASS.search(code)
    need(not m, f"le programme utilise « {m and m.group(0)} » : une option qui coupe la vérification du certificat est interdite "
         f"(relire : « {S_VERIF} »)")
    need(not CHECKED_OTA.search(code), "esp_https_ota est appelée dans ESP_ERROR_CHECK : un échec de mise à jour (image corrompue, connexion "
         f"coupée) est attendu et ne doit pas arrêter la carte ; testez le code renvoyé (relire : « {S_FAIL} »)")


# ---- lecture de la trace ----

def _levels_in(marks: list[tuple[int, int]], a: int, b: int) -> set[int]:
    cur = 0
    for t, lv in marks:
        if t <= a:
            cur = lv
    return {cur} | {lv for t, lv in marks if a < t < b}


def _logs(trace: Trace, since: int, levels=("W", "E")) -> list[dict]:
    return [e for e in trace.logs(tag="ota") if e["level"] in levels and e["t_ms"] >= since]


def _common(trace: Trace, name: str) -> None:
    label = LABELS[name]
    need(trace.events("mqtt", event="connected"), f"{label} : le client MQTT n'a jamais pu se connecter : le client du TP 10 est fourni, "
         f"n'y touchez pas (relire : « {S_FLOW} »)")
    need(any(e["pin"] == PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} du relais n'est pas configurée en sortie (relire : « {S_FAIL} »)")
    for e in trace.events("tls_handshake"):
        need(e["verify"] != "cn_skipped", f"{label} : la vérification du nom du serveur est désactivée (skip_cert_common_name_check) "
             f"(relire : « {S_VERIF} »)")
        if e["ok"]:
            continue
        why = e["verify"]
        hint = ("le certificat donné n'est pas celui du serveur, ou le paquet de certificats public (crt_bundle_attach) ne contient pas "
                "l'autorité d'un serveur privé : donnez http.cert_pem = _binary_server_cert_pem_start" if why == "failed:not_trusted"
                else f"raison : {why}")
        need(False, f"{label} : la poignée de main TLS de {_s(e['t_ms'])} avec {e['host']} échoue ({hint}) (relire : « {S_VERIF} »)")
    pubs = [e for e in trace.events("mqtt_publish", topic=T_TELE) if e["t_ms"] > T_NEXT]
    need(pubs, f"{label} : plus aucune télémétrie après {_s(T_NEXT)} : le service doit continuer après une mise à jour, réussie, échouée ou "
         f"refusée ; rien ne doit bloquer ou arrêter la boucle (relire : « {S_FAIL} »)")


def _check_update(trace: Trace, name: str) -> None:
    label = LABELS[name]
    url = CASES[name][4]
    begins = trace.events("ota_begin")
    need(begins, f"{label} : aucun téléchargement commencé : la commande {{\"ota\": ...}} est-elle reçue (gestionnaire : BIT_OTA), "
         f"la version proposée est-elle jugée strictement plus récente que {CASES[name][0]} (comparaison des nombres, pas des textes), "
         f"et esp_https_ota reçoit-elle http.cert_pem (sans option de vérification elle renvoie ESP_ERR_INVALID_ARG) ? "
         f"(relire : « {S_VERSION} »)")
    need(len(begins) == 1, f"{label} : {len(begins)} téléchargements : une commande = une seule tentative (relire : « {S_FAIL} »)")
    b = begins[0]
    need(b["url"] == url, f"{label} : le téléchargement vise {b['url']} au lieu de l'adresse de la commande (relire : « {S_OTA} »)")
    need(not b["cleartext"], f"{label} : le téléchargement se fait en clair (http://) : le micrologiciel pourrait être remplacé par un "
         f"attaquant (relire : « {S_VERIF} »)")
    need(T_OTA <= b["t_ms"] <= T_OTA + START_MS, f"{label} : le téléchargement commence à {_s(b['t_ms'])} alors que la commande est de "
         f"{_s(T_OTA)} (au plus {_s(START_MS)} accordées) (relire : « {S_FLOW} »)")
    ends = trace.events("ota_end")
    need(ends, f"{label} : le téléchargement n'a pas de fin dans la trace (relire : « {S_OTA} »)")
    end = ends[0]
    marks = trace.gpio_levels(PIN)
    need(_levels_in(marks, T_ON + REACT_MS, T_OTA) == {1},
         f"{label} : le relais devrait être allumé de {_s(T_ON + REACT_MS)} à {_s(T_OTA)} (commande de {_s(T_ON)}, niveau 72,5 %) : "
         f"ne modifiez pas le code fourni (relire : « {S_FAIL} »)")
    need(_levels_in(marks, b["t_ms"], T_NEXT) == {0},
         f"{label} : le relais n'est pas éteint pendant la mise à jour (début {_s(b['t_ms'])}, fin {_s(end['t_ms'])}) ou se rallume "
         f"avant la prochaine commande : éteignez-le avant esp_https_ota et laissez-le éteint ; si le téléchargement est fait dans le gestionnaire "
         f"MQTT, les commandes reçues pendant qu'il dure attendent et s'exécutent après : levez BIT_OTA et téléchargez dans app_main "
         f"(relire : « {S_FLOW} »)")
    reboots = trace.events("reboot")
    if name == "a":
        need(end["ok"], f"{label} : la mise à jour a échoué ({end['err']}) alors que l'image est valide (relire : « {S_OTA} »)")
        need(len(reboots) == 1 and reboots[0]["reason"] == "sw",
             f"{label} : {len(reboots)} redémarrage(s) : après une mise à jour réussie il en faut un seul, par esp_restart (relire : « {S_RESTART} »)")
        r = reboots[0]
        need(end["t_ms"] <= r["t_ms"] <= end["t_ms"] + RESTART_MS, f"{label} : redémarrage à {_s(r['t_ms'])}, la mise à jour s'est "
             f"terminée à {_s(end['t_ms'])} (au plus {_s(RESTART_MS)} accordées) (relire : « {S_RESTART} »)")
        boots = [e for e in trace.logs(tag="ota") if e["msg"].startswith("démarrage, version ")]
        need(any(e["t_ms"] >= r["t_ms"] and e["msg"].endswith(" " + CASES[name][1]) for e in boots),
             f"{label} : après le redémarrage la carte devrait annoncer la version {CASES[name][1]} : le nouveau micrologiciel ne tourne pas "
             f"(relire : « {S_RESTART} »)")
        need(_levels_in(marks, T_NEXT + REACT_MS, MAX_MS) == {1},
             f"{label} : la commande {{\"relay\": true}} de {_s(T_NEXT)} n'allume pas le relais après le redémarrage : le service doit "
             f"reprendre (relire : « {S_RESTART} »)")
        return
    err = EXPECTED_ERR[name]
    need(not end["ok"] and end["err"] == err, f"{label} : la mise à jour devait échouer par {err} (résultat : {end['err']}) (relire : « {S_IMAGE} »)")
    need(not reboots, f"{label} : la carte a redémarré à {_s(reboots[0]['t_ms'] if reboots else 0)} malgré l'échec : on ne redémarre qu'après "
         f"un succès, sinon la carte repart sans rien de neuf et coupe le service (relire : « {S_RESTART} »)")
    need([e for e in _logs(trace, end["t_ms"]) if err in e["msg"]],
         f"{label} : l'échec n'est pas journalisé : écrivez un ESP_LOGE de tag « ota » dont le texte contient le nom du code d'erreur "
         f"({err}, par esp_err_to_name) (relire : « {S_FAIL} »)")
    need(_levels_in(marks, T_NEXT + REACT_MS, MAX_MS) == {1},
         f"{label} : la commande {{\"relay\": true}} de {_s(T_NEXT)} n'allume pas le relais : après un échec le service doit continuer "
         f"(relire : « {S_FAIL} »)")


def _check_refused(trace: Trace, name: str) -> None:
    label = LABELS[name]
    running, version, _, _, url, _ = CASES[name]
    begins = trace.events("ota_begin")
    if name == "f":
        need(not begins, f"{label} : un téléchargement a été lancé pour une adresse en http:// (en clair : esp_https_ota ne refuse pas ce "
             f"schéma, c'est à vous de le refuser) (relire : « {S_VERIF} »)")
        tokens = [url]
    elif name == "g":
        need(not begins, f"{label} : un téléchargement a été lancé pour la version « {version} » : une version qui n'a pas exactement la forme x.y.z "
             f"(trois nombres séparés par des points, rien après) n'est jamais plus récente ; vérifiez la valeur renvoyée par sscanf "
             f"(relire : « {S_VERSION} »)")
        tokens = sorted({version, running})
    else:
        need(not begins, f"{label} : un téléchargement a été lancé alors que la version proposée {version} n'est pas strictement plus récente "
             f"que {running} : comparez les versions avant de télécharger (relire : « {S_VERSION} »)")
        tokens = sorted({version, running})
    need(not trace.events("ota_end"), f"{label} : une mise à jour a eu lieu alors qu'elle devait être refusée (relire : « {S_VERSION} »)")
    need(not trace.events("reboot"), f"{label} : la carte a redémarré alors qu'aucune mise à jour n'a eu lieu (relire : « {S_RESTART} »)")
    need([e for e in _logs(trace, T_OTA) if all(t in e["msg"] for t in tokens)],
         f"{label} : le refus n'est pas journalisé : écrivez un ESP_LOGW de tag « ota » dont le texte contient "
         + ("l'adresse refusée" if name == "f" else "la version proposée et la version courante") + f" (relire : « {S_FAIL} »)")
    marks = trace.gpio_levels(PIN)
    need(_levels_in(marks, T_ON + REACT_MS, T_OFF) == {1},
         f"{label} : le relais n'est pas resté allumé de {_s(T_ON + REACT_MS)} à {_s(T_OFF)} : une demande refusée ne touche pas à la pompe, "
         f"n'éteignez le relais que si une mise à jour démarre vraiment (relire : « {S_FAIL} »)")
    need(_levels_in(marks, T_OFF + REACT_MS, MAX_MS) == {0},
         f"{label} : la commande {{\"relay\": false}} de {_s(T_OFF)} n'éteint pas le relais (relire : « {S_FAIL} »)")


def verify(traces: dict, source: str) -> None:
    _check_source(source)
    for name in CASES:
        _common(traces[name], name)
        (_check_update if name in UPDATES else _check_refused)(traces[name], name)
