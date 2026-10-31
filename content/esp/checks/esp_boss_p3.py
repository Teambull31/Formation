"""Boss final, phase 3 : le contrôleur livrable (mises à jour OTA, auto-test et retour arrière ; leçons es11 et es12).

Le programme de la phase 2 reçoit aussi {"ota": "<url>"} sur home/devices/pool-ctl/command (adresses https://hôte:port/firmware/pool-ctl-<version>.bin).
Il refuse une adresse qui n'est pas en https:// ou une version qui n'est pas strictement plus récente que la version courante (comparaison des
NOMBRES x.y.z), éteint la pompe, télécharge avec esp_https_ota en donnant le certificat du serveur (http.cert_pem), journalise l'échec (ESP_LOGE, tag
« ota », avec esp_err_to_name) et ne redémarre qu'après un succès. À chaque démarrage il annonce sa version : ESP_LOGI de tag « pool », texte exact
« démarrage, version X.Y.Z ». Quand l'image qui tourne est à confirmer (état ESP_OTA_IMG_PENDING_VERIFY), il fait l'auto-test (capteur lisible dans
[300, 3900] ET MQTT connecté, au plus 60 s après le DÉMARRAGE de la carte, attente du Wi-Fi comprise) puis confirme l'image
(esp_ota_mark_app_valid_cancel_rollback) ou, s'il échoue, journalise la cause (ESP_LOGW ou ESP_LOGE, tag « autotest »), éteint la pompe et appelle
esp_ota_mark_app_invalid_rollback_and_reboot : jamais les deux, une seule fois.

Les dix exécutions de la phase 2 (a à j) sont rejouées, puis six exécutions de mise à jour (SCENARIOS k à p) : niveau constant de 50 % (la
pompe tourne), courtier et serveur de micrologiciels broker.local, version courante 1.9.0 sauf en l :
  k : image 1.10.0 valide, {"ota": adresse} à 40 s : mise à jour, redémarrage, auto-test réussi, confirmation.
  l : courante 1.4.2, image 2.0.0 corrompue (ESP_ERR_OTA_VALIDATE_FAILED) : échec journalisé, pas de redémarrage, la pompe repart.
  m : image 1.10.0 valide ; coupure de courant à 42 s, en plein téléchargement : la carte reprend sur l'ancienne image (1.9.0), la pompe repart ;
      la commande {"ota": adresse} revient à 80 s : cette fois la mise à jour va au bout et l'image est confirmée.
  n : adresse https://updates.example.net:8443/... : le certificat du serveur (nom broker.local) n'est pas celui de cet hôte : la poignée de main est
      refusée (ESP_ERR_HTTP_CONNECT), jamais contournée : échec journalisé, pas de redémarrage, la pompe repart.
  p : quatre commandes refusées, sans téléchargement (les images existent sur le serveur) : une adresse en http:// à 20 s (jamais de téléchargement en clair),
      la version courante 1.9.0 à 40 s (pas strictement plus récente), la version 1.8.0 à 60 s (plus ancienne), la version 1.12.3a à 80 s (qui n'a pas
      la forme x.y.z : elle n'est jamais plus récente). Chaque refus est journalisé (ESP_LOGW, tag « ota ») avec l'adresse refusée pour http://, avec
      la version proposée ET la version courante pour les autres ; la pompe n'est jamais touchée, la carte ne redémarre pas.
  o : image 1.10.0 valide mais défaillante (elle n'atteint jamais le courtier) : mise à jour, redémarrage, auto-test échoué à 60 s du démarrage :
      retour arrière vers 1.9.0, la pompe repart avec l'ancienne image.

Tolérances : le téléchargement commence au plus 10 s après la commande ; la pompe est éteinte du début du téléchargement jusqu'au redémarrage et ne
repart qu'avec la liaison ; le redémarrage a lieu au plus 10 s après une mise à jour réussie ; confirmation au plus 10 s après la connexion MQTT ;
retour arrière décidé de 55 s à 70 s après le démarrage, redémarrage au plus 5 s plus tard ; la pompe repart au plus 5 s après la confirmation (15 s après
un redémarrage) ; télémétrie de 9 s à 11 s (la durée du téléchargement en plus).

Le contrôle lit aussi le texte du programme (commentaires et chaînes retirés) : aucune option qui réduit la vérification TLS, aucun identifiant en
clair, aucun ESP_ERROR_CHECK autour de esp_https_ota.
"""
import json

