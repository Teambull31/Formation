"""TP es1 : faire clignoter la LED du GPIO 2 (500 ms allumée, 500 ms éteinte) avec un journal « blink » à chaque changement."""
from esp_trace import Trace, need

SCENARIO: dict = {}
MAX_MS = 10_000

PIN = 2
PERIOD_MS = 500
TOLERANCE_MS = 10
MIN_CHANGES = 10
OUTPUT_MODES = {"output", "output_od", "input_output", "input_output_od"}


def verify(trace: Trace, source: str) -> None:
    configured = {e["pin"] for e in trace.events("gpio_config") if e["mode"] in OUTPUT_MODES}
    others = f" (broches configurées en sortie : {', '.join(map(str, sorted(configured)))})" if configured else ""
    need(PIN in configured, f"GPIO 2 jamais configurée en sortie{others} (relire : « Configurer une broche avec gpio_config »)")

    writes = trace.gpio_levels(PIN)
    written = sorted({e["pin"] for e in trace.events("gpio_set")})
    need(writes, "aucune écriture sur GPIO 2 : gpio_set_level n'a jamais été appelée sur cette broche"
         + (f" (broches écrites : {', '.join(map(str, written))})" if written else "")
         + " (relire : « Allumer et éteindre avec gpio_set_level »)")
    need(writes[0][1] == 1, "le premier niveau écrit sur GPIO 2 est 0 : la LED doit d'abord être allumée (niveau 1) "
         "(relire : « Allumer et éteindre avec gpio_set_level »)")

    # Un changement = un niveau écrit différent du précédent (la LED est éteinte au départ).
    changes: list[tuple[int, int]] = []
    previous = 0
    for t, level in writes:
        if level != previous:
            changes.append((t, level))
        previous = level
    need(len(changes) > 1, f"le niveau de GPIO 2 n'a jamais changé après le premier : la LED est restée "
         f"{'allumée' if previous else 'éteinte'} pendant {MAX_MS // 1000} s "
         "(relire : « Allumer et éteindre avec gpio_set_level »)")

    gaps = [b[0] - a[0] for a, b in zip(changes, changes[1:])]
    bad = [g for g in gaps if abs(g - PERIOD_MS) > TOLERANCE_MS]
    need(not bad, f"période observée de {bad[0] if bad else 0} ms entre deux changements de la LED au lieu de {PERIOD_MS} ms "
         "(relire : « Attendre sans bloquer avec vTaskDelay »)")
    need(len(changes) >= MIN_CHANGES, f"la LED n'a changé que {len(changes)} fois en {MAX_MS // 1000} s, il en faut au moins "
         f"{MIN_CHANGES} : la boucle s'arrête-t-elle trop tôt ? (relire : « La boucle infinie »)")

    blink = trace.logs(tag="blink")
    info = [e["t_ms"] for e in blink if e["level"] == "I"]
    if not blink:
        tags = sorted({e["tag"] for e in trace.logs()})
        need(not tags, "les journaux ont le tag " + ", ".join(f"« {t} »" for t in tags) + " au lieu de « blink » : "
             "le premier argument de ESP_LOGI est le tag (relire : « Écrire dans le journal avec ESP_LOGI »)")
        need(False, "aucun journal de tag « blink » : ajoutez ESP_LOGI(TAG, ...) à chaque changement de la LED "
             "(relire : « Écrire dans le journal avec ESP_LOGI »)")
    used = ", ".join(sorted({"ESP_LOG" + e["level"] for e in blink}))
    need(info, f"les journaux de tag « blink » sont écrits avec {used} et non ESP_LOGI "
         "(relire : « Écrire dans le journal avec ESP_LOGI »)")
    missing = [t for t, _ in changes if not any(abs(t - m) <= TOLERANCE_MS for m in info)]
    need(not missing, f"il manque un ESP_LOGI de tag « blink » au changement de la LED à {missing[0] if missing else 0} ms : "
         "un journal par changement, allumage comme extinction (relire : « Écrire dans le journal avec ESP_LOGI »)")
