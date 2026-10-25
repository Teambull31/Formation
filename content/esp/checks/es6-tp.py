"""TP es6 : réguler le niveau d'une piscine avec une pompe sur le relais GPIO 5 (actif haut).

Le programme lit le niveau sur l'ADC1 canal 6 (étalonnage du TP 4 : brut 620 = 0 %, 3723 = 100 %), démarre la pompe
sous 60 %, l'arrête au-dessus de 80 %, et coupe la pompe avec une alarme (ESP_LOGE, tag « pool ») quand elle tourne
depuis 10 minutes sans que le niveau monte ou quand la valeur brute du capteur reste identique pendant 10 minutes.
Après une alarme, la pompe reste éteinte jusqu'au redémarrage de la carte (alarme verrouillée).

Quatre exécutions du même programme (SCENARIOS) :
  a : cycle normal de 2 h, capteur sain, évaporation. Niveau de départ 72 % (dans la zone 60-80 %), remplissage de
      2,5 points par minute (20 points en 8 min : le délai de 10 min laisse 2 min de marge), évaporation de
      0,4 point par minute quand la pompe est éteinte. Deux cycles complets (démarrage vers 30 min et vers 91 min), la
      pompe est éteinte à la fin (120 min : niveau d'environ 72 %).
  b : capteur bloqué à 40 % de 0 à 15 min (le niveau vrai est 40 % au départ, la pompe démarre, le niveau vrai monte
      pendant que le capteur ne bouge plus). Le niveau vrai revient sous 60 % vers 23 min, capteur de nouveau sain
      depuis 15 min : un programme qui n'a pas verrouillé son alarme redémarrerait la pompe, le scénario dure 30 min.
  c : capteur figé à 70 % toute la durée, pompe arrêtée (zone 60-80 %) : seule la détection de capteur figé peut
      lever l'alarme (le délai maximal de remplissage ne tourne pas, la pompe n'a jamais démarré).
  d : capteur sain mais pompe presque sans effet (débit de 0,03 point par minute : +0,3 point en 10 min, le niveau part
      de 50,1 %). La valeur brute change environ chaque minute (pas figée) : seul le délai maximal de remplissage peut lever
      l'alarme. Dans b, les deux protections se déclenchent en même temps ; c'est d qui isole le délai maximal. Un débit
      NUL ne conviendrait pas : le simulateur ne fait pas baisser le niveau pompe allumée, la valeur brute serait
      identique et la détection de capteur figé se déclencherait aussi. Le niveau de départ 50,1 % et le gain de 0,3
      point restent à l'écart d'une marche du pourcentage entier, que le programme tronque (50 -> 51 à 51,0 %) ou
      arrondisse (50 -> 51 à 50,5 %) : le gain de 1 point n'est jamais atteint par un effet d'arrondi.

Le niveau vrai n'est pas lu dans la trace : il est rejoué ici à partir des changements de niveau de la broche 5
(remplissage pompe allumée, évaporation sinon, bornes 0 et 100), avec les mêmes taux que le simulateur.

Tolérances, annoncées dans l'énoncé :
  - seuils à 1 point près : la pompe démarre au plus tard quand le niveau passe sous 60 %, elle peut démarrer
    jusqu'à 61 % ; elle s'arrête au plus tôt à 79 %, au plus tard 12 s après le passage de 81 % ;
  - réaction : 12 s (une mesure toutes les 10 s au plus, plus le temps de décider) ;
  - échantillonnage : au plus 10 s (0,5 s de marge) entre deux lectures du capteur, tant que le programme régule ;
  - délai maximal : coupure et alarme entre 9 min 30 s et 10 min 15 s après le démarrage de la pompe (b) ou
    après la première lecture (c) ;
  - une seule ligne d'alarme (ESP_LOGE, tag « pool ») : l'alarme est un état, on l'annonce en y entrant.
"""
from esp_trace import Trace, need

