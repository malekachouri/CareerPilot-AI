"""Celery application.

Run with `celery -A careerpilot.worker worker` and `celery -A careerpilot.worker beat`.

Queues follow docs/02 §5 so slow LLM/media jobs never block notifications or ingestion.
"""

from __future__ import annotations

import time

from celery import Celery
from kombu import Queue  # type: ignore[attr-defined]

from careerpilot.core.config import get_settings

settings = get_settings()

celery_app = Celery("careerpilot", broker=settings.valkey_url, backend=settings.valkey_url)
celery_app.conf.update(
    task_default_queue="default",
    task_queues=[Queue(name) for name in ("default", "ingest", "content", "llm", "media")],  # type: ignore[no-untyped-call]
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    beat_schedule={
        "heartbeat": {"task": "careerpilot.heartbeat", "schedule": 300.0},
    },
)


@celery_app.task(name="careerpilot.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"


@celery_app.task(name="careerpilot.heartbeat")  # type: ignore[untyped-decorator]
def heartbeat() -> float:
    """Proves beat → broker → worker works; ops can alert when `worker:heartbeat` gets stale."""
    import redis

    now = time.time()
    redis.Redis.from_url(settings.valkey_url).set("worker:heartbeat", now, ex=3600)
    return now


@celery_app.task(name="content.import_source")  # type: ignore[untyped-decorator]
def import_source(
    source_id: str, job_id: str, owner_id: str | None = None, publish: bool | None = None
) -> None:
    import asyncio

    from careerpilot import tasks

    asyncio.run(tasks.import_source(source_id, job_id, owner_id, publish))


@celery_app.task(name="generator.generate", time_limit=1800, soft_time_limit=1750)  # type: ignore[untyped-decorator]
def generate_questions(request: dict[str, object], owner_id: str, job_id: str) -> None:
    import asyncio

    from careerpilot import tasks

    asyncio.run(tasks.generate_questions(request, owner_id, job_id))


app = celery_app
