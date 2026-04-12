from __future__ import annotations

import socket
import time
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.config import settings


def _retry_until_ready(name: str, checker: Callable[[], None], interval_seconds: int) -> None:
    while True:
        try:
            checker()
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[startup] 等待 {name} 就绪中 ... {exc}")
            time.sleep(max(1, interval_seconds))


def _check_mysql(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _read_redis_line(sock: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("Redis 连接被意外关闭")
        data += chunk
    return data


def _send_redis_command(sock: socket.socket, *parts: str) -> bytes:
    payload = f"*{len(parts)}\r\n".encode("utf-8")
    for part in parts:
        binary = part.encode("utf-8")
        payload += f"${len(binary)}\r\n".encode("utf-8") + binary + b"\r\n"
    sock.sendall(payload)
    return _read_redis_line(sock)


def _check_redis(host: str, port: int, password: str) -> None:
    with socket.create_connection((host, port), timeout=3) as sock:
        if password:
            auth_reply = _send_redis_command(sock, "AUTH", password)
            if not auth_reply.startswith(b"+OK"):
                raise RuntimeError(f"Redis 鉴权失败: {auth_reply.decode(errors='ignore').strip()}")

        ping_reply = _send_redis_command(sock, "PING")
        if not ping_reply.startswith(b"+PONG"):
            raise RuntimeError(f"Redis PING 失败: {ping_reply.decode(errors='ignore').strip()}")


def wait_for_docker_middlewares(system_engine: Engine) -> list[str]:
    if not settings.STARTUP_WAIT_ENABLED:
        return []

    wait_interval = settings.STARTUP_WAIT_INTERVAL_SECONDS

    _retry_until_ready("mysql(system)", lambda: _check_mysql(system_engine), wait_interval)
    _retry_until_ready(
        "redis",
        lambda: _check_redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=settings.REDIS_PASSWORD,
        ),
        wait_interval,
    )

    connected = [
        f"mysql(system:{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB})",
        f"redis({settings.REDIS_HOST}:{settings.REDIS_PORT})",
    ]
    return connected
