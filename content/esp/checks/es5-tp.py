"""TP es5 : lire une température sur le bus I2C (adresse 0x44, 2 octets), commander un relais (GPIO 5) allumé
au-dessus de 28,0 °C, garder le dernier état et journaliser UNE erreur par panne quand le capteur ne répond plus."""
from esp_trace import Trace, need

RELAY_PIN = 5
ADDR = 0x44
PERIOD_MS = 5000
PERIOD_TOLERANCE_MS = 100
MIN_READS = 15
THRESHOLD_TENTHS = 280  # 28,0 °C : le relais est allumé strictement au-dessus
MAX_MS = 80500
OUTPUT_MODES = {"output", "input_output"}

# Capteur simulé : 2 octets, entier non signé de 16 bits, poids fort d'abord, valant (température + 40,0 °C) × 10.
# Température vraie aux instants multiples de 5 s (en °C) ; elle monte, lentement près du seuil : 27,9 puis 28,0 pile
# (égalité : relais éteint) puis 28,1. Entre deux de ces instants, la valeur reste celle du dernier instant.
TEMPS_C = {0: 20.0, 5: 21.0, 10: 22.0, 15: 23.0, 20: 24.0, 25: 25.0, 30: 26.0, 35: 27.9, 40: 28.0, 45: 28.1,
           50: 29.0, 55: 30.0, 60: 31.0, 65: 32.0, 70: 33.0, 75: 34.0, 80: 35.0}
# Pannes (capteur muet) : une courte, puis une de 12 s en pleine montée, alors que le relais est déjà allumé
# depuis 45 s. Avec une mesure toutes les 5 s, la longue contient 2 ou 3 mesures, la courte une.
GLITCH = {"from_ms": 12000, "to_ms": 17000}
NACK = {"from_ms": 47000, "to_ms": 59000}


def raw_of(temp_c: float) -> int:
    return round((temp_c + 40.0) * 10)


def raw_at(t_ms: int) -> int:
    """Valeur brute (en dixièmes, avec décalage de 40 °C) que le capteur renvoie à l'instant t."""
    latest = max(s for s in TEMPS_C if s * 1000 <= t_ms)
    return raw_of(TEMPS_C[latest])


def tenths_at(t_ms: int) -> int:
    return raw_at(t_ms) - 400


SCENARIO = {"i2c": {"0x44": {
    "series": [{"t_ms": s * 1000, "bytes": [raw_of(c) >> 8, raw_of(c) & 0xFF]} for s, c in TEMPS_C.items()],
    "nack": [GLITCH, NACK]}}}

CONVENTION = "relais actif haut : niveau 1 = relais allumé"


def _fmt(tenths: int) -> str:
    return f"{tenths / 10:.1f}".replace(".", ",")


def _relay_level(trace: Trace, t_ms: int) -> int:
    level = 0
    for t, lv in trace.gpio_levels(RELAY_PIN):
        if t <= t_ms:
            level = lv
    return level


def _instants(trace: Trace) -> list[tuple[int, bool]]:
    """Un transfert vers le capteur par instant : (t_ms, réussi), le dernier transfert de l'instant compte."""
    out: dict[int, bool] = {}
    for e in trace.events("i2c_xfer"):
        out[e["t_ms"]] = e["ok"]
    return sorted(out.items())


