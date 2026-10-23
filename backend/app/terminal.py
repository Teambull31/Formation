import asyncio
import contextlib
import fcntl
import ipaddress
import json
import os
import signal
import struct
import subprocess
import termios
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.tp import child_env

from app.tp import child_env

LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
QUEUE_MAX = 64


def is_local(host: str | None) -> bool:
    try:
        ip = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip in (ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1"))


def _hostname(netloc: str) -> str | None:
    try:
        return urlsplit("//" + netloc).hostname
    except ValueError:
        return None


def _origin_ok(ws: WebSocket, hosts=LOCAL_HOSTNAMES) -> bool:
    """Host doit etre dans `hosts` (local par defaut); un Origin eventuel doit etre same-origin (anti CSWSH / DNS rebinding)."""
    host = ws.headers.get("host", "")
    if _hostname(host) not in hosts:
        return False
    origin = ws.headers.get("origin")
    if origin is None:
        return True  # client non navigateur
    try:
        o = urlsplit(origin)
        return (o.scheme in ("http", "https") and o.netloc.lower() == host.lower()
                and o.hostname in hosts)
    except ValueError:
        return False


def exec_ok(conn, remote_hosts=frozenset()) -> bool:
    """Execution de commandes : pair loopback + Host local, ou (opt-in FORMATION_REMOTE_EXEC) Host autorise.
    Le mot de passe est deja verifie par le middleware BasicAuth, obligatoire des que remote_hosts est non vide."""
    if is_local(conn.client.host if conn.client else None) and _origin_ok(conn):
        return True
    return bool(remote_hosts) and _origin_ok(conn, remote_hosts)


def _resize(fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _write_all(fd: int, data: bytes) -> None:
    while data:
        data = data[os.write(fd, data):]


def register_terminal(app: FastAPI, workspace: Path, remote_hosts=frozenset()) -> None:
    @app.websocket("/ws/terminal")
    async def terminal(ws: WebSocket) -> None:
        if not exec_ok(ws, remote_hosts):
            await ws.close(code=1008)
            return
        await ws.accept()
        loop = asyncio.get_running_loop()
        master = proc = None
        tasks: list[asyncio.Task] = []
        try:
            master, slave = os.openpty()
            try:
                proc = subprocess.Popen(
                    [os.environ.get("SHELL") or "/bin/bash"],
                    stdin=slave, stdout=slave, stderr=slave, cwd=workspace,
                    env=child_env(TERM="xterm-256color"),
                    start_new_session=True,
                    preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
                )
            finally:
                os.close(slave)

            out: asyncio.Queue[bytes | None] = asyncio.Queue(QUEUE_MAX)
            paused = False

            def pause() -> None:
                nonlocal paused
                if not paused:
                    loop.remove_reader(master)
                    paused = True

            def on_readable() -> None:
                if out.full():
                    return pause()
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                out.put_nowait(data or None)
                if not data or out.full():
                    pause()

            loop.add_reader(master, on_readable)

            async def pump_out() -> None:
                nonlocal paused
                while (data := await out.get()) is not None:
                    await ws.send_bytes(data)
                    if paused and not out.full():
                        paused = False
                        loop.add_reader(master, on_readable)

            async def pump_in() -> None:
                while True:
                    msg = await ws.receive()
                    if msg["type"] == "websocket.disconnect":
                        return
                    if msg.get("bytes") is not None:
                        data = msg["bytes"]
                    else:
                        text = msg.get("text") or ""
                        try:
                            size = json.loads(text)["resize"]
                            _resize(master, int(size[0]), int(size[1]))
                            continue
                        except (ValueError, KeyError, TypeError, IndexError):
                            data = text.encode()
                    await loop.run_in_executor(None, _write_all, master, data)

            tasks = [asyncio.create_task(pump_out()), asyncio.create_task(pump_in())]
            for t in tasks:  # recupere l'exception: pas de "never retrieved"
                t.add_done_callback(lambda t: t.cancelled() or t.exception())
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            # shell mort -> pump_out fini en premier: on ferme le websocket
            if tasks[0].done():
                with contextlib.suppress(Exception):
                    await ws.close()
        except (WebSocketDisconnect, OSError, RuntimeError):
            pass
        finally:
            # nettoyage synchrone d'abord: reste complet meme si le handler est annule
            for t in tasks:
                t.cancel()
            if master is not None:
                with contextlib.suppress(Exception):
                    loop.remove_reader(master)
            if proc is not None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGHUP)
            if master is not None:
                os.close(master)
            if proc is not None:
                try:
                    await asyncio.wait_for(loop.run_in_executor(None, proc.wait), 2)
                except TimeoutError:
                    pass
                finally:  # aussi sur annulation
                    if proc.poll() is None:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
            with contextlib.suppress(Exception):
                await ws.close()