PIN = 5
CHANNEL = 6
RAW_0, RAW_100 = 620, 3723  # étalonnage du TP 4
LOW, HIGH = 60, 80
TOL = 1.0  # points de pourcentage
FILL_PER_MIN, LOSS_PER_MIN = 2.5, 0.4
REACT_MS = 12000
MAX_GAP_MS = 10500
WATCH_MIN_MS, WATCH_MAX_MS = 570000, 615000
OUTPUT_MODES = {"output", "input_output"}
TAG = "pool"


def _scenario(level0: int, stuck: list[dict], fill: float = FILL_PER_MIN) -> dict:
    tank = {"level_pct0": level0, "fill_pct_per_min": fill, "loss_pct_per_min": LOSS_PER_MIN, "relay_pin": PIN,
            "adc_channel": CHANNEL, "raw_at_0": RAW_0, "raw_at_100": RAW_100}
    if stuck:
        tank["stuck"] = stuck
    return {"plant": {"tank": tank}}


# Scenario a lasts 2 h: a program reading the sensor 16 times per second would write ~115 200 adc_read
# lines (~55 bytes each, ~6.3 MB). 12 MB keeps a margin; the driver still caps it hard (16 MB ceiling).
MAX_OUT = 12_000_000
LEVEL0 = {"a": 72, "b": 40, "c": 70, "d": 50.1}
MAX_MS = {"a": 7_200_500, "b": 1_800_500, "c": 720_500, "d": 900_500}
SCENARIOS = {
    "a": (_scenario(LEVEL0["a"], []), MAX_MS["a"]),
    "b": (_scenario(LEVEL0["b"], [{"from_ms": 0, "to_ms": 900_000}]), MAX_MS["b"]),
    "c": (_scenario(LEVEL0["c"], [{"from_ms": 0, "to_ms": 3_600_000}]), MAX_MS["c"]),
    "d": (_scenario(LEVEL0["d"], [], fill=0.03), MAX_MS["d"]),
}
LABELS = {"a": "scénario a (cycle normal sur 2 h)", "b": "scénario b (capteur bloqué à 40 % pendant 15 min)",
          "c": "scénario c (capteur figé à 70 %, pompe arrêtée)",
          "d": "scénario d (capteur sain, pompe sans effet sur le niveau)"}
# Texte propre à chaque exécution où la pompe doit être coupée par le délai maximal.
CUT_TEXT = {
    "b": ("le niveau lu est de 40 %", "le niveau lu est resté à 40 % pendant 10 min de pompe",
          "la pompe tourne depuis 10 min sans que le niveau monte"),
    "d": ("le niveau lu est de 50 %", "le niveau n'a gagné que 0,3 point en 10 min de pompe (la pompe ne remplit presque rien)",
          "la pompe tourne depuis 10 min sans que le niveau monte, même si le capteur répond et que sa valeur change"),
}

S_LOOP = "La boucle de régulation : lire, décider, agir, recommencer"
S_CALIB = "Du brut au pourcentage (l'étalonnage du TP 4)"
S_HYST = "L'hystérésis : deux seuils pour que le relais ne batte pas"
S_STATE = "L'état de la régulation : IDLE, FILLING, ALARM"
S_MAX = "Le délai maximal : surveiller le procédé, pas seulement le capteur"
S_FROZEN = "Le capteur figé"
S_SAFE = "L'état sûr : pompe éteinte au démarrage, sur alarme, à la fin"
S_PERIOD = "Choisir la période d'échantillonnage"
S_TIME = "Mesurer le temps avec esp_timer_get_time"


def _dur(ms: float) -> str:
    s = round(ms / 1000)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def _relay_changes(trace: Trace) -> list[tuple[int, int]]:
    """Changements réels du niveau de la broche 5 (départ à 0 : sortie non commandée) : [(t_ms, niveau)]."""
    out, level = [], 0
    for t, lv in trace.gpio_levels(PIN):
        if lv != level:
            out.append((t, lv))
            level = lv
    return out