from esp_trace import Trace, fmt_s as _s, need, load_check

es11 = load_check("es11-tp")
es12 = load_check("es12-tp")
p2 = load_check("esp_boss_p2")

PIN = p2.PIN
V_OLD, V_NEW = "1.9.0", "1.10.0"
FW = es11.FW
FW_OTHER = "https://updates.example.net:8443/firmware/pool-ctl-1.10.0.bin"
START_MS, RESTART_MS, DECIDE_MS, REBOOT_MS = 10_000, 10_000, 10_000, 5_000
DELAY_MS, EARLY_MS, LATE_MS = 60_000, 55_000, 70_000
RESUME_MS, BOOT_RESUME_MS = 5_000, 15_000
MAX_OUT = p2.MAX_OUT
S_SAFE_START = p2.S_SAFE_START
S_SLOTS, S_OTA, S_VERIF, S_VERSION, S_IMAGE, S_FAIL, S_RESTART, S_FLOW = (
    es11.S_SLOTS, es11.S_OTA, es11.S_VERIF, es11.S_VERSION, es11.S_IMAGE, es11.S_FAIL, es11.S_RESTART, es11.S_FLOW)
S_ROLLBACK, S_STATE, S_TEST, S_DECIDE, S_POWER = es12.S_ROLLBACK, es12.S_STATE, es12.S_TEST, es12.S_DECIDE, es12.S_POWER
S_BOOT = p2.S_BOOT

IMG_OK = {"url": FW.format(V_NEW), "version": V_NEW, "valid": True, "drop_at_pct": None}
CASES = {  # nom -> (version courante, images du serveur, commandes {"ota": ...} : instants, redémarrages du scénario, durée)
    "k": (V_OLD, [IMG_OK], [40_000], [], 160_000),
    "l": ("1.4.2", [{"url": FW.format("2.0.0"), "version": "2.0.0", "valid": False, "drop_at_pct": None}], [40_000], [], 120_000),
    "m": (V_OLD, [IMG_OK], [40_000, 80_000], [42_000], 150_000),
    "n": (V_OLD, [{"url": FW_OTHER, "version": V_NEW, "valid": True, "drop_at_pct": None}], [40_000], [], 120_000),
    "o": (V_OLD, [IMG_OK], [40_000], [], 180_000),
}
HTTP_FW = "http://broker.local:8080/firmware/pool-ctl-1.11.0.bin"
REFUSED = [  # (instant, adresse, version proposée, texte attendu dans le journal)
    (20_000, HTTP_FW, "1.11.0", [HTTP_FW]),
    (40_000, FW.format(V_OLD), V_OLD, [V_OLD]),
    (60_000, FW.format("1.8.0"), "1.8.0", ["1.8.0", V_OLD]),
    (80_000, FW.format("1.12.3a"), "1.12.3a", ["1.12.3a", V_OLD]),
]
MAX_P = 120_000
URL = {"k": FW.format(V_NEW), "l": FW.format("2.0.0"), "m": FW.format(V_NEW), "n": FW_OTHER, "o": FW.format(V_NEW)}
LABELS = {
    "k": "scénario k (mise à jour valide 1.9.0 vers 1.10.0)",
    "l": "scénario l (image corrompue)",
    "m": "scénario m (coupure de courant en plein téléchargement)",
    "n": "scénario n (certificat qui n'est pas celui du serveur de mise à jour)",
    "o": "scénario o (nouvelle image défaillante : retour arrière)",
    "p": "scénario p (adresse en http:// et trois versions refusées)",
}


def _scenario(name: str) -> dict:
    running, images, cmds, reboots, _ = CASES[name]
    sc = p2.net(p2._tank(p2.LEVEL), [(t, json.dumps({"ota": URL[name]})) for t in cmds], reboots=reboots)
    sc["ota"] = {"images": images, "running_version": running}
    if name == "o":
        sc["boot"] = {"self_test_fails": True}
    return sc


def _scenario_p() -> dict:
    sc = p2.net(p2._tank(p2.LEVEL), [(t, json.dumps({"ota": url})) for t, url, _, _ in REFUSED])
    sc["ota"] = {"images": [{"url": url, "version": v, "valid": True, "drop_at_pct": None} for _, url, v, _ in REFUSED], "running_version": V_OLD}
    return sc


