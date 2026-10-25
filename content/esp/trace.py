"""Simulator trace (one JSON object per line) as read by the TP checks, and the check error type.

Check modules (checks/<tp_id>.py) import this as `esp_trace`: `from esp_trace import Trace, need`.
"""
import json


class CheckError(Exception):
    """Erreur affichée à l'apprenant."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


# Fields the accessors rely on, per event type; an event lacking one (or with the wrong type) is dropped.
FIELDS = {
    "gpio_set": {"pin": int, "level": int},  # plus "task": name of the task that called gpio_set_level
    "gpio_config": {"pin": int, "mode": str},
    "log": {"level": str, "tag": str, "msg": str},
    "task_create": {"name": str},  # plus "stack" (bytes) and "priority" for tasks made by xTaskCreate
    "queue_create": {"queue": int, "length": int, "item_size": int},
    "queue_send": {"queue": int, "task": str, "ok": bool},
    "queue_receive": {"queue": int, "task": str, "ok": bool},
    "adc_read": {"channel": int, "raw": int},  # successful adc_oneshot_read; raw is the value returned
    "i2c_xfer": {"addr": int, "ok": bool},  # one transfer to a device; ok False = NACK/no device (ESP_ERR_TIMEOUT)
    "end": {"reason": str},
}


def _valid(e) -> bool:
    if not (isinstance(e, dict) and type(e.get("ev")) is str and type(e.get("t_ms")) is int):
        return False
    return all(type(e.get(k)) is t for k, t in FIELDS.get(e["ev"], {}).items())  # `is`: True is not a level


class Trace:
    def __init__(self, text: str):
        self._events: list[dict] = []
        self.bad_lines = 0  # lines that are not well-formed events (should never happen: the trace fd is private)
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                e = None
            if _valid(e):
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
