"""TP es3 : une tâche sonde le bouton du GPIO 4 et poste chaque appui dans une file ; une autre tâche,
bloquée sur xQueueReceive(..., portMAX_DELAY), inverse la LED du GPIO 2 à chaque événement reçu."""
import importlib.util
from pathlib import Path

from esp_trace import Trace, need

# Même bouton et mêmes appuis (avec rebonds) que le TP es2 : le scénario et le calcul des fronts
# stables sont repris du contrôle es2, chargé par chemin (ce dossier est du contenu de confiance).
_spec = importlib.util.spec_from_file_location("esp_check_es2_tp_for_es3", Path(__file__).with_name("es2-tp.py"))
es2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es2)

LED, BUTTON = es2.LED, es2.BUTTON
SCENARIO = es2.SCENARIO
PRESS_STARTS, RELEASE_AT, WINDOW_MS = es2.PRESS_STARTS, es2.RELEASE_AT, es2.WINDOW_MS
MAX_MS = es2.MAX_MS
MIN_STACK = 2048  # octets (ESP-IDF compte la pile de xTaskCreate en octets, pas en mots)


def verify(trace: Trace, source: str) -> None:
    need(any(e["mode"] in es2.OUTPUT_MODES for e in trace.events("gpio_config", pin=LED)),
         "GPIO 2 jamais configurée en sortie : la LED se configure comme aux TP 1 et 2 "
         "(relire : « Le programme du TP en un coup d'œil »)")
    btn = [e for e in trace.events("gpio_config", pin=BUTTON) if e["mode"] in es2.INPUT_MODES]
    need(btn and any(e.get("pull_up") is True for e in btn),
         "GPIO 4 n'est pas configurée en entrée avec pull-up, comme au TP 2 "
         "(relire : « Le programme du TP en un coup d'œil »)")

    created = [e for e in trace.events("task_create") if "stack" in e]  # celles de xTaskCreate, sans app_main
    names = ", ".join(f"« {e['name']} »" for e in created)
    sent = [e for e in trace.events("queue_send") if e["ok"]]
    from_main = [e for e in sent if e["task"] == "main"]
    need(not from_main, f"xQueueSend est appelé depuis app_main (tâche « main », première fois à {from_main[0]['t_ms'] if from_main else 0} ms) "
         "et non depuis une tâche créée par xTaskCreate : le sondage du bouton doit tourner dans sa propre tâche "
         "(relire : « Producteur et consommateur »)")
    need(len(created) >= 2, f"{len(created)} tâche(s) créée(s) par xTaskCreate" + (f" ({names})" if created else "")
         + " : il en faut deux, une qui sonde le bouton et une qui commande la LED "
         "(relire : « Créer une tâche avec xTaskCreate »)")
    small = [e for e in created if e["stack"] < MIN_STACK]
    need(not small, "la tâche « {} » est créée avec une pile de {} octets : il en faut au moins {} "
         "(relire : « La taille de la pile »)".format(*(
             (small[0]["name"], small[0]["stack"], MIN_STACK) if small else ("", 0, 0))))

    need(trace.events("queue_create"), "aucune file créée : appelez xQueueCreate dans app_main, avant de créer les tâches "
         "(relire : « Les files : xQueueCreate, xQueueSend, xQueueReceive »)")
    need(sent, "aucun événement n'est passé par la file (aucun xQueueSend réussi) : les tâches communiquent "
         "autrement, par exemple par une variable globale partagée ; postez chaque appui avec xQueueSend "
         "(relire : « Les files : xQueueCreate, xQueueSend, xQueueReceive »)")
    received = [e for e in trace.events("queue_receive") if e["ok"]]
    need(received, f"{len(sent)} événement(s) envoyé(s) dans la file mais aucun reçu : la tâche de la LED doit "
         "attendre avec xQueueReceive(file, &evenement, portMAX_DELAY) (relire : « Les files : xQueueCreate, xQueueSend, xQueueReceive »)")

    changes: list[int] = []
    previous = 0
    for t, level in trace.gpio_levels(LED):
        if level != previous:
            changes.append(t)
        previous = level
    before = [t for t in changes if t < PRESS_STARTS[0]]
    need(not before, f"la LED a changé à {before[0] if before else 0} ms, avant tout appui : elle ne doit changer "
         "qu'à la réception d'un événement (relire : « Producteur et consommateur »)")
    ends = PRESS_STARTS[1:] + [MAX_MS + 1]
    for n, (start, end, edge) in enumerate(zip(PRESS_STARTS, ends, es2.stable_edges()), 1):
        mine = [t for t in changes if start <= t < end]
        span = f"de {start} à {start + RELEASE_AT} ms"
        need(mine, f"l'appui n°{n} ({span}) n'a provoqué aucun changement de la LED : l'événement n'a pas été "
             "envoyé ou pas reçu (relire : « Producteur et consommateur »)")
        need(len(mine) == 1, f"{len(mine)} changements de la LED pour l'appui n°{n} ({span}), aux instants "
             + ", ".join(f"{t} ms" for t in mine) + " : il en faut un seul, l'anti-rebond du TP 2 doit rester dans "
             "la tâche du bouton (relire : « Le programme du TP en un coup d'œil »)")
        need(edge <= mine[0] <= edge + WINDOW_MS, f"la LED a changé à {mine[0]} ms pour l'appui n°{n} : il faut "
             f"entre {edge} et {edge + WINDOW_MS} ms, dans les {WINDOW_MS} ms qui suivent le premier front stable "
             "(relire : « Le programme du TP en un coup d'œil »)")
    need(len(changes) == len(PRESS_STARTS), f"la LED a changé {len(changes)} fois au lieu de {len(PRESS_STARTS)} "
         "(relire : « Producteur et consommateur »)")