def _segments(trace: Trace, level0: float, end_ms: int) -> list[tuple[int, int, float, float, int]]:
    """Niveau vrai rejoué : [(t0, t1, niveau en t0, niveau en t1, pompe allumée)] entre deux changements de la broche."""
    segs, t, level, on = [], 0, float(level0), 0
    for te, lv in [*_relay_changes(trace), (end_ms, None)]:
        te = min(te, end_ms)
        rate = FILL_PER_MIN if on else -LOSS_PER_MIN
        nxt = min(max(level + rate * (te - t) / 60000, 0.0), 100.0)
        segs.append((t, te, level, nxt, on))
        t, level = te, nxt
        if lv is not None:
            on = lv
    return segs


def _level_at(segs, t_ms: int) -> float:
    for t0, t1, l0, l1, _ in segs:
        if t0 <= t_ms <= t1:
            return l0 + (l1 - l0) * (t_ms - t0) / (t1 - t0) if t1 > t0 else l0
    return segs[-1][3]


def _time_beyond(seg, threshold: float, above: bool) -> tuple[float, float]:
    """(début, durée en ms) de la partie du segment où le niveau est au-dessus (above) ou au-dessous du seuil."""
    t0, t1, l0, l1, on = seg
    rate = (FILL_PER_MIN if on else -LOSS_PER_MIN) / 60000
    in0, in1 = ((l0 > threshold), (l1 > threshold)) if above else ((l0 < threshold), (l1 < threshold))
    if not in0 and not in1:
        return t0, 0.0
    cross = t0 + (threshold - l0) / rate if in0 != in1 else t0
    start = t0 if in0 else cross
    end = t1 if in1 else cross
    return start, max(end - start, 0.0)


def _alarms(trace: Trace) -> list[dict]:
    return trace.logs(tag=TAG, level="E")


def _common(trace: Trace, name: str) -> int:
    """Vérifications communes aux trois exécutions. Renvoie l'instant de la première lecture."""
    label = LABELS[name]
    reads = [e for e in trace.events("adc_read") if e["channel"] == CHANNEL]
    others = sorted({e["channel"] for e in trace.events("adc_read")} - {CHANNEL})
    need(reads, f"{label} : aucune lecture du canal {CHANNEL} de l'ADC1 (GPIO 34)"
         + (f", mais des lectures du canal {others[0]}" if others else "")
         + f" : le capteur est sur ADC_CHANNEL_{CHANNEL}, comme au TP 4 (relire : « {S_CALIB} »)")
    need(any(e["pin"] == PIN and e["mode"] in OUTPUT_MODES for e in trace.events("gpio_config")),
         f"{label} : la broche GPIO {PIN} de la pompe n'est pas configurée en sortie : il faut un gpio_config avec "
         f"mode = GPIO_MODE_OUTPUT pour la broche {PIN} (relire : « {S_SAFE} »)")
    first_read = min(e["t_ms"] for e in reads)
    sets = trace.gpio_levels(PIN)
    need(sets and sets[0][1] == 0 and sets[0][0] <= first_read,
         f"{label} : le premier gpio_set_level de la broche {PIN} "
         + (f"met la pompe en marche (niveau 1) à {sets[0][0]} ms" if sets and sets[0][1] == 1 else
            "n'a lieu qu'après la première lecture" if sets else "n'existe pas")
         + f" : au démarrage il faut mettre la pompe à l'état sûr, niveau 0 (éteinte), juste après gpio_config et avant la "
         f"première lecture (relire : « {S_SAFE} »)")
    # Échantillonnage : tant que le programme régule (jusqu'à l'alarme, ou la fin de l'exécution).
    alarms = _alarms(trace)
    horizon = alarms[0]["t_ms"] if alarms else MAX_MS[name]
    times = sorted({e["t_ms"] for e in reads if e["t_ms"] <= horizon})
    need(times[0] <= MAX_GAP_MS, f"{label} : première lecture à {_dur(times[0])} seulement (relire : « {S_PERIOD} »)")
    for a, b in zip(times, times[1:]):
        need(b - a <= MAX_GAP_MS, f"{label} : {_dur(b - a)} sans lire le capteur (de {_dur(a)} à {_dur(b)}) : une lecture "
             f"au moins toutes les 10 s, sinon la pompe déborde avant qu'on s'en aperçoive (relire : « {S_PERIOD} »)")
    need(horizon - times[-1] <= MAX_GAP_MS, f"{label} : plus aucune lecture après {_dur(times[-1])} alors que la régulation "
         f"devait continuer (relire : « {S_LOOP} »)")
    return first_read


