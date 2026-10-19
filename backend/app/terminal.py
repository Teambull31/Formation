import asyncio
import fcntl
import json
import os
import signal
import struct
import subprocess
import termios
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def is_local(host: str | None) -> bool:
    return host in ("127.0.0.1", "::1")


def _resize(fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def register_terminal(app: FastAPI, workspace: Path) -> None:
    @app.websocket("/ws/terminal")
    async def terminal(ws: WebSocket) -> None:
        if not is_local(ws.client.host if ws.client else None):
            await ws.close(code=1008)
            return
        await ws.accept()
        master, slave = os.openpty()
        proc = subprocess.Popen(
            [os.environ.get("SHELL") or "/bin/bash"],
            stdin=slave, stdout=slave, stderr=slave, cwd=workspace,
            env={**os.environ, "TERM": "xterm-256color"},
            start_new_session=True,
            preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
        )
        os.close(slave)
        loop = asyncio.get_running_loop()
        out: asyncio.Queue[bytes | None] = asyncio.Queue()

        def on_readable() -> None:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b""
            if data:
                out.put_nowait(data)
            else:
                loop.remove_reader(master)
                out.put_nowait(None)

        loop.add_reader(master, on_readable)

        async def pump_out() -> None:
            while (data := await out.get()) is not None:
                await ws.send_bytes(data)

        task = asyncio.create_task(pump_out())
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    os.write(master, msg["bytes"])
                    continue
                text = msg.get("text") or ""
                try:
                    size = json.loads(text)["resize"]
                    _resize(master, int(size[0]), int(size[1]))
                except (ValueError, KeyError, TypeError, IndexError):
                    os.write(master, text.encode())
        except (WebSocketDisconnect, OSError, RuntimeError):
            pass
        finally:
            task.cancel()
            loop.remove_reader(master)
            try:
                os.killpg(proc.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            os.close(master)
            try:
                await loop.run_in_executor(None, lambda: proc.wait(2))
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
