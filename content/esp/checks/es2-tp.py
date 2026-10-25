"""TP es2 : le bouton du GPIO 4 inverse la LED du GPIO 2, une seule fois par appui, malgré les rebonds."""
from esp_trace import Trace, need

LED = 2
BUTTON = 4
OUTPUT_MODES = {"output", "output_od", "input_output", "input_output_od"}
INPUT_MODES = {"input", "input_output", "input_output_od"}

# Trois appuis courts sur GPIO 4. Chaque appui : rebonds 0,1,0,1,0 (un niveau toutes les 10 ms, la
# résolution du simulateur), puis le bouton reste enfoncé (niveau 0) HOLD_MS, puis il est relâché (niveau 1).
# Au repos, la ligne vaut 1 grâce au pull-up. Les appuis 1 et 2 sont séparés de 400 ms ; sondés toutes les 500 ms,
# ils sont tous manqués ; une pause de 2 s après le premier appui fait manquer le deuxième.
PRESS_STARTS = [1130, 1530, 3570]
BOUNCE_STEPS = [(0, 0), (10, 1), (20, 0), (30, 1), (40, 0)]
HOLD_MS = 80
RELEASE_AT = BOUNCE_STEPS[-1][0] + HOLD_MS
MAX_MS = 5000
WINDOW_MS = 60  # un changement doit tomber dans les 60 ms qui suivent le premier front stable

SCENARIO = {"gpio_in": sorted(
    [{"t_ms": t + dt, "pin": BUTTON, "level": level} for t in PRESS_STARTS for dt, level in BOUNCE_STEPS]
    + [{"t_ms": t + RELEASE_AT, "pin": BUTTON, "level": 1} for t in PRESS_STARTS],
    key=lambda e: e["t_ms"])}


def stable_edges() -> list[int]:
    """Premier front stable de chaque appui, lu dans le scénario : l'instant où commence le niveau 0
    qui dure au moins HOLD_MS (le dernier 0 des rebonds, dont l'appui n'est plus interrompu)."""
    ev = SCENARIO["gpio_in"]
    return [a["t_ms"] for a, b in zip(ev, ev[1:]) if a["level"] == 0 and b["level"] == 1 and b["t_ms"] - a["t_ms"] >= HOLD_MS]


def verify(trace: Trace, source: str) -> None:
    out_pins = {e["pin"] for e in trace.events("gpio_config") if e["mode"] in OUTPUT_MODES}
    others = f" (broches configurées en sortie : {', '.join(map(str, sorted(out_pins)))})" if out_pins else ""
    need(LED in out_pins, f"GPIO 2 jamais configurée en sortie{others} (relire : « Rappel : configurer la LED en sortie »)")

    btn = [e for e in trace.events("gpio_config", pin=BUTTON) if e["mode"] in INPUT_MODES]
    in_pins = sorted({e["pin"] for e in trace.events("gpio_config") if e["mode"] in INPUT_MODES})
    need(btn, "GPIO 4 jamais configurée en entrée"
         + (f" (broches configurées en entrée : {', '.join(map(str, in_pins))})" if in_pins else "")
         + " (relire : « Configurer le bouton en entrée »)")
    need(any(e.get("pull_up") is True for e in btn),
         "GPIO 4 est une entrée sans pull-up : sans résistance de rappel, la ligne du bouton flotte et "
         "le programme lit 0 en permanence, comme si le bouton était toujours enfoncé "
         "(relire : « La résistance de pull-up et la logique inversée »)")

    # La LED est éteinte au départ : un changement = un niveau écrit différent du précédent.
    changes: list[int] = []
    previous = 0
    for t, level in trace.gpio_levels(LED):
        if level != previous:
            changes.append(t)
        previous = level

    edges = stable_edges()
    ends = PRESS_STARTS[1:] + [MAX_MS + 1]
    before = [t for t in changes if t < PRESS_STARTS[0]]
    need(not before, f"la LED a changé à {before[0] if before else 0} ms, avant tout appui : le bouton au repos "
         "est lu à 1, un changement ne doit suivre qu'un appui (relire : « Front ou niveau : réagir une seule fois »)")
    for n, (start, end, edge) in enumerate(zip(PRESS_STARTS, ends, edges), 1):
        mine = [t for t in changes if start <= t < end]
        span = f"de {start} à {start + RELEASE_AT} ms"
        need(mine, f"l'appui n°{n} ({span}) n'a provoqué aucun changement de la LED : appui manqué, "
             "le bouton est lu trop rarement ou l'anti-rebond exige une stabilité plus longue que l'appui "
             "(relire : « Sonder le bouton à intervalle régulier »)")
        need(len(mine) == 1, f"plus d'un changement pour l'appui n°{n} ({span}) : {len(mine)} changements de la LED, "
             "aux instants " + ", ".join(f"{t} ms" for t in mine) + ". Ce sont les rebonds pris pour des appuis, "
             "ou le relâchement compté comme un appui (relire : « L'anti-rebond par durée de stabilité »)")
        t = mine[0]
        need(t >= edge, f"la LED a changé à {t} ms pour l'appui n°{n}, avant que le signal soit stable (à {edge} ms) : "
             "le programme réagit à un rebond (relire : « L'anti-rebond par durée de stabilité »)")
        need(t <= edge + WINDOW_MS, f"la LED a changé à {t} ms pour l'appui n°{n}, {t - edge} ms après le premier front stable "
             f"({edge} ms) : il en faut au plus {WINDOW_MS} (relire : « L'anti-rebond par durée de stabilité »)")
    need(len(changes) == len(PRESS_STARTS), f"la LED a changé {len(changes)} fois au lieu de {len(PRESS_STARTS)} "
         "(relire : « Front ou niveau : réagir une seule fois »)")
