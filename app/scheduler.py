"""Scheduler simples para rotinas periódicas."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

Job = Callable[[], Coroutine[Any, Any, None]]

_jobs: list[tuple[str, float, Job]] = []
_tasks: list[asyncio.Task] = []


def register(name: str, interval_seconds: float = 300):
    """Decorator para registrar rotina periódica.

    Uso:
        @register("meu-job", interval_seconds=300)
        async def meu_job():
            ...
    """

    def decorator(fn: Job) -> Job:
        _jobs.append((name, interval_seconds, fn))
        return fn

    return decorator


async def _run_loop(name: str, interval: float, fn: Job) -> None:
    """Loop interno que executa job no intervalo."""
    await asyncio.sleep(interval)
    while True:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Job '%s' falhou", name)
        await asyncio.sleep(interval)


def start_all() -> None:
    """Inicia todos os jobs registrados como tasks asyncio."""
    for name, interval, fn in _jobs:
        task = asyncio.create_task(_run_loop(name, interval, fn))
        _tasks.append(task)
        logger.info("Scheduler: '%s' iniciado (intervalo=%ss)", name, interval)


async def stop_all() -> None:
    """Cancela todos os jobs."""
    for task in _tasks:
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
