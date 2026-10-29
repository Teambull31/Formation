"""TP es7 : connecter l'ESP32 au Wi-Fi (station) avec reconnexion à attente croissante, et journaliser l'adresse IP.

Deux exécutions du même programme (SCENARIOS) :
  a : la box refuse les 3 premières tentatives (wifi.fail_attempts = 3) puis accepte : 4 tentatives, attentes de
      1 s, 2 s et 4 s entre elles, adresse IP journalisée une fois (ESP_LOGI, tag « wifi », « adresse IP : 192.168.1.42 »),
      aucun ESP_LOGE de tag « wifi ».
  b : réseau absent (la box n'existe qu'à partir de 10^9 ms) pendant 120 s : EXACTEMENT 10 tentatives, attentes de
      1, 2, 4, 8, 8, 8, 8, 8, 8 s, puis UN ESP_LOGE de tag « wifi » (après le 10e échec) et plus aucune tentative.

Les tentatives se lisent dans les événements « wifi » de la trace, sans que le programme ait rien à émettre : la
station du simulateur termine une tentative refusée 1000 ms après esp_wifi_connect (sta_disconnected, raison 201 ou
205) et une tentative réussie 300 ms après (sta_connected). Le début de la tentative n°k+1 vaut donc
(sta_disconnected de k+1 - 1000 ms), ou (sta_connected - 300 ms) pour la tentative qui réussit, et l'attente après
l'échec k est ce début moins l'instant de l'échec k. Tolérance de chaque attente : de 50 ms de moins à 500 ms de plus.

Analyse statique de main.cpp (le texte, hors commentaires) :
  - le motif NVS complet (ESP_ERR_NVS_NO_FREE_PAGES, ESP_ERR_NVS_NEW_VERSION_FOUND, nvs_flash_erase) ;
  - aucun mot de passe en dur : pas de texte entre guillemets dans une instruction (ou un #define) qui parle d'un mot de
    passe (pass, pwd, mdp, secret, psk), jamais le mot de passe d'exemple du simulateur, et CONFIG_ESP_WIFI_PASSWORD utilisé ;
  - pas d'adresse IP écrite en dur (192.168.1.42).
Un secret caché autrement (un autre texte, un calcul) n'est pas détecté : c'est une garde contre l'accident.
"""
import re

from esp_trace import Trace, need

FAIL_MS, CONNECT_MS = 1000, 300  # durées d'une tentative du simulateur (wifi.cpp)
FAIL_REASONS = {201, 205}  # WIFI_REASON_NO_AP_FOUND, WIFI_REASON_CONNECTION_FAIL
WAIT_UNDER_MS, WAIT_OVER_MS = 50, 500
FIRST_WAIT_MS, MAX_WAIT_MS = 1000, 8000
MAX_TRIES = 10
IP = "192.168.1.42"
IP_MSG = f"adresse IP : {IP}"
TAG = "wifi"
SAMPLE_PASSWORD = "exemple-motdepasse"
MAX_MS = {"a": 20_000, "b": 120_000}
SCENARIOS = {
    "a": ({"wifi": {"fail_attempts": 3}}, MAX_MS["a"]),
    "b": ({"wifi": {"up_from_ms": 1_000_000_000}}, MAX_MS["b"]),
}
LABELS = {"a": "scénario a (3 échecs puis succès)", "b": "scénario b (réseau absent)"}

S_NVS = "La NVS d'abord : le motif d'initialisation"
S_STACK = "La pile réseau : esp_netif et la boucle d'événements par défaut"
S_INIT = "Initialiser et démarrer le Wi-Fi en mode station"
S_EVENTS = "Les événements Wi-Fi : qui appelle quoi, et dans quelle tâche"
S_BACKOFF = "Reconnecter sans marteler : l'attente croissante"
S_GIVEUP = "Savoir abandonner : le nombre maximal d'essais"
S_IP = "Journaliser l'adresse obtenue"
S_SECRET = "Le mot de passe ne s'écrit jamais dans le code"