def _end_off(trace: Trace, name: str) -> None:
    final = _relay_changes(trace)[-1][1] if _relay_changes(trace) else 0
    need(final == 0, f"{LABELS[name]} : la pompe est encore allumée à la fin de l'exécution : la régulation doit la laisser "
         f"éteinte (relire : « {S_SAFE} »)")


def _check_a(trace: Trace) -> None:
    label = LABELS["a"]
    alarms = _alarms(trace)
    need(not alarms, f"{label} : alarme à {_dur(alarms[0]['t_ms'] if alarms else 0)} (« {alarms[0]['msg'] if alarms else ''} ») "
         "alors que le capteur est sain et que le remplissage monte normalement : fausse alarme. Le minuteur du délai maximal "
         "doit repartir de zéro à chaque démarrage de la pompe et se contenter de 10 min SANS hausse du niveau "
         f"(relire : « {S_MAX} »)")
    segs = _segments(trace, LEVEL0["a"], MAX_MS["a"])
    for seg in segs:
        start, dur = _time_beyond(seg, HIGH + TOL, above=True)
        if seg[4]:
            need(dur <= REACT_MS, f"{label} : la pompe est restée allumée {_dur(dur)} avec un niveau de plus de {HIGH + TOL:.0f} % "
                 f"(jusqu'à {seg[3]:.0f} % à {_dur(seg[1])}) : elle doit s'arrêter au-dessus de {HIGH} %, sinon la piscine "
                 f"déborde (relire : « {S_HYST} »)")
    for t, lv in _relay_changes(trace):
        level = _level_at(segs, t)
        if lv == 1:
            need(level <= LOW + TOL, f"{label} : la pompe s'allume à {_dur(t)} alors que le niveau vrai est de {level:.0f} % "
                 + (f"(plus de {HIGH} % : débordement) " if level > HIGH - TOL else
                    f"(dans la zone entre {LOW} % et {HIGH} %) : elle ne démarre qu'en dessous de {LOW} %. Seuils inversés, "
                    "ou un seul seuil au milieu de la zone ? ")
                 + f"(relire : « {S_HYST} »)")
        else:
            need(level >= HIGH - TOL, f"{label} : la pompe s'éteint à {_dur(t)} alors que le niveau vrai est de seulement "
                 f"{level:.0f} % : elle doit tourner jusqu'à {HIGH} %, puis seulement s'éteindre. Un seul seuil fait battre "
                 f"le relais autour de la limite (relire : « {S_HYST} »)")
    for seg in segs:
        start, dur = _time_beyond(seg, LOW - TOL, above=False)
        if not seg[4]:
            need(dur <= REACT_MS, f"{label} : le niveau vrai est resté {_dur(dur)} sous {LOW - TOL:.0f} % sans que la pompe "
                 f"démarre (à partir de {_dur(start)}) : elle doit démarrer sous {LOW} % (relire : « {S_HYST} »)")
    need(any(lv == 1 for _, lv in _relay_changes(trace)),
         f"{label} : la pompe ne s'est jamais allumée alors que le niveau est passé sous {LOW} % (relire : « {S_HYST} »)")
    _end_off(trace, "a")


