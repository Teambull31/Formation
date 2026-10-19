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


def test_is_local_ipv4_mapped():
    assert is_local("::ffff:127.0.0.1") and not is_local("::ffff:10.0.0.1") and not is_local("junk")


def _rejected(client, headers):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/ws/terminal", headers=headers) as ws:
            ws.receive_bytes()
    assert e.value.code == 1008


@pytest.mark.parametrize("origin,host", [
    ("http://localhost.evil.example", "localhost:8000"),
    ("http://127.0.0.1.nip.io", "127.0.0.1.nip.io"),
    ("http://evil.example", "localhost:8000"),
    ("http://localhost:3000", "localhost:8000"),
    ("null", "localhost:8000"),
    ("http://evil.example", "evil.example"),
])
def test_terminal_rejects_bad_origin(terminal_client, origin, host):
    _rejected(terminal_client, {"origin": origin, "host": host})


@pytest.mark.parametrize("host", ["evil.example", "localhost.evil.example:8000", "evil.example:8000"])
def test_terminal_rejects_bad_host(terminal_client, host):
    _rejected(terminal_client, {"host": host})


@pytest.mark.parametrize("host", ["localhost:8000", "[::1]:8000", "127.0.0.1:8000"])
def test_terminal_accepts_same_origin(terminal_client, host):
    with terminal_client.websocket_connect(
        "/ws/terminal", headers={"origin": f"http://{host}", "host": host}
    ) as ws:
        ws.send_bytes(b"echo salu$((0+1))t\n")
        assert b"salu1t" in read_until(ws, b"salu1t")


def test_terminal_closes_when_shell_exits(terminal_client):
    with terminal_client.websocket_connect("/ws/terminal") as ws:
        ws.send_bytes(b"exit\n")
        with pytest.raises(WebSocketDisconnect):
            read_until(ws, rb"NEVER")


def test_terminal_failed_spawn_closes_without_leak(terminal_client, monkeypatch):
    monkeypatch.setenv("SHELL", "/nonexistent/shell")
    before = len(os.listdir("/proc/self/fd"))
    with pytest.raises(WebSocketDisconnect):
        with terminal_client.websocket_connect("/ws/terminal") as ws:
            ws.receive_bytes()
    assert len(os.listdir("/proc/self/fd")) <= before
