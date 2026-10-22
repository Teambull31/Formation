from __future__ import annotations
import asyncio
import fcntl
import json
import os
import pty
import select
import signal
import struct
import subprocess
import termios
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.security import LOCAL_HOSTS, clean_env, is_local, is_trusted  # noqa: F401  (réexportés)


def register_terminal(app: FastAPI, workspace: Path | str) -> None:
    ws_path = Path(workspace).resolve()
    ws_path.mkdir(parents=True, exist_ok=True)

    @app.websocket("/ws/terminal")
    async def terminal_endpoint(websocket: WebSocket):
        client_host = websocket.client.host if websocket.client else None
        if not is_trusted(client_host, websocket.headers):
            await websocket.close(code=1008)
            return

        await websocket.accept()

        master, slave = pty.openpty()
        try:
            init_winsize = struct.pack("HHHH", 24, 80, 0, 0)
            fcntl.ioctl(master, termios.TIOCSWINSZ, init_winsize)
        except Exception:
            pass

        shell = os.environ.get("SHELL", "/bin/bash")
        term_env = clean_env()
        term_env["TERM"] = "xterm-256color"
        term_env["COLORTERM"] = "truecolor"
        term_env["LANG"] = "C.UTF-8"
        term_env["LC_ALL"] = "C.UTF-8"

        proc = subprocess.Popen(
            [shell],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=str(ws_path),
            preexec_fn=os.setsid,
            close_fds=True,
            env=term_env,
        )
        os.close(slave)

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        async def read_from_pty():
            while not stop_event.is_set():
                r, _, _ = await loop.run_in_executor(None, select.select, [master], [], [], 0.05)
                if r:
                    try:
                        data = os.read(master, 1024)
                        if not data:
                            break
                        await websocket.send_bytes(data)
                    except OSError:
                        break
                elif proc.poll() is not None:
                    break

        async def write_to_pty():
            try:
                while not stop_event.is_set():
                    try:
                        msg = await websocket.receive()
                    except WebSocketDisconnect:
                        break
                    except Exception:
                        break

                    if msg.get("type") == "websocket.disconnect":
                        break

                    data_bytes = msg.get("bytes")
                    text = msg.get("text")

                    if data_bytes:
                        os.write(master, data_bytes)
                    elif text:
                        try:
                            parsed = json.loads(text)
                            if (
                                isinstance(parsed, dict)
                                and "resize" in parsed
                                and isinstance(parsed["resize"], list)
                                and len(parsed["resize"]) == 2
                            ):
                                rows, cols = parsed["resize"]
                                winsize = struct.pack("HHHH", int(rows), int(cols), 0, 0)
                                fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
                                continue
                        except Exception:
                            pass
                        os.write(master, text.encode("utf-8"))
            finally:
                stop_event.set()

        pty_task = asyncio.create_task(read_from_pty())
        ws_task = asyncio.create_task(write_to_pty())

        done, pending = await asyncio.wait(
            [pty_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        stop_event.set()
        for task in pending:
            task.cancel()

        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass

        try:
            os.close(master)
        except Exception:
            pass
