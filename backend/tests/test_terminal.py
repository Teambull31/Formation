import concurrent.futures as cf
import json
import os
import re
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.terminal import is_local


def read_until(ws, pattern: bytes, timeout: float = 5.0) -> bytes:
    """Lit les frames jusqu'a ce que la regex `pattern` matche; borne par timeout."""
    buf = b""
    deadline = time.monotonic() + timeout
    ex = cf.ThreadPoolExecutor(1)
    try:
        while not re.search(pattern, buf):
            try:
                buf += ex.submit(ws.receive_bytes).result(max(deadline - time.monotonic(), 0.01))
            except cf.TimeoutError:
                raise AssertionError(f"timeout, recu {buf!r}")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return buf


def test_is_local():
    assert is_local("127.0.0.1") and is_local("::1")
    assert not is_local("192.168.1.20") and not is_local(None) and not is_local("testclient")


def test_terminal_echoes_command_output(terminal_client):
    with terminal_client.websocket_connect("/ws/terminal") as ws:
        ws.send_bytes(b"echo salu$((0+1))t\n")
        assert b"salu1t" in read_until(ws, b"salu1t")


def test_terminal_rejects_remote_client(terminal_remote_client):
    with pytest.raises(WebSocketDisconnect) as e:
        with terminal_remote_client.websocket_connect("/ws/terminal") as ws:
            ws.receive_bytes()
    assert e.value.code == 1008


def test_terminal_resize(terminal_client):
    with terminal_client.websocket_connect("/ws/terminal") as ws:
        ws.send_text(json.dumps({"resize": [31, 97]}))
        time.sleep(0.3)
        ws.send_bytes(b"stty size\n")
        assert b"31 97" in read_until(ws, rb"31 97\r\n")


def test_terminal_kills_shell_on_close(terminal_client):
    with terminal_client.websocket_connect("/ws/terminal") as ws:
        ws.send_bytes(b"echo p$((1))id=$$=\n")
        pid = int(re.search(rb"p1id=(\d+)=", read_until(ws, rb"p1id=\d+=")).group(1))
        os.kill(pid, 0)  # vivant
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("shell encore present (vivant ou zombie)")