def _alarm_window(trace: Trace, name: str, t_ref: int, what: str) -> None:
    label = LABELS[name]
    alarms = _alarms(trace)
    need(alarms, f"{label} : aucune alarme : il faut un ESP_LOGE de tag « {TAG} » quand {what} (relire : « {S_MAX} »)")
    need(len(alarms) == 1, f"{label} : {len(alarms)} lignes d'alarme (ESP_LOGE, tag « {TAG} ») au lieu d'une : l'alarme est un "
         "état, on l'annonce une seule fois en y entrant, et pas à chaque mesure, sinon le journal se noie "
         f"(relire : « {S_STATE} »)")
    t = alarms[0]["t_ms"]
    lo, hi = t_ref + WATCH_MIN_MS, t_ref + WATCH_MAX_MS
    need(lo <= t <= hi, f"{label} : alarme à {_dur(t)}, attendue entre {_dur(lo)} et {_dur(hi)} (10 min après "
         f"{'la première lecture' if name == 'c' else 'le démarrage de la pompe'}) (relire : « {S_FROZEN if name == 'c' else S_MAX} »)")


def _check_cut(trace: Trace, name: str) -> None:
    label = LABELS[name]
    start, stay, what = CUT_TEXT[name]
    changes = _relay_changes(trace)
    need(changes and changes[0][1] == 1 and changes[0][0] <= REACT_MS,
         f"{label} : la pompe n'a pas démarré alors que {start} (sous {LOW} %) (relire : « {S_HYST} »)")
    t_on = changes[0][0]
    offs = [t for t, lv in changes if lv == 0 and t > t_on]
    need(offs, f"{label} : la pompe tourne encore à {_dur(MAX_MS[name])} : {stay}, il fallait la couper et lever "
         f"l'alarme (délai maximal de remplissage) (relire : « {S_MAX} »)")
    cut = offs[0]
    need(cut >= t_on + WATCH_MIN_MS, f"{label} : pompe coupée à {_dur(cut)}, seulement {_dur(cut - t_on)} après son démarrage : "
         f"le délai maximal est de 10 min sans hausse du niveau (relire : « {S_MAX} »)")
    need(cut <= t_on + WATCH_MAX_MS, f"{label} : pompe coupée à {_dur(cut)}, {_dur(cut - t_on)} après son démarrage : "
         "au plus 10 min 15 s sont acceptées. Le délai maximal de 10 min n'a pas joué son rôle (absent, trop long, ou mal "
         "mesuré : mesurez le temps avec esp_timer_get_time, sans compter des tours de boucle) "
         f"(relire : « {S_MAX} »)")
    _alarm_window(trace, name, t_on, what)
    again = [t for t, lv in changes if lv == 1 and t > cut]
    need(not again, f"{label} : la pompe est rallumée à {_dur(again[0] if again else 0)}, après l'alarme : une alarme est "
         "verrouillée, la pompe reste éteinte jusqu'au redémarrage de la carte, même quand le capteur répond de nouveau "
         f"(relire : « {S_STATE} »)")
    _end_off(trace, name)


def _check_c(trace: Trace, first_read: int) -> None:
    label = LABELS["c"]
    ons = [t for t, lv in _relay_changes(trace) if lv == 1]
    need(not ons, f"{label} : la pompe s'allume à {_dur(ons[0] if ons else 0)} alors que le niveau lu (70 %) est entre "
         f"{LOW} % et {HIGH} % : elle doit rester éteinte (relire : « {S_HYST} »)")
    _alarm_window(trace, "c", first_read, "la valeur brute du capteur reste identique pendant 10 min")
    _end_off(trace, "c")


def verify(traces: dict, source: str) -> None:
    # Chaque exécution est jugée en entier avant la suivante : le premier message nomme le premier scénario en faute.
    _common(traces["a"], "a")
    _check_a(traces["a"])
    _common(traces["b"], "b")
    _check_cut(traces["b"], "b")
    _check_c(traces["c"], _common(traces["c"], "c"))
    _common(traces["d"], "d")
    _check_cut(traces["d"], "d")