SCENARIOS = {**p2.SCENARIOS, **{name: (_scenario(name), CASES[name][4]) for name in CASES}, "p": (_scenario_p(), MAX_P)}
# L'analyse de la liaison, de la télémétrie et du relais au démarrage est celle de la phase 2 : on lui déclare les nouvelles exécutions.
p2.LABELS.update(LABELS)
p2.MAX_MS.update({**{name: CASES[name][4] for name in CASES}, "p": MAX_P})
p2.LEVEL_OF.update({name: p2.LEVEL for name in (*CASES, "p")})


# ---- lecture de la trace ----

def _from(marks: list[tuple[int, int]], a: int, b: int) -> set[int]:
    """Niveaux de la broche de a (compris, avec l'état déjà en vigueur) à b (exclu)."""
    cur = 0
    for t, lv in marks:
        if t <= a:
            cur = lv
    return {cur} | {lv for t, lv in marks if a < t < b}


def _versions(trace: Trace) -> list[str]:
    return [e["msg"].removeprefix("démarrage, version ") for e in trace.logs(tag="pool") if e["msg"].startswith("démarrage, version ")]


def _sw_reboots(trace: Trace) -> list[dict]:
    return [e for e in trace.events("reboot") if e["reason"] == "sw"]


def _start(trace: Trace, name: str, index: int) -> dict:
    label = LABELS[name]
    t_cmd = CASES[name][2][index]
    begins = [e for e in trace.events("ota_begin") if e["t_ms"] >= t_cmd]
    need(begins, f"{label} : aucun téléchargement commencé après la commande de {_s(t_cmd)} : la commande {{\"ota\": ...}} est-elle reçue (gestionnaire : "
         f"drapeau, rien de bloquant), la version proposée est-elle jugée strictement plus récente que {V_OLD} (comparaison des nombres, pas des "
         f"textes), et esp_https_ota reçoit-elle http.cert_pem (sans option de vérification elle renvoie ESP_ERR_INVALID_ARG) ? (relire : « {S_VERSION} »)")
    b = begins[0]
    need(b["url"] == URL[name], f"{label} : le téléchargement vise {b['url']} au lieu de l'adresse de la commande (relire : « {S_OTA} »)")
    need(not b["cleartext"], f"{label} : le téléchargement se fait en clair (http://) : le micrologiciel pourrait être remplacé par un attaquant "
         f"(relire : « {S_VERIF} »)")
    need(t_cmd <= b["t_ms"] <= t_cmd + START_MS, f"{label} : le téléchargement commence à {_s(b['t_ms'])} alors que la commande est de {_s(t_cmd)} "
         f"(au plus {_s(START_MS)} accordées) : ne téléchargez pas dans le gestionnaire MQTT, levez un drapeau (relire : « {S_FLOW} »)")
    return b


def _end_after(trace: Trace, begin: dict) -> dict | None:
    ends = [e for e in trace.events("ota_end") if e["t_ms"] >= begin["t_ms"]]
    return ends[0] if ends else None


def _pump_before(trace: Trace, name: str, until: int) -> None:
    label = LABELS[name]
    need(_from(p2._marks(trace), p2.BOOT_MS, until) == {1},
         f"{label} : la pompe devrait tourner de {_s(p2.BOOT_MS)} à {_s(until)} (niveau 50 %, liaison établie) : ne cassez pas la régulation "
         f"de la phase 2 (relire : « {S_FAIL} »)")


def _pump_off_during(trace: Trace, name: str, a: int, b: int) -> None:
    need(_from(p2._marks(trace), a, b) == {0},
         f"{LABELS[name]} : la pompe n'est pas éteinte du début du téléchargement ({_s(a)}) à {_s(b)} ou se rallume avant : éteignez-la avant esp_https_ota "
         f"(pendant la mise à jour plus personne ne la surveille) et laissez-la éteinte jusqu'au redémarrage (relire : « {S_FLOW} »)")


def _pump_on_after(trace: Trace, name: str, a: int, why: str, section: str) -> None:
    need(_from(p2._marks(trace), a, CASES[name][4]) == {1},
         f"{LABELS[name]} : la pompe ne tourne pas de {_s(a)} à la fin (niveau 50 %) : {why} (relire : « {section} »)")


