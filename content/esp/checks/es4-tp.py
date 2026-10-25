"""TP es4 : lire un capteur analogique sur l'ADC1 (canal 6, GPIO 34), le convertir en pourcentage selon
l'étalonnage (0 % = 0,5 V, 100 % = 3,0 V) en moyennant 8 échantillons, et journaliser `level=NN%` chaque seconde."""
import re

from esp_trace import Trace, need

CHANNEL = 6  # ADC_CHANNEL_6 de l'ADC1 = GPIO 34
TAG = "niveau"
VREF_MV = 3300.0  # plage 0..3,3 V du simulateur : raw = V / 3,3 * 4095
RAW_MAX = 4095
LOW_MV, HIGH_MV = 500.0, 3000.0  # 0 % et 100 %
TOLERANCE = 2.0  # points de pourcentage
PERIOD_MS = 1000
PERIOD_TOLERANCE_MS = 50
MIN_READS = 8
MIN_INSTANTS = 4  # lectures à au moins 4 instants différents entre deux journaux : sinon, pas de pause entre elles
MIN_LOGS = 19

# Rampe bruitée : la tension du capteur monte linéairement de 0,35 V à 3,15 V en 20 s (le niveau vrai passe
# de -6 % à 106 % : les deux extrémités sont saturées). Un point toutes les 10 ms ; le bruit est une suite
# pseudo-aléatoire fixe (générateur congruentiel linéaire à graine fixe, donc la même à chaque exécution)
# d'amplitude ±NOISE_RAW, soit ±2,4 points. Une mesure isolée sort de la tolérance, la moyenne de 8 mesures
# prises à 10 ms d'intervalle (bruits indépendants, un point par 10 ms) reste à environ 1 point.
RAMP_MS = 20000
START_MV, END_MV = 350.0, 3150.0
STEP_MS = 10
NOISE_RAW = 75
SEED = 20251025
MAX_MS = 20500


def _noise():
    x = SEED
    while True:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        yield (x >> 8) % (2 * NOISE_RAW + 1) - NOISE_RAW


def true_raw(t_ms: float) -> float:
    """Valeur brute sans bruit à l'instant t (rampe linéaire, constante après RAMP_MS)."""
    mv = START_MV + (END_MV - START_MV) * min(max(t_ms, 0), RAMP_MS) / RAMP_MS
    return mv * RAW_MAX / VREF_MV


def true_level(t_ms: float) -> float:
    """Niveau vrai en % à l'instant t : la tension sans bruit, passée dans l'étalonnage, bornée à 0..100."""
    mv = true_raw(t_ms) * VREF_MV / RAW_MAX
    return min(max((mv - LOW_MV) * 100.0 / (HIGH_MV - LOW_MV), 0.0), 100.0)


# Aux instants où une lecture unique est la plus probable (début de chaque seconde : sans pause, ou une seule
# lecture ; 70 ms plus tard : dernière des 8 lectures), le bruit vaut ±FORCED_RAW (+ puis -, la moyenne de 8 n'en
# est pas gênée) : une mesure isolée à ces instants sort donc de la tolérance (2,9 points, 2,4 après arrondi).
FORCED_RAW = 90
_n = _noise()


def _noise_at(t: int) -> int:
    n = next(_n)  # toujours tiré, pour que le reste de la suite ne dépende pas des instants forcés
    if t % 1000 == 0:
        return FORCED_RAW
    if t % 1000 == 70:
        return -FORCED_RAW
    return n


SCENARIO = {"adc": [
    {"t_ms": t, "channel": CHANNEL, "raw": min(max(round(true_raw(t)) + _noise_at(t), 0), RAW_MAX)}
    for t in range(0, RAMP_MS + 1, STEP_MS)]}

LEVEL = re.compile(r"level=(\d{1,3})%")


def _cause(values: list[tuple[int, int]]) -> str:
    """Nomme la cause probable d'un écart : une formule fautive classique, rejouée sur la valeur sans bruit,
    doit coller à TOUS les niveaux journalisés (à 3 points près), sinon on soupçonne la mesure unique bruitée."""
    def matches(formula) -> bool:
        return all(abs(got - formula(true_raw(t))) <= 3 for t, got in values)

    def level(mv: float, top: float) -> float:
        return min(max((mv - LOW_MV) * 100.0 / (top - LOW_MV), 0.0), 100.0)

    if matches(lambda raw: raw * 100.0 / RAW_MAX):
        return (" : cela correspond à une simple division par 4095, sans l'étalonnage (0 % à 0,5 V, 100 % à 3,0 V) "
                "(relire : « L'étalonnage : du brut au pourcentage »)")
    if matches(lambda raw: level(raw * VREF_MV / RAW_MAX, VREF_MV)):
        return (" : cela correspond à une échelle de 3,3 V au lieu de 3,0 V pour 100 % (le haut de l'échelle est 3,0 V) "
                "(relire : « L'étalonnage : du brut au pourcentage »)")
    return (" : le niveau saute d'une seconde à l'autre autour de la bonne valeur, signe d'une mesure unique bruitée au "
            "lieu de la moyenne de 8 échantillons (relire : « Le bruit et la moyenne de 8 échantillons »)")