_TOKEN = re.compile(r"""//[^\n]*|/\*.*?\*/|R"([^()\s]{0,16})\(.*?\)\1"|"(?:\\.|[^"\\\n])*"|(?<![0-9A-Fa-f])'(?:\\.|[^'\\\n])*'""",
                    re.S)
SECRETISH = re.compile(r"pass|pwd|mdp|secret|psk", re.I)


def _blank(source: str) -> tuple[str, str]:
    """(code, no_comments) : commentaires effacés ; dans `code` le contenu des littéraux l'est aussi (reste "")."""
    def comment(m):
        return " " if m.group(0).startswith(("//", "/*")) else m.group(0)

    def literal(m):
        t = m.group(0)
        return " " if t.startswith(("//", "/*")) else t[0] * 2 if t[0] in "\"'" else '""'

    return _TOKEN.sub(literal, source), _TOKEN.sub(comment, source)


def _static(source: str) -> None:
    code, nc = _blank(source)
    need(all(w in code for w in ("ESP_ERR_NVS_NO_FREE_PAGES", "ESP_ERR_NVS_NEW_VERSION_FOUND", "nvs_flash_erase")),
         "le motif d'initialisation de la NVS est incomplet : il faut nvs_flash_init, puis, si le résultat est "
         "ESP_ERR_NVS_NO_FREE_PAGES ou ESP_ERR_NVS_NEW_VERSION_FOUND, nvs_flash_erase et une nouvelle initialisation "
         f"(relire : « {S_NVS} »)")
    need(SAMPLE_PASSWORD not in nc, f"le mot de passe d'exemple est écrit dans main.cpp : un mot de passe ne s'écrit jamais en dur, "
         f"lisez-le dans CONFIG_ESP_WIFI_PASSWORD (relire : « {S_SECRET} »)")
    for line in code.splitlines():
        s = line.strip()
        need(not (s.startswith("#") and re.match(r"#\s*define\b", s) and SECRETISH.search(s) and '""' in s),
             f"mot de passe en dur : la ligne « {s[:60]} » met un texte entre guillemets dans un #define qui parle d'un mot de "
             f"passe : lisez-le dans CONFIG_ESP_WIFI_PASSWORD (relire : « {S_SECRET} »)")
    statements = re.split(r"[;{}]", re.sub(r"(?m)^[ \t]*#[^\n]*$", " ", code))
    for st in statements:
        need(not (SECRETISH.search(st) and '""' in st),
             "mot de passe en dur : une instruction parle d'un mot de passe et contient un texte entre guillemets "
             f"(« {' '.join(st.split())[:70]} ») : lisez-le dans CONFIG_ESP_WIFI_PASSWORD, jamais dans le code "
             f"(relire : « {S_SECRET} »)")
    need(re.search(r"\bCONFIG_ESP_WIFI_PASSWORD\b", code),
         f"le mot de passe doit être lu avec CONFIG_ESP_WIFI_PASSWORD (relire : « {S_SECRET} »)")
    need(IP not in nc, f"l'adresse {IP} est écrite en dur dans main.cpp : lisez celle de l'événement IP_EVENT_STA_GOT_IP "
         f"(relire : « {S_IP} »)")


def _s(ms: float) -> str:
    return f"{ms / 1000:g}".replace(".", ",") + " s"


def _expected_wait(k: int) -> int:
    """Attente après le k-ième échec de suite (k >= 1) : 1 s doublée, plafonnée à 8 s."""
    return min(FIRST_WAIT_MS << (k - 1), MAX_WAIT_MS)


def _ordinal(n: int) -> str:
    return "1re" if n == 1 else f"{n}e"


def _tries(trace: Trace) -> tuple[list[int], int | None]:
    """(instants des échecs, instant de sta_connected ou None)."""
    ev = trace.events("wifi")
    fails = [e["t_ms"] for e in ev if e["event"] == "sta_disconnected" and e.get("reason") in FAIL_REASONS]
    conns = [e["t_ms"] for e in ev if e["event"] == "sta_connected"]
    return fails, (conns[0] if conns else None)