def verify(trace: Trace, source: str) -> None:
    xfers = trace.events("i2c_xfer")
    need(xfers, "aucun transfert I2C : le programme n'a jamais lu le capteur. Il faut créer le bus avec "
         "i2c_new_master_bus, ajouter le capteur avec i2c_master_bus_add_device, puis lire avec i2c_master_receive "
         "(relire : « Les étapes du pilote I2C maître »)")
    others = sorted({e["addr"] for e in xfers} - {ADDR})
    need(not others, f"transferts vers l'adresse 0x{others[0]:02X} au lieu de 0x{ADDR:02X} : le capteur répond à l'adresse "
         f"0x{ADDR:02X} (7 bits, sans le bit lecture/écriture) (relire : « Le bus I2C : adresse, ACK et NACK »)"
         if others else "")
    need(any(e["pin"] == RELAY_PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"la broche GPIO {RELAY_PIN} du relais n'est pas configurée en sortie : il faut un gpio_config avec "
         f"mode = GPIO_MODE_OUTPUT pour la broche {RELAY_PIN} (relire : « Le relais sur la GPIO 5 »)")

    inst = _instants(trace)
    for (a, _), (b, _) in zip(inst, inst[1:]):
        need(abs(b - a - PERIOD_MS) <= PERIOD_TOLERANCE_MS,
             f"lectures du capteur espacées de {b - a} ms (à {a} ms puis {b} ms) : il en faut une toutes les "
             f"{PERIOD_MS} ms, à {PERIOD_TOLERANCE_MS} ms près, que la lecture réussisse ou non "
             "(relire : « Le programme du TP en un coup d'œil »)")
    need(len(inst) >= MIN_READS, f"seulement {len(inst)} lectures du capteur en {MAX_MS} ms : il en faut au moins "
         f"{MIN_READS}, une toutes les {PERIOD_MS} ms (relire : « Le programme du TP en un coup d'œil »)")

    # État attendu du relais après chaque lecture : allumé si la DERNIÈRE température valide dépasse 28,0 °C
    # (strictement), inchangé quand la lecture échoue. Il est observé juste avant la lecture suivante.
    expected, last_good, wrong = 0, None, []
    for i, (t, ok) in enumerate(inst):
        if ok:
            last_good = tenths_at(t)
            expected = int(last_good > THRESHOLD_TENTHS)
        end = inst[i + 1][0] - 1 if i + 1 < len(inst) else MAX_MS
        got = _relay_level(trace, end)
        if got != expected:
            wrong.append((t, ok, expected, got, last_good))
    good_count = sum(1 for _, ok in inst if ok)
    if wrong:
        t, ok, expected, got, temp = wrong[0]
        if not ok:
            raise_error = (
                f"à {t} ms la lecture du capteur a échoué et, pendant la panne du capteur, le relais est passé à "
                f"{'allumé' if got else 'éteint'} alors qu'il devait garder son dernier état ({'allumé' if expected else 'éteint'}) : "
                "une lecture ratée ne dit rien de la température (relire : « Garder le dernier état quand la lecture échoue »)")
        elif sum(1 for w in wrong if w[1]) == good_count:
            raise_error = (f"le relais est toujours à l'opposé de l'état attendu (dès {t} ms) : {CONVENTION} "
                           "(relire : « Le relais sur la GPIO 5 »)")
        elif got and temp == THRESHOLD_TENTHS:
            raise_error = (f"à {t} ms la température vaut exactement 28,0 °C et le relais est allumé : il doit rester éteint "
                           "pile à 28,0 °C, il ne s'allume que strictement au-dessus de 28,0 "
                           "(relire : « Le seuil de 28,0 °C et l'hystérésis »)")
        elif got and temp <= 250:
            raise_error = (f"à {t} ms la température vaut {_fmt(temp)} °C et le relais est déjà allumé, loin du seuil de 28,0 °C : "
                           "la conversion fausse des 2 octets (poids fort et poids faible inversés ? décalage de 40,0 °C oublié ?) "
                           "est la cause probable (relire : « Décoder les 2 octets du capteur »)")
        elif got:
            raise_error = (f"à {t} ms la température vaut {_fmt(temp)} °C et le relais est allumé : seuil trop bas, il ne doit "
                           "s'allumer qu'au-dessus de 28,0 °C (relire : « Le seuil de 28,0 °C et l'hystérésis »)")
        else:
            raise_error = (f"à {t} ms la température vaut {_fmt(temp)} °C (au-dessus de 28,0 °C) et le relais est éteint : "
                           "seuil trop haut ou comparaison à l'envers (relire : « Le seuil de 28,0 °C et l'hystérésis »)")
        need(False, raise_error)

    # Journaux d'erreur : exactement un (niveau E ou W) entre le premier échec d'une panne et la première lecture réussie
    # qui suit. Une panne = des lectures ratées consécutives.
    problems = [(t, ok) for t, ok in inst]
    i = 0
    while i < len(problems):
        if problems[i][1]:
            i += 1
            continue
        start = problems[i][0]
        j = i
        while j < len(problems) and not problems[j][1]:
            j += 1
        stop = problems[j][0] if j < len(problems) else MAX_MS + 1
        n_fail = j - i
        n = sum(1 for e in trace.logs() if e["level"] in ("E", "W") and start <= e["t_ms"] < stop)
        need(n >= 1, f"aucun journal d'erreur pendant la panne du capteur (lectures ratées de {start} ms à {inst[j - 1][0]} ms) : "
             "il faut un ESP_LOGE (ou ESP_LOGW) qui dit pourquoi la lecture a échoué "
             "(relire : « Une erreur par panne, pas une par lecture »)")
        need(n <= 1, f"{n} journaux d'erreur pendant la même panne ({n_fail} lectures ratées de {start} ms à "
             f"{inst[j - 1][0]} ms) : un seul par panne suffit, sinon le journal se noie. Retenez qu'une panne est en cours "
             "avec une variable, et réarmez-la quand une lecture réussit "
             "(relire : « Une erreur par panne, pas une par lecture »)")
        i = j
