"""Integration tests: import pipeline (local, GitHub + licence gate, uploads), dedup, versions, privacy."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import func, select

from careerpilot.core.config import get_settings
from careerpilot.core.db import SessionFactory
from careerpilot.modules.content.models import Question, QuestionVersion, Source
from careerpilot.modules.content.service import run_import
from tests.conftest import csrf, login_as

BANK = """questions:
  - id: d1
    categories: [docker]
    stem: Which instruction sets the default command of a container image?
    options: [CMD, RUN, COPY]
    answer: A
  - id: d2
    categories: [k8s]
    stem: Which object exposes pods behind a stable virtual IP and DNS name?
    options: [Service, Secret, Job]
    answer: Service
  - id: d3
    categories: [unknown-topic]
    stem: This one has no known category at all.
    options: [a, b]
"""


@pytest.fixture
def bank_dir(tmp_path: Path) -> Path:
    (tmp_path / "bank").mkdir()
    (tmp_path / "bank" / "docker.yaml").write_text(BANK)
    settings = get_settings()
    original = settings.content_dirs
    settings.content_dirs = [*original, str(tmp_path)]
    yield tmp_path
    settings.content_dirs = original


async def _source(**kw: object) -> Source:
    async with SessionFactory() as db:
        s = Source(
            **{
                "slug": "test-bank",
                "name": "Test bank",
                "kind": "directory",
                "license_spdx": "MIT",
                "config": {"path": "bank"},
            }
            | kw
        )
        db.add(s)
        await db.commit()
        return s


async def test_local_import_maps_aliases_reports_unknown_and_is_idempotent(
    taxonomy: None, bank_dir: Path
) -> None:
    source = await _source()
    async with SessionFactory() as db:
        report = await run_import(db, source.id, publish=True)
    assert (report.created, report.parsed) == (2, 3)
    assert report.unknown_categories == {"unknown-topic": 1}  # "k8s" resolved via alias
    assert report.licence["status"] == "approved"

    async with SessionFactory() as db:
        again = await run_import(db, source.id, publish=True)
    assert (again.created, again.unchanged) == (0, 2)

    # Changing the content creates a new version instead of a duplicate.
    (bank_dir / "bank" / "docker.yaml").write_text(BANK.replace("[CMD, RUN, COPY]", "[CMD, RUN, COPY, ADD]"))
    async with SessionFactory() as db:
        changed = await run_import(db, source.id, publish=True)
        versions = await db.scalar(select(func.count()).select_from(QuestionVersion))
    assert changed.updated == 1 and versions == 3


async def test_cross_source_duplicates_are_skipped(taxonomy: None, bank_dir: Path) -> None:
    a = await _source()
    b = await _source(slug="other-bank")
    async with SessionFactory() as db:
        await run_import(db, a.id, publish=True)
        report = await run_import(db, b.id, publish=True)
    assert report.created == 0 and report.duplicates == 2


async def test_imports_go_to_review_unless_published(taxonomy: None, bank_dir: Path) -> None:
    source = await _source()
    async with SessionFactory() as db:
        await run_import(db, source.id)
        statuses = set(await db.scalars(select(Question.status)))
    assert statuses == {"in_review"}


async def test_local_paths_cannot_escape_content_dirs(taxonomy: None) -> None:
    source = await _source(config={"path": "/etc"})
    async with SessionFactory() as db:
        with pytest.raises(Exception, match="outside the allowed"):
            await run_import(db, source.id)


GH = "https://api.github.com/repos/acme/quiz"


def _mock_repo(license_spdx: str | None) -> None:
    respx.get(GH).respond(
        json={
            "full_name": "acme/quiz",
            "default_branch": "main",
            "html_url": "https://github.com/acme/quiz",
            "stargazers_count": 5,
            "license": {"spdx_id": license_spdx, "name": "x", "url": "u"} if license_spdx else None,
        }
    )
    respx.get(f"{GH}/commits/main").respond(json={"sha": "abc123"})
    respx.get(f"{GH}/git/trees/abc123").respond(
        json={
            "tree": [
                {"path": "README.md", "type": "blob", "size": 10},
                {"path": "docker/docker-quiz.md", "type": "blob", "size": 100},
                {"path": "src/app.py", "type": "blob", "size": 100},
            ]
        }
    )
    respx.get("https://raw.githubusercontent.com/acme/quiz/abc123/README.md").respond(text="# Quiz bank\n")
    respx.get("https://raw.githubusercontent.com/acme/quiz/abc123/docker/docker-quiz.md").respond(
        text="#### Q1. What does `docker ps` list?\n- [x] Running containers\n- [ ] Images\n"
    )


@respx.mock
async def test_github_import_detects_bank_records_licence_commit_and_attribution(taxonomy: None) -> None:
    _mock_repo("MIT")
    source = await _source(
        slug="gh",
        kind="github_repo",
        url="https://github.com/acme/quiz",
        license_spdx=None,
        categories=["docker"],
        config={},
    )
    async with SessionFactory() as db:
        report = await run_import(db, source.id, publish=True)
        q = await db.scalar(select(Question))
        s = await db.get(Source, source.id)
    assert report.created == 1
    assert report.scan["readmes"] == ["README.md"]
    assert report.scan["question_bank_candidates"] == ["docker/docker-quiz.md"]
    assert s is not None and s.license_spdx == "MIT" and s.metadata_["revision"] == "abc123"
    assert (
        q is not None and q.source_ref == "https://github.com/acme/quiz/blob/abc123/docker/docker-quiz.md#L1"
    )
    assert q.provenance == "community_licensed"


@respx.mock
async def test_github_repo_without_licence_is_link_only(taxonomy: None) -> None:
    _mock_repo(None)
    raw = respx.get("https://raw.githubusercontent.com/acme/quiz/abc123/docker/docker-quiz.md")
    source = await _source(
        slug="gh", kind="github_repo", url="https://github.com/acme/quiz", license_spdx=None, config={}
    )
    async with SessionFactory() as db:
        report = await run_import(db, source.id, publish=True)
        s = await db.get(Source, source.id)
    assert report.link_only and report.created == 0
    assert not raw.called  # nothing is downloaded
    assert s is not None and s.status == "link_only" and "No licence" in s.licence_decision


async def test_admin_import_endpoint_runs_job_and_inspect(
    client: httpx.AsyncClient, taxonomy: None, bank_dir: Path
) -> None:
    source = await _source()
    await login_as(client, "learner@example.org")
    assert (
        await client.post(f"/api/v1/admin/sources/{source.id}/import", headers=csrf(client))
    ).status_code == 403
    await login_as(client, "admin@example.org", role="admin")
    r = await client.post(f"/api/v1/admin/sources/{source.id}/import?publish=true", headers=csrf(client))
    assert r.status_code == 202
    job = (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()
    assert job["status"] == "succeeded" and job["result"]["created"] == 2
    inspect = (await client.post(f"/api/v1/admin/sources/{source.id}/inspect", headers=csrf(client))).json()
    assert inspect["decision"] == "approved"
    sources = (await client.get("/api/v1/admin/sources")).json()
    assert sources[0]["question_count"] == 2


async def test_upload_creates_private_questions_only_visible_to_owner(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    await login_as(client, "owner@example.org")
    files = {"file": ("notes.yaml", b"company: Neoshore\n" + BANK.encode(), "application/x-yaml")}
    r = await client.post(
        "/api/v1/me/imports/upload", files=files, data={"kind": "personal_capture"}, headers=csrf(client)
    )
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 2
    mine = (await client.get("/api/v1/questions?provenance=personal_capture")).json()
    assert mine["total"] == 2 and mine["items"][0]["visibility"] == "private"
    assert mine["items"][0]["label"] == "Your private notes from a test you took"
    assert "answer_key" not in mine["items"][0]  # never in listings

    await login_as(client, "someone-else@example.org")
    assert (await client.get("/api/v1/questions?provenance=personal_capture")).json()["total"] == 0
    other = await client.get(f"/api/v1/questions/{mine['items'][0]['id']}")
    assert other.status_code == 404