def _waits(fails: list[int], conn: int | None) -> list[tuple[int, int]]:
    """[(k, attente en ms après le k-ième échec)] pour chaque tentative qui a suivi un échec."""
    out = []
    for i, t in enumerate(fails):
        nxt = fails[i + 1] - FAIL_MS if i + 1 < len(fails) else (conn - CONNECT_MS if conn is not None else None)
        if nxt is not None:
            out.append((i + 1, nxt - t))
    return out


def _common(trace: Trace, name: str) -> None:
    label = LABELS[name]
    reboots = trace.events("reboot")
    need(not reboots, f"{label} : la carte a redémarré à {_s(reboots[0]['t_ms'] if reboots else 0)} (esp_restart, watchdog ou "
         "ESP_ERROR_CHECK qui échoue) : rien dans ce TP ne doit redémarrer la carte, il faut abandonner proprement "
         f"(relire : « {S_GIVEUP} »)")
    ev = trace.events("wifi")
    need(ev, f"{label} : aucun événement Wi-Fi : le Wi-Fi n'a jamais démarré. esp_wifi_start a-t-elle été appelée, et "
         "esp_wifi_init a-t-elle réussi (la NVS doit être initialisée d'abord, puis esp_netif_init et "
         f"esp_event_loop_create_default) ? (relire : « {S_NVS} » puis « {S_INIT} »)")
    need(any(e["event"] == "sta_start" for e in ev),
         f"{label} : esp_wifi_start n'a jamais produit WIFI_EVENT_STA_START : le Wi-Fi est-il démarré en mode station "
         f"(esp_wifi_set_mode(WIFI_MODE_STA) puis esp_wifi_start) ? (relire : « {S_INIT} »)")
    fails, conn = _tries(trace)
    need(fails or conn is not None,
         f"{label} : le Wi-Fi a démarré (STA_START) mais aucune tentative de connexion n'a eu lieu : appelez esp_wifi_connect() "
         "quand WIFI_EVENT_STA_START arrive. Le gestionnaire est-il enregistré pour WIFI_EVENT, et AVANT esp_wifi_start ? "
         f"(relire : « {S_EVENTS} »)")


def _check_waits(trace: Trace, name: str) -> None:
    label = LABELS[name]
    fails, conn = _tries(trace)
    for k, w in _waits(fails, conn):
        exp = _expected_wait(k)
        need(exp - WAIT_UNDER_MS <= w <= exp + WAIT_OVER_MS,
             f"{label} : attente de {_s(w)} entre l'échec n°{k} (à {_s(fails[k - 1])}) et la tentative suivante : il en faut "
             f"{_s(exp)} (1 s doublée à chaque échec, plafonnée à 8 s ; tolérance de {WAIT_UNDER_MS} ms de moins à "
             f"{WAIT_OVER_MS} ms de plus) (relire : « {S_BACKOFF} »)")


