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
    "nvs_set": {"ns": str, "key": str, "type": str},  # plus "value" (number or text) or "size" for a blob
    "nvs_commit": {"ns": str},
    "wifi": {"event": str},  # sta_start | sta_connected | sta_disconnected (plus "reason") | got_ip | sta_stop; "delivered": false when the event queue refused it
    "mqtt": {"event": str},  # before_connect | connected | disconnected | error | subscribed | unsubscribed | published | data; "connected" carries client_id, username and password (when set) and lwt_topic, lwt_msg, lwt_retain, lwt_qos
    "mqtt_publish": {"topic": str, "payload": str, "retain": bool, "qos": int},  # plus "msg_id"
    "mqtt_subscribe": {"topic": str, "qos": int},
    "wdt_reset": {"tasks": str, "panic": bool},  # task watchdog expiry; "tasks" = the names that did not reset it
    "reboot": {"reason": str},  # sw | task_wdt | scripted; the program starts again from app_main
    "tls_handshake": {"host": str, "ok": bool, "verify": str},  # mqtts:// or https:// handshake; verify = ok | cn_skipped (skip_cert_common_name_check set) | failed:<no_verification|parse|handshake|not_trusted|expired|cn_mismatch>
    "ota_begin": {"url": str, "cleartext": bool},  # esp_https_ota started (arguments valid); cleartext True = an http:// URL, fetched without TLS
    "ota_end": {"url": str, "ok": bool, "err": str},  # err = esp_err_to_name of the result (ESP_OK, ESP_FAIL, ESP_ERR_OTA_VALIDATE_FAILED, ...)
    "ota_mark": {"valid": bool},  # esp_ota_mark_app_valid_cancel_rollback (True) / esp_ota_mark_app_invalid_rollback_and_reboot (False)
    "rollback": {"why": str, "from": str, "to": str},  # why = not_validated (reset while PENDING_VERIFY) | marked_invalid; versions of the slots
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

    def all(self) -> list[dict]:
        """Every event in the order the simulator wrote them (to compare the order of events of different types)."""
        return list(self._events)

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
