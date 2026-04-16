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
            print(f"[startup] waiting for {name} ... {exc}")
            time.sleep(max(1, interval_seconds))


def _check_mysql(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _read_redis_line(sock: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("redis socket closed unexpectedly")
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
                raise RuntimeError(f"redis auth failed: {auth_reply.decode(errors='ignore').strip()}")
        ping_reply = _send_redis_command(sock, "PING")
        if not ping_reply.startswith(b"+PONG"):
            raise RuntimeError(f"redis ping failed: {ping_reply.decode(errors='ignore').strip()}")


def _parse_host_port(endpoint: str, default_port: int) -> tuple[str, int]:
    raw = str(endpoint or "").strip()
    if not raw:
        raise ValueError("endpoint is empty")
    host, sep, port_text = raw.partition(":")
    if not sep:
        return host, default_port
    return host, int(port_text or default_port)


def _check_tcp(host: str, port: int, timeout: int = 3) -> None:
    with socket.create_connection((host, port), timeout=timeout):
        return


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

    if settings.STARTUP_WAIT_MILVUS:
        _retry_until_ready(
            "milvus",
            lambda: _check_tcp(settings.MILVUS_HOST, int(settings.MILVUS_PORT)),
            wait_interval,
        )
        connected.append(f"milvus({settings.MILVUS_HOST}:{settings.MILVUS_PORT})")

    if settings.STARTUP_WAIT_MINIO:
        minio_host, minio_port = _parse_host_port(settings.MINIO_ENDPOINT, 9000)
        _retry_until_ready(
            "minio",
            lambda: _check_tcp(minio_host, minio_port),
            wait_interval,
        )
        connected.append(f"minio({settings.MINIO_ENDPOINT})")

    return connected