def _check_a(trace: Trace) -> None:
    label = LABELS["a"]
    fails, conn = _tries(trace)
    _check_waits(trace, "a")  # d'abord les attentes : une attente trop longue fait aussi manquer la connexion
    need(conn is not None,
         f"{label} : jamais connecté : {len(fails)} échec(s) (dernier à {_s(fails[-1])}), puis plus aucune tentative. La box "
         f"accepte la 4e tentative : on n'abandonne qu'après {MAX_TRIES} échecs de suite, et il faut rappeler "
         f"esp_wifi_connect() après chaque échec (relire : « {S_GIVEUP} »)")
    need(len(fails) == 3, f"{label} : {len(fails)} échecs avant la connexion au lieu de 3 : le programme a-t-il lancé des "
         f"tentatives en trop ? (relire : « {S_BACKOFF} »)")
    got = trace.events("wifi", event="got_ip")
    need(got, f"{label} : connecté mais l'adresse IP n'est jamais arrivée : esp_netif_create_default_wifi_sta doit être appelée "
         f"avant esp_wifi_init pour que l'interface demande une adresse (relire : « {S_STACK} »)")
    t_ip = got[0]["t_ms"]
    ip_logs = [e for e in trace.logs(tag=TAG, level="I") if e["msg"] == IP_MSG]
    near = [e["msg"] for e in trace.logs() if IP in e["msg"] or "IP" in e["msg"]]
    need(ip_logs, f"{label} : l'adresse obtenue à {_s(t_ip)} n'est pas journalisée : il faut un ESP_LOGI de tag « {TAG} » au "
         f"format exact « {IP_MSG} » (IP_EVENT_STA_GOT_IP est-il enregistré ?)"
         + (f" ; message trouvé : « {near[0]} »" if near else "") + f" (relire : « {S_IP} »)")
    need(len(ip_logs) == 1, f"{label} : {len(ip_logs)} lignes « {IP_MSG} » au lieu d'une : on journalise l'adresse une fois, "
         f"quand elle arrive (relire : « {S_IP} »)")
    need(ip_logs[0]["t_ms"] >= t_ip, f"{label} : l'adresse est journalisée à {_s(ip_logs[0]['t_ms'])}, avant d'être obtenue "
         f"({_s(t_ip)}) : la ligne se trouve dans la réaction à IP_EVENT_STA_GOT_IP (relire : « {S_IP} »)")
    errors = trace.logs(tag=TAG, level="E")
    need(not errors, f"{label} : un ESP_LOGE de tag « {TAG} » à {_s(errors[0]['t_ms'] if errors else 0)} (« "
         f"{errors[0]['msg'] if errors else ''} ») alors que la connexion réussit : un échec intermédiaire se journalise "
         f"avec ESP_LOGW ou ESP_LOGI, ESP_LOGE est réservé à l'abandon (relire : « {S_GIVEUP} »)")


def _check_b(trace: Trace) -> None:
    label = LABELS["b"]
    fails, conn = _tries(trace)
    need(conn is None and not trace.events("wifi", event="got_ip"),
         f"{label} : connecté alors que le réseau n'existe pas (erreur interne du TP)")
    n = len(fails)
    need(n >= MAX_TRIES, f"{label} : seulement {n} tentative(s) : il en faut {MAX_TRIES} avant d'abandonner (dernier échec à "
         f"{_s(fails[-1])}) (relire : « {S_GIVEUP} »)")
    need(n == MAX_TRIES, f"{label} : {n} tentatives en {_s(MAX_MS['b'])} au lieu de {MAX_TRIES} : après le {_ordinal(MAX_TRIES)} "
         "échec il faut abandonner et ne plus jamais rappeler esp_wifi_connect() (relire : « "
         f"{S_GIVEUP} »)")
    _check_waits(trace, "b")
    errors = trace.logs(tag=TAG, level="E")
    need(errors, f"{label} : aucune ligne d'erreur après l'abandon : il faut un ESP_LOGE de tag « {TAG} » qui dit que l'on "
         f"abandonne (relire : « {S_GIVEUP} »)")
    need(len(errors) == 1, f"{label} : {len(errors)} lignes ESP_LOGE de tag « {TAG} » au lieu d'une : les échecs intermédiaires "
         f"se journalisent avec ESP_LOGW ou ESP_LOGI, une seule ligne d'erreur pour l'abandon (relire : « {S_GIVEUP} »)")
    need(errors[0]["t_ms"] >= fails[-1], f"{label} : la ligne d'erreur est écrite à {_s(errors[0]['t_ms'])}, avant le "
         f"{_ordinal(MAX_TRIES)} échec ({_s(fails[-1])}) : on abandonne après le {_ordinal(MAX_TRIES)} échec "
         f"(relire : « {S_GIVEUP} »)")


def verify(traces: dict, source: str) -> None:
    _static(source)
    for name in ("a", "b"):
        _common(traces[name], name)
        (_check_a if name == "a" else _check_b)(traces[name])