def _no_decision(trace: Trace, name: str, section: str) -> None:
    label = LABELS[name]
    need(not trace.events("ota_mark"), f"{label} : un marquage de l'image (ota_mark) a eu lieu alors qu'aucune décision n'était à prendre : on ne "
         f"confirme ni n'annule que l'image à confirmer, une seule fois (relire : « {section} »)")
    need(not trace.events("rollback"), f"{label} : un retour arrière a eu lieu (relire : « {section} »)")


def _failure(trace: Trace, name: str, err_name: str) -> dict:
    label = LABELS[name]
    b = _start(trace, name, 0)
    end = _end_after(trace, b)
    need(end, f"{label} : le téléchargement n'a pas de fin dans la trace (relire : « {S_OTA} »)")
    need(not end["ok"] and end["err"] == err_name, f"{label} : la mise à jour devait échouer par {err_name} (résultat : {end['err']}) : "
         f"{'ne contournez pas la vérification du serveur' if name == 'n' else 'une image corrompue ne se confirme pas'} (relire : "
         f"« {S_VERIF if name == 'n' else S_IMAGE} »)")
    need(len(trace.events("ota_begin")) == 1, f"{label} : {len(trace.events('ota_begin'))} téléchargements : une commande = une seule tentative (relire : « {S_FAIL} »)")
    reboots = trace.events("reboot")
    need(not reboots, f"{label} : la carte a redémarré à {_s(reboots[0]['t_ms'] if reboots else 0)} malgré l'échec : on ne redémarre qu'après un "
         f"succès, sinon la carte repart sans rien de neuf et coupe le service (relire : « {S_RESTART} »)")
    need([e for e in trace.logs(tag="ota") if e["level"] == "E" and err_name in e["msg"] and e["t_ms"] >= end["t_ms"]],
         f"{label} : l'échec n'est pas journalisé : écrivez un ESP_LOGE de tag « ota » dont le texte contient le nom du code d'erreur ({err_name}, par "
         f"esp_err_to_name) (relire : « {S_FAIL} »)")
    _no_decision(trace, name, S_FAIL)
    need(_versions(trace) == [CASES[name][0]], f"{LABELS[name]} : versions annoncées {_versions(trace)} au lieu de [{CASES[name][0]}] : chaque démarrage "
         f"annonce sa version par un ESP_LOGI de tag « pool », « démarrage, version X.Y.Z » (relire : « {S_RESTART} »)")
    _pump_before(trace, name, b["t_ms"])
    _pump_off_during(trace, name, b["t_ms"], end["t_ms"])
    _pump_on_after(trace, name, end["t_ms"] + RESUME_MS, "après un échec le service continue : la régulation reprend d'elle-même (la liaison n'est pas "
                   "tombée, le niveau est sous 60 %)", S_FAIL)
    return end


def _confirmed(trace: Trace, name: str, since: int, expect_versions: list[str]) -> dict:
    """La dernière image confirmée : un seul marquage valide, après la connexion MQTT du dernier démarrage."""
    label = LABELS[name]
    marks = trace.events("ota_mark")
    need(marks, f"{label} : l'image n'est jamais confirmée : après un auto-test réussi, appelez esp_ota_mark_app_valid_cancel_rollback ; sans cela la "
         f"carte reviendra à l'ancienne version au prochain redémarrage (relire : « {S_DECIDE} »)")
    need(len(marks) == 1, f"{label} : {len(marks)} marquages de l'image : un seul, une seule fois, et seulement sur une image à confirmer (relire : « {S_DECIDE} »)")
    m = marks[0]
    need(m["valid"], f"{label} : l'auto-test a réussi mais l'image est marquée invalide (relire : « {S_DECIDE} »)")
    connected = [e["t_ms"] for e in trace.events("mqtt", event="connected") if e["t_ms"] >= since]
    need(connected, f"{label} : la nouvelle image ne se connecte jamais au courtier : le client de la phase 2 doit tourner dans toutes les versions "
         f"(relire : « {S_TEST} »)")
    need(connected[0] <= m["t_ms"] <= connected[0] + DECIDE_MS,
         f"{label} : l'image est confirmée à {_s(m['t_ms'])}, la connexion MQTT du démarrage est à {_s(connected[0])} : confirmez dès que l'auto-test "
         f"a réussi, jamais avant la connexion (relire : « {S_TEST} »)")
    need([e for e in trace.events("adc_read", channel=p2.CHANNEL) if since <= e["t_ms"] <= m["t_ms"] and es12.RAW_MIN_OK <= e["raw"] <= es12.RAW_MAX_OK],
         f"{label} : le capteur n'a pas été lu avant la confirmation : l'auto-test doit lire le capteur (relire : « {S_TEST} »)")
    need(not trace.events("rollback"), f"{label} : retour arrière alors que l'auto-test a réussi (relire : « {S_DECIDE} »)")
    need(_versions(trace) == expect_versions, f"{label} : versions annoncées {_versions(trace)} au lieu de {expect_versions} : chaque démarrage "
         f"annonce sa version par un ESP_LOGI de tag « pool », « démarrage, version X.Y.Z » (relire : « {S_RESTART} »)")
    return m


