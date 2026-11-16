"""Source adapters: where content comes from. Each one describes the source (metadata, licence) and yields
files to parse. Add a source type by writing an adapter and registering it in `ADAPTERS`.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from careerpilot.core.config import get_settings
from careerpilot.modules.content.models import Source
from careerpilot.modules.content.parsers import SUPPORTED_EXTENSIONS


class AdapterError(Exception):
    pass


@dataclass
class SourceDescription:
    """What the adapter learned about the source (stored in `sources.metadata`)."""

    license_spdx: str | None = None
    license_url: str | None = None
    homepage: str | None = None
    revision: str | None = None  # e.g. commit SHA, so imports are reproducible
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchedFile:
    path: str
    fmt: str
    data: bytes
    url: str | None = None


class SourceAdapter(Protocol):
    async def describe(self, source: Source) -> SourceDescription: ...
    def files(self, source: Source, description: SourceDescription) -> AsyncIterator[FetchedFile]: ...


def _fmt(path: str) -> str:
    return PurePosixPath(path).suffix.lower().lstrip(".")


def _included(path: str, config: dict[str, Any]) -> bool:
    include = config.get("include") or ["*"]
    exclude = config.get("exclude") or []
    return any(fnmatch.fnmatch(path, p) for p in include) and not any(
        fnmatch.fnmatch(path, p) for p in exclude
    )


class LocalAdapter:
    """Files under the allowed content folders (`CONTENT_DIRS`, `PRIVATE_CONTENT_DIR`). No path escapes."""

    def _root(self, source: Source) -> Path:
        settings = get_settings()
        allowed = [Path(d).resolve() for d in settings.content_dirs]
        if settings.private_content_dir:
            allowed.append(Path(settings.private_content_dir).resolve())
        raw = Path(str(source.config.get("path", ""))).expanduser()
        candidates = [raw] if raw.is_absolute() else [base / raw for base in allowed]
        target = next((c.resolve() for c in candidates if c.exists()), candidates[0].resolve())
        if not any(target == base or base in target.parents for base in allowed):
            raise AdapterError(f"path {target} is outside the allowed content folders")
        if not target.exists():
            raise AdapterError(f"path {target} does not exist")
        return target

    async def describe(self, source: Source) -> SourceDescription:
        root = self._root(source)
        return SourceDescription(license_spdx=source.license_spdx, metadata={"path": str(root)})

    async def files(self, source: Source, description: SourceDescription) -> AsyncIterator[FetchedFile]:
        settings = get_settings()
        root = self._root(source)
        paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        count = 0
        for p in paths:
            rel = p.name if root.is_file() else p.relative_to(root).as_posix()
            if _fmt(rel) not in SUPPORTED_EXTENSIONS or not _included(rel, source.config):
                continue
            if p.stat().st_size > settings.import_max_file_bytes:
                continue
            count += 1
            if count > settings.import_max_files:
                break
            yield FetchedFile(path=rel, fmt=_fmt(rel), data=p.read_bytes())


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "CareerPilot-AI-importer (+https://github.com/malekachouri/CareerPilot-AI)"},
    )


async def _download(client: httpx.AsyncClient, url: str) -> bytes:
    max_bytes = get_settings().import_max_file_bytes
    async with client.stream("GET", url) as resp:
        if resp.status_code != 200:
            raise AdapterError(f"GET {url} returned {resp.status_code}")
        chunks, size = [], 0
        async for chunk in resp.aiter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise AdapterError(f"{url} is larger than {max_bytes} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


class HttpAdapter:
    """One or more public HTTPS files (JSON/CSV/YAML/MD/PDF), e.g. an open dataset or a public API export."""

    async def describe(self, source: Source) -> SourceDescription:
        return SourceDescription(license_spdx=source.license_spdx, homepage=source.url)

    async def files(self, source: Source, description: SourceDescription) -> AsyncIterator[FetchedFile]:
        urls = source.config.get("urls") or ([source.url] if source.url else [])
        async with _client() as client:
            for url in urls:
                if urlparse(url).scheme != "https":
                    raise AdapterError(f"only https URLs are allowed: {url}")
                fmt = str(source.config.get("format") or _fmt(urlparse(url).path))
                yield FetchedFile(
                    path=urlparse(url).path, fmt=fmt, data=await _download(client, url), url=url
                )


_GH_URL = re.compile(
    r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<path>.*))?)?/?$"
)
_QUESTION_HINTS = re.compile(r"quiz|question|interview|exercise|qcm|test|assessment|faq", re.I)


class GitHubAdapter:
    """A public GitHub repository: metadata and licence from the REST API, files from raw downloads.

    The licence is read from GitHub's licence detection; the import is refused or limited to a link when the
    policy says so (see `licensing.decide`). The commit SHA is recorded so the import is reproducible.
    """

    def _parse(self, source: Source) -> dict[str, str | None]:
        m = _GH_URL.match(source.url or "")
        if not m:
            raise AdapterError(f"not a GitHub repository URL: {source.url}")
        return m.groupdict()

    def _api_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = get_settings().github_token
        if token:
            headers["Authorization"] = f"Bearer {token.get_secret_value()}"
        return headers

    async def describe(self, source: Source) -> SourceDescription:
        settings = get_settings()
        parts = self._parse(source)
        owner, repo = parts["owner"], parts["repo"]
        async with _client() as client:
            r = await client.get(
                f"{settings.github_api_url}/repos/{owner}/{repo}", headers=self._api_headers()
            )
            if r.status_code == 404:
                raise AdapterError("repository not found or private")
            if r.status_code != 200:
                raise AdapterError(f"GitHub API returned {r.status_code}: {r.text[:200]}")
            meta = r.json()
            ref = parts["ref"] or meta.get("default_branch") or "main"
            c = await client.get(
                f"{settings.github_api_url}/repos/{owner}/{repo}/commits/{ref}", headers=self._api_headers()
            )
            sha = c.json().get("sha") if c.status_code == 200 else None
        lic = meta.get("license") or {}
        return SourceDescription(
            license_spdx=lic.get("spdx_id"),
            license_url=(lic.get("url") and f"https://github.com/{owner}/{repo}/blob/{ref}/LICENSE") or None,
            homepage=meta.get("html_url"),
            revision=sha or ref,
            metadata={
                "full_name": meta.get("full_name"),
                "description": meta.get("description"),
                "stars": meta.get("stargazers_count"),
                "default_branch": meta.get("default_branch"),
                "pushed_at": meta.get("pushed_at"),
                "archived": meta.get("archived"),
                "fork": meta.get("fork"),
                "ref": ref,
                "license_name": lic.get("name"),
            },
        )

    async def list_candidates(self, source: Source, description: SourceDescription) -> dict[str, Any]:
        """Repository scan: README, supported files and the ones that look like question banks."""
        settings = get_settings()
        parts = self._parse(source)
        owner, repo, sub = parts["owner"], parts["repo"], (parts["path"] or "").strip("/")
        async with _client() as client:
            r = await client.get(
                f"{settings.github_api_url}/repos/{owner}/{repo}/git/trees/{description.revision}",
                params={"recursive": "1"},
                headers=self._api_headers(),
            )
        if r.status_code != 200:
            raise AdapterError(f"could not list repository files ({r.status_code})")
        tree = [e for e in r.json().get("tree", []) if e.get("type") == "blob"]
        files = [e for e in tree if not sub or e["path"].startswith(sub + "/") or e["path"] == sub]
        readmes = [e["path"] for e in files if PurePosixPath(e["path"]).name.lower().startswith("readme")]
        supported = [
            e
            for e in files
            if _fmt(e["path"]) in SUPPORTED_EXTENSIONS
            and not e["path"].startswith(".github/")
            and int(e.get("size") or 0) <= settings.import_max_file_bytes
            and _included(e["path"], source.config)
        ]
        hinted = [e["path"] for e in supported if _QUESTION_HINTS.search(e["path"])]
        return {
            "readmes": readmes,
            "supported_files": len(supported),
            "formats": sorted({_fmt(e["path"]) for e in supported}),
            "question_bank_candidates": hinted[:50],
            "truncated": bool(r.json().get("truncated")),
            "_paths": [e["path"] for e in supported],
        }

    async def files(self, source: Source, description: SourceDescription) -> AsyncIterator[FetchedFile]:
        settings = get_settings()
        parts = self._parse(source)
        scan = await self.list_candidates(source, description)
        paths: list[str] = scan["_paths"]
        if source.config.get("only_hinted", True) and not source.config.get("include"):
            hinted = set(scan["question_bank_candidates"])
            paths = [p for p in paths if p in hinted or PurePosixPath(p).name.lower().startswith("readme")]
        async with _client() as client:
            for path in paths[: settings.import_max_files]:
                repo_path = f"{parts['owner']}/{parts['repo']}/{description.revision}/{path}"
                url = f"{settings.github_raw_url}/{repo_path}"
                try:
                    data = await _download(client, url)
                except AdapterError:
                    continue
                yield FetchedFile(
                    path=path,
                    fmt=_fmt(path),
                    data=data,
                    url=f"https://github.com/{parts['owner']}/{parts['repo']}/blob/{description.revision}/{path}",
                )


class LinkOnlyAdapter:
    """Websites whose terms do not allow copying: only the reference is kept."""

    async def describe(self, source: Source) -> SourceDescription:
        return SourceDescription(license_spdx=source.license_spdx, homepage=source.url)

    async def files(self, source: Source, description: SourceDescription) -> AsyncIterator[FetchedFile]:
        return
        yield  # pragma: no cover - makes this an async generator


ADAPTERS: dict[str, SourceAdapter] = {
    "file": LocalAdapter(),
    "directory": LocalAdapter(),
    "url": HttpAdapter(),
    "github_repo": GitHubAdapter(),
    "website": LinkOnlyAdapter(),
}


def adapter_for(kind: str) -> SourceAdapter:
    try:
        return ADAPTERS[kind]
    except KeyError:
        raise AdapterError(f"unknown source kind: {kind}") from None
