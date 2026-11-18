"""Enqueue background work. Production: Celery via Valkey. Tests: an in-process dispatcher (see conftest)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Dispatcher = Callable[[str, dict[str, Any]], Awaitable[None]]

# Task name -> queue (docs/02 §5): slow LLM work never blocks imports or notifications.
TASK_QUEUES = {
    "content.import_source": "content",
    "generator.generate": "llm",
    "coach.process": "llm",
}


async def _celery_dispatch(name: str, kwargs: dict[str, Any]) -> None:
    from careerpilot.worker import celery_app

    celery_app.send_task(name, kwargs=kwargs, queue=TASK_QUEUES.get(name, "default"))


_dispatcher: Dispatcher = _celery_dispatch


async def enqueue(name: str, **kwargs: Any) -> None:
    await _dispatcher(name, kwargs)


def set_dispatcher(dispatcher: Dispatcher | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher or _celery_dispatch