def _success(trace: Trace, name: str, index: int) -> tuple[dict, dict]:
    """Une mise à jour réussie : début, fin ok, redémarrage unique juste après. Renvoie (fin, redémarrage)."""
    label = LABELS[name]
    b = _start(trace, name, index)
    end = _end_after(trace, b)
    need(end, f"{label} : le téléchargement n'a pas de fin dans la trace (relire : « {S_OTA} »)")
    need(end["ok"], f"{label} : la mise à jour a échoué ({end['err']}) alors que l'image est valide (relire : « {S_OTA} »)")
    sw = [r for r in _sw_reboots(trace) if r["t_ms"] >= end["t_ms"]]
    need(sw, f"{label} : aucun redémarrage après la mise à jour réussie de {_s(end['t_ms'])} : il faut un esp_restart, la nouvelle image ne tourne qu'ensuite "
         f"(relire : « {S_RESTART} »)")
    r = sw[0]
    need(r["t_ms"] <= end["t_ms"] + RESTART_MS, f"{label} : redémarrage à {_s(r['t_ms'])}, la mise à jour s'est terminée à {_s(end['t_ms'])} (au plus "
         f"{_s(RESTART_MS)} accordées) (relire : « {S_RESTART} »)")
    _pump_off_during(trace, name, b["t_ms"], r["t_ms"])
    return end, r


def _check_k(trace: Trace) -> None:
    b = _start(trace, "k", 0)
    _pump_before(trace, "k", b["t_ms"])
    need(len(trace.events("ota_begin")) == 1, f"{LABELS['k']} : {len(trace.events('ota_begin'))} téléchargements : une commande = une seule tentative "
         f"(relire : « {S_FAIL} »)")
    end, r = _success(trace, "k", 0)
    need(len(trace.events("reboot")) == 1, f"{LABELS['k']} : {len(trace.events('reboot'))} redémarrages : après une mise à jour réussie il en faut un seul "
         f"(relire : « {S_RESTART} »)")
    m = _confirmed(trace, "k", r["t_ms"], [V_OLD, V_NEW])
    _pump_on_after(trace, "k", m["t_ms"] + RESUME_MS, "après la confirmation le service reprend : la régulation tourne avec la nouvelle image", S_DECIDE)


def _check_l(trace: Trace) -> None:
    _failure(trace, "l", "ESP_ERR_OTA_VALIDATE_FAILED")


def _check_n(trace: Trace) -> None:
    label = LABELS["n"]
    host = FW_OTHER.split("/")[2].split(":")[0]
    hs = [e for e in trace.events("tls_handshake") if e["host"] == host]
    need(not [e for e in hs if e["ok"] or e["verify"] == "cn_skipped"],
         f"{label} : la poignée de main avec {host} réussit (ou la vérification du nom est désactivée) alors que le certificat du serveur est "
         f"celui de broker.local : la vérification doit refuser un certificat qui n'est pas celui de l'hôte, sans contournement (relire : « {S_VERIF} »)")
    _failure(trace, "n", "ESP_ERR_HTTP_CONNECT")
    need(hs and all(e["verify"] == "failed:cn_mismatch" for e in hs),
         f"{label} : la poignée de main avec {host} devait échouer pour un nom qui ne correspond pas (failed:cn_mismatch) : {[e['verify'] for e in hs]} "
         f"(relire : « {S_VERIF} »)")


