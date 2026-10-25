"""TP d'essai pour les tests du pilote (le préfixe _ le tient hors des TP livrés) : LED en GPIO 2 allumée à 500 ms."""
from esp_trace import Trace, need

SCENARIO: dict = {}
MAX_MS = 1000


def verify(trace: Trace, source: str) -> None:
    before = [level for t, level in trace.gpio_levels(2) if t <= 500]
    need(before and before[-1] == 1, "la LED en GPIO 2 doit être allumée (niveau 1) à 500 ms")