def verify(trace: Trace, source: str) -> None:
    reads = trace.events("adc_read")
    mine = [e for e in reads if e["channel"] == CHANNEL]
    others = sorted({e["channel"] for e in reads} - {CHANNEL})
    need(not (reads and not mine),
         f"lectures sur le canal {others[0] if others else '?'} au lieu du canal {CHANNEL} : le capteur est branché sur ADC_CHANNEL_{CHANNEL} "
         "(GPIO 34), de l'ADC1 (relire : « Les quatre étapes de l'API oneshot »)")
    need(mine, f"aucune lecture réussie du canal {CHANNEL} : adc_oneshot_read a échoué ou n'a jamais été appelée. "
         "Le canal doit d'abord être configuré avec adc_oneshot_config_channel, après adc_oneshot_new_unit "
         "(relire : « Les quatre étapes de l'API oneshot »)")

    logs = [e for e in trace.logs(tag=TAG, level="I") if LEVEL.fullmatch(e["msg"])]
    need(logs, f"aucun journal level=NN% : il faut un ESP_LOGI de tag « {TAG} » au format exact level=NN% "
         "(par exemple level=42%) (relire : « Le programme du TP en un coup d'œil »)")
    times = [e["t_ms"] for e in logs]
    for a, b in zip(times, times[1:]):
        need(abs(b - a - PERIOD_MS) <= PERIOD_TOLERANCE_MS,
             f"journaux espacés de {b - a} ms (à {a} ms puis {b} ms) : il en faut un toutes les {PERIOD_MS} ms, à "
             f"{PERIOD_TOLERANCE_MS} ms près (relire : « Pourquoi une mesure par seconde ne suffit pas »)")
    need(len(logs) >= MIN_LOGS, f"seulement {len(logs)} journaux level=NN% en {MAX_MS} ms : il en faut au moins {MIN_LOGS}, "
         "un par seconde (relire : « Le programme du TP en un coup d'œil »)")

    # Entre deux journaux (depuis le début pour le premier), il faut au moins MIN_READS lectures : la moyenne
    # est calculée sur des lectures réelles d'adc_oneshot_read.
    previous = -1
    for t in times:
        n = sum(1 for e in mine if previous < e["t_ms"] <= t)
        need(n >= MIN_READS, f"seulement {n} lecture(s) adc_oneshot_read avant le journal de {t} ms : il en faut au moins "
             f"{MIN_READS} par seconde pour moyenner le bruit (relire : « Le bruit et la moyenne de 8 échantillons »)")
        instants = {e["t_ms"] for e in mine if previous < e["t_ms"] <= t}
        need(len(instants) >= MIN_INSTANTS,
             f"les lectures avant le journal de {t} ms ont lieu à {len(instants)} instant(s) seulement : aucune pause "
             "(ou presque) entre elles, donc pas de vraie moyenne. Le temps du simulateur n'avance que pendant vTaskDelay : "
             "mettez vTaskDelay(pdMS_TO_TICKS(10)) après chaque lecture (relire : « Pourquoi 10 ms entre deux lectures ? »)")
        previous = t

    # Niveau attendu à chaque journal : true_level(t) au moment du journal. Les 8 mesures sont prises dans les
    # quelques dizaines de ms qui précèdent, la rampe bouge de moins d'un point sur ce laps de temps.
    for e in logs:
        t, got = e["t_ms"], int(LEVEL.fullmatch(e["msg"]).group(1))
        expected = true_level(t)
        need(abs(got - expected) <= TOLERANCE,
             f"à {t} ms, level={got}% au lieu de {expected:.0f}% attendu (écart de {abs(got - expected):.1f} points, "
             f"tolérance ± {TOLERANCE:.0f}){_cause([(x['t_ms'], int(LEVEL.fullmatch(x['msg']).group(1))) for x in logs])}")