def _check_m(trace: Trace) -> None:
    label = LABELS["m"]
    b1 = _start(trace, "m", 0)
    cut = 42_000
    need(b1["t_ms"] < cut, f"{label} : le premier téléchargement commence à {_s(b1['t_ms'])}, après la coupure de courant de {_s(cut)} (relire : « {S_POWER} »)")
    _pump_before(trace, "m", b1["t_ms"])
    _pump_off_during(trace, "m", b1["t_ms"], cut)
    first_end = _end_after(trace, b1)
    need(first_end is None or first_end["t_ms"] > 80_000 - 1, f"{label} : le premier téléchargement a une fin à {_s(first_end['t_ms'] if first_end else 0)} "
         f"alors que le courant a été coupé à {_s(cut)} (relire : « {S_POWER} »)")
    need(not [e for e in trace.events("ota_mark") if e["t_ms"] < 80_000], f"{label} : un marquage de l'image a eu lieu avant la deuxième mise à jour : "
         f"après la coupure la carte tourne sur l'ancienne image, déjà confirmée : aucun appel à faire (relire : « {S_POWER} »)")
    need(not [e for e in trace.events("rollback") if e["t_ms"] < 80_000], f"{label} : un retour arrière a eu lieu après la coupure : l'image en cours "
         f"d'écriture n'a jamais été activée, l'ancienne continue (relire : « {S_POWER} »)")
    need(_from(p2._marks(trace), cut + BOOT_RESUME_MS, 80_000) == {1},
         f"{label} : la pompe ne tourne pas de {_s(cut + BOOT_RESUME_MS)} à 80 s : après la coupure de courant la carte repart sur l'ancienne image et le "
         f"service reprend (la consigne et la régulation ne dépendent pas de la mise à jour) (relire : « {S_POWER} »)")
    end, r = _success(trace, "m", 1)
    need(len(trace.events("ota_begin")) == 2, f"{label} : {len(trace.events('ota_begin'))} téléchargements au lieu de 2 : une commande = une seule tentative "
         f"(relire : « {S_FAIL} »)")
    m = _confirmed(trace, "m", r["t_ms"], [V_OLD, V_OLD, V_NEW])
    _pump_on_after(trace, "m", m["t_ms"] + RESUME_MS, "après la confirmation le service reprend", S_DECIDE)


def _check_o(trace: Trace) -> None:
    label = LABELS["o"]
    b = _start(trace, "o", 0)
    _pump_before(trace, "o", b["t_ms"])
    end, r = _success(trace, "o", 0)
    marks = trace.events("ota_mark")
    need(marks, f"{label} : la nouvelle image n'atteint jamais le courtier mais aucune décision n'est prise : l'attente de l'auto-test doit avoir un délai "
         f"fini ({_s(DELAY_MS)} depuis le démarrage), puis retour arrière (relire : « {S_TEST} »)")
    need(len(marks) == 1, f"{label} : {len(marks)} marquages de l'image : un seul, une seule fois (relire : « {S_DECIDE} »)")
    m = marks[0]
    need(m["valid"] is False, f"{label} : l'image est confirmée alors que MQTT n'a jamais fonctionné avec elle : une image qui échoue à son auto-test ne "
         f"doit jamais être validée (relire : « {S_DECIDE} »)")
    need(r["t_ms"] + EARLY_MS <= m["t_ms"] <= r["t_ms"] + LATE_MS,
         f"{label} : décision à {_s(m['t_ms'])}, {_s(m['t_ms'] - r['t_ms'])} après le démarrage de la nouvelle image : le délai de l'auto-test est de "
         f"{_s(DELAY_MS)} après le démarrage de la carte (le contrôle accepte de {_s(EARLY_MS)} à {_s(LATE_MS)}) (relire : « {S_TEST} »)")
    need([e for e in trace.logs(tag="autotest") if e["level"] in ("W", "E") and r["t_ms"] <= e["t_ms"] <= m["t_ms"]],
         f"{label} : l'échec n'est pas journalisé avant l'appel de retour arrière : écrivez un ESP_LOGW ou ESP_LOGE de tag « autotest » qui dit pourquoi "
         f"(le redémarrage efface tout) (relire : « {S_DECIDE} »)")
    rb = trace.events("rollback")
    need(len(rb) == 1 and rb[0]["why"] == "marked_invalid" and rb[0]["from"] == V_NEW and rb[0]["to"] == V_OLD,
         f"{label} : le retour arrière vers {V_OLD} n'a pas eu lieu comme prévu : l'appel de retour arrière marque l'image invalide puis redémarre sur "
         f"l'emplacement précédent (relire : « {S_ROLLBACK} »)")
    back = [e for e in _sw_reboots(trace) if e["t_ms"] >= m["t_ms"]]
    need(back and back[0]["t_ms"] <= m["t_ms"] + REBOOT_MS, f"{label} : la carte ne redémarre pas dans les {_s(REBOOT_MS)} qui suivent le retour arrière : "
         f"esp_ota_mark_app_invalid_rollback_and_reboot redémarre d'elle-même (relire : « {S_DECIDE} »)")
    need(len(trace.events("reboot")) == 2, f"{label} : {len(trace.events('reboot'))} redémarrages au lieu de 2 (la mise à jour, puis le retour arrière) "
         f"(relire : « {S_DECIDE} »)")
    need(_versions(trace) == [V_OLD, V_NEW, V_OLD], f"{label} : versions annoncées {_versions(trace)} au lieu de {[V_OLD, V_NEW, V_OLD]} : après le retour "
         f"arrière la carte annonce {V_OLD} (relire : « {S_DECIDE} »)")
    _pump_off_during(trace, "o", b["t_ms"], back[0]["t_ms"])
    need(trace.events("mqtt", event="connected") and trace.events("mqtt", event="connected")[-1]["t_ms"] >= back[0]["t_ms"],
         f"{label} : le service ne reprend pas avec l'ancienne image : la liaison MQTT n'est pas rétablie après le retour arrière (relire : « {S_ROLLBACK} »)")
    _pump_on_after(trace, "o", back[0]["t_ms"] + BOOT_RESUME_MS, "après le retour arrière l'ancienne image reprend le service : la régulation repart "
                   "(niveau 50 %, liaison rétablie)", S_ROLLBACK)


