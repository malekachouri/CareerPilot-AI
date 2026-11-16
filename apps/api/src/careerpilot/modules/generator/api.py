from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from careerpilot.core.errors import ProblemError
from careerpilot.core.jobs import enqueue
from careerpilot.core.llm import get_llm
from careerpilot.core.valkey import hit_rate_limit
from careerpilot.modules.auth.deps import CurrentUser, DbSession
from careerpilot.modules.content.api import JobOut
from careerpilot.modules.content.models import BackgroundJob
from careerpilot.modules.generator.service import GENERATABLE_TYPES, GenerateRequest

router = APIRouter(prefix="/generator", tags=["generator"])


@router.get("/status")
async def generator_status(_: CurrentUser) -> dict[str, Any]:
    llm = get_llm()
    return {
        "provider": llm.name,
        "model": llm.model,
        "available": await llm.health(),
        "types": sorted(t.value for t in GENERATABLE_TYPES),
    }


@router.post("/questions", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def generate_questions(body: GenerateRequest, db: DbSession, user: CurrentUser) -> BackgroundJob:
    """Queues a generation job (a local model can take minutes on CPU). Poll GET /jobs/{id}."""
    if await hit_rate_limit(f"rl:generate:{user.id}", 20, 3600):
        raise ProblemError(429, "Too many generation requests", "Try again later.")
    job = BackgroundJob(kind="generate", requested_by=user.id, params=body.model_dump(mode="json"))
    db.add(job)
    await db.commit()
    await enqueue(
        "generator.generate", request=body.model_dump(mode="json"), owner_id=str(user.id), job_id=str(job.id)
    )
    await db.refresh(job)
    return job
