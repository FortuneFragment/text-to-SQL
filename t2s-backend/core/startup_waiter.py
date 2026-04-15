from __future__ import annotations

import socket
import time
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.config import settings


def _retry_until_ready(name: str, checker: Callable[[], None], interval_seconds: int) -> None:
    """中文备注：处理until ready相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 核心处理：执行当前阶段的业务逻辑。
    while True:
        try:
            checker()
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[startup] 等待 {name} 就绪中 ... {exc}")
            time.sleep(max(1, interval_seconds))


def _check_mysql(engine: Engine) -> None:
    """中文备注：处理mysql相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 核心处理：执行当前阶段的业务逻辑。
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _read_redis_line(sock: socket.socket) -> bytes:
    """中文备注：读取redis line相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 变量构建：计算并更新 `data`。
    data = b""
    # 2. 核心处理：执行当前阶段的业务逻辑。
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("Redis 连接被意外关闭")
        data += chunk
    # 3. 返回结果：输出当前函数最终结果。
    return data


def _send_redis_command(sock: socket.socket, *parts: str) -> bytes:
    """中文备注：发送redis command相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 结果组装：将当前阶段产物写入结构化结果。
    payload = f"*{len(parts)}\r\n".encode("utf-8")
    # 2. 迭代处理：遍历集合并逐项构建结果。
    for part in parts:
        binary = part.encode("utf-8")
        payload += f"${len(binary)}\r\n".encode("utf-8") + binary + b"\r\n"
    sock.sendall(payload)
    # 3. 返回结果：输出当前函数最终结果。
    return _read_redis_line(sock)


def _check_redis(host: str, port: int, password: str) -> None:
    """中文备注：处理redis相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 变量构建：计算并更新 `with socket.create_connection((host, port), timeout`。
    with socket.create_connection((host, port), timeout=3) as sock:
        if password:
            auth_reply = _send_redis_command(sock, "AUTH", password)
            if not auth_reply.startswith(b"+OK"):
                raise RuntimeError(f"Redis 鉴权失败: {auth_reply.decode(errors='ignore').strip()}")

        ping_reply = _send_redis_command(sock, "PING")
        if not ping_reply.startswith(b"+PONG"):
            raise RuntimeError(f"Redis PING 失败: {ping_reply.decode(errors='ignore').strip()}")


def wait_for_docker_middlewares(system_engine: Engine) -> list[str]:
    """中文备注：处理for docker middlewares相关业务数据并返回结果。
    执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
    """
    # 1. 条件分支：根据当前状态选择不同处理路径。
    if not settings.STARTUP_WAIT_ENABLED:
        return []

    # 2. 变量构建：计算并更新 `wait_interval`。
    wait_interval = settings.STARTUP_WAIT_INTERVAL_SECONDS

    # 3. 核心处理：执行当前阶段的业务逻辑。
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

    # 4. 变量构建：计算并更新 `connected`。
    connected = [
        f"mysql(system:{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB})",
        f"redis({settings.REDIS_HOST}:{settings.REDIS_PORT})",
    ]
    # 5. 返回结果：输出当前函数最终结果。
    return connected