def _check_p(trace: Trace) -> None:
    label = LABELS["p"]
    for t, url, version, tokens in REFUSED:
        what = "une adresse en http:// (en clair : esp_https_ota ne refuse pas ce schéma, c'est à vous de le refuser)" if url == HTTP_FW else \
            f"la version proposée {version}, qui n'est pas strictement plus récente que {V_OLD} (ou n'a pas la forme x.y.z : trois nombres séparés par des " \
            f"points, rien après ; vérifiez la valeur renvoyée par sscanf)"
        need(not [e for e in trace.events("ota_begin") if e["t_ms"] >= t and e["url"] == url],
             f"{label} : un téléchargement a été lancé après la commande de {_s(t)} : {what} (relire : « {S_VERSION if url != HTTP_FW else S_VERIF} »)")
        need([e for e in trace.logs(tag="ota") if e["level"] == "W" and t <= e["t_ms"] <= t + START_MS and all(x in e["msg"] for x in tokens)],
             f"{label} : le refus de la commande de {_s(t)} n'est pas journalisé : écrivez un ESP_LOGW de tag « ota » dont le texte contient "
             + ("l'adresse refusée" if url == HTTP_FW else "la version proposée et la version courante") + f" (relire : « {S_FAIL} »)")
    need(not trace.events("ota_begin") and not trace.events("ota_end"), f"{label} : une mise à jour a eu lieu alors que toutes les commandes devaient être "
         f"refusées (relire : « {S_VERSION} »)")
    need(not trace.events("reboot"), f"{label} : la carte a redémarré alors qu'aucune mise à jour n'a eu lieu (relire : « {S_RESTART} »)")
    _no_decision(trace, "p", S_FAIL)
    need(_from(p2._marks(trace), p2.BOOT_MS, MAX_P) == {1}, f"{label} : la pompe n'est pas restée allumée de {_s(p2.BOOT_MS)} à la fin : une demande "
         f"refusée ne touche pas à la pompe, n'éteignez-la que si une mise à jour démarre vraiment (relire : « {S_FAIL} »)")


CHECKS = (("k", _check_k), ("l", _check_l), ("m", _check_m), ("n", _check_n), ("o", _check_o), ("p", _check_p))


def verify(traces: dict, source: str) -> None:
    p2.es10._check_source(source)
    es11._check_source(source)
    p2.verify_runs(traces)
    for name, fn in CHECKS:
        p2._net_ok(traces[name], name)
        fn(traces[name])
