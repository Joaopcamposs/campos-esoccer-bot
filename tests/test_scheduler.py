"""Testes do scheduler."""

import asyncio

from app.scheduler import _jobs, _tasks, register, start_all, stop_all


async def test_register_and_run():
    """Verifica registro e execução de job."""
    executed = []

    @register("test-job", interval_seconds=0.05)
    async def test_job():
        executed.append(True)

    start_all()
    await asyncio.sleep(0.15)
    await stop_all()

    assert len(executed) >= 2
    _jobs.pop()


async def test_job_survives_exception():
    """Verifica que job continua após exceção."""
    calls = []

    @register("failing-job", interval_seconds=0.05)
    async def failing_job():
        calls.append(True)
        if len(calls) == 1:
            raise ValueError("boom")

    start_all()
    await asyncio.sleep(0.2)
    await stop_all()

    assert len(calls) >= 2
    _jobs.pop()


async def test_stop_all_clears_tasks():
    """Verifica que stop_all limpa lista de tasks."""

    @register("cleanup-job", interval_seconds=60)
    async def noop():
        pass

    start_all()
    assert len(_tasks) > 0
    await stop_all()
    assert len(_tasks) == 0
    _jobs.pop()
