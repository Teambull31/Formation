"""Simulator trace (one JSON object per line) as read by the TP checks, and the check error type.

Check modules (checks/<tp_id>.py) import this as `esp_trace`: `from esp_trace import Trace, need`.
"""
import json


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


class Trace:
    def __init__(self, text: str):
        self._events: list[dict] = []
        self.bad_lines = 0  # lines that are not trace events (should never happen: the trace fd is private)
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                e = None
            if isinstance(e, dict) and isinstance(e.get("ev"), str) and type(e.get("t_ms")) is int:
                self._events.append(e)
            else:
                self.bad_lines += 1

    def events(self, ev: str, **match) -> list[dict]:
        return [e for e in self._events if e["ev"] == ev and all(e.get(k) == v for k, v in match.items())]

    def gpio_levels(self, pin: int) -> list[tuple[int, int]]:
        return [(e["t_ms"], e["level"]) for e in self.events("gpio_set", pin=pin)]

    def logs(self, tag: str | None = None, level: str | None = None) -> list[dict]:
        match = {k: v for k, v in (("tag", tag), ("level", level)) if v is not None}
        return self.events("log", **match)

    def last_end(self) -> dict:
        ends = self.events("end")
        return ends[-1] if ends else {}
