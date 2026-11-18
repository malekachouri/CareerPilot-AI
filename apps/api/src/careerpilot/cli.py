"""Admin CLI: `careerpilot create-admin --email you@example.org`.

The password is prompted (or read from CAREERPILOT_ADMIN_PASSWORD), never passed as an argument.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from careerpilot.core.db import SessionFactory, engine
from careerpilot.core.errors import ProblemError
from careerpilot.modules.auth import service
from careerpilot.modules.users.models import Role
from careerpilot.modules.users.repository import audit, get_by_email


async def _create_admin(email: str, display_name: str) -> int:
    password = os.environ.get("CAREERPILOT_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    async with SessionFactory() as db:
        existing = await get_by_email(db, email)
        if existing is not None:
            existing.role = Role.ADMIN.value
            audit(
                db,
                "user.promoted",
                actor_id=None,
                entity_type="user",
                entity_id=str(existing.id),
                metadata={"role": "admin", "via": "cli"},
            )
            await db.commit()
            print(f"Existing user {email} promoted to admin.")
            return 0
        try:
            await service.register(
                db, email=email, password=password, display_name=display_name, locale="en", role=Role.ADMIN
            )
        except ProblemError as exc:
            print(f"Error: {exc.title}. {exc.detail or ''}", file=sys.stderr)
            return 1
    print(f"Admin {email} created.")
    return 0


async def _seed() -> int:
    import json

    import careerpilot.models  # noqa: F401
    from careerpilot.modules.content.seed import seed_content
    from careerpilot.modules.taxonomy.seed import seed_taxonomy

    async with SessionFactory() as db:
        taxonomy = await seed_taxonomy(db)
        content = await seed_content(db)
    q = content["questions"]
    print(
        json.dumps(
            {
                "taxonomy": taxonomy,
                "sources": content["sources"],
                "tests": content["tests"],
                "questions": {k: q[k] for k in ("parsed", "created", "updated", "unchanged", "duplicates")},
                "kb": content["kb"],
            }
        )
    )
    return 0


async def _import_captures(email: str, path: str) -> int:
    import json

    import careerpilot.models  # noqa: F401
    from careerpilot.modules.content.seed import import_captures

    async with SessionFactory() as db:
        user = await get_by_email(db, email)
        if user is None:
            print(f"Error: no user with email {email}", file=sys.stderr)
            return 1
        result = await import_captures(db, owner_id=user.id, path=path)
    r = result["import"]
    print(
        json.dumps(
            {
                "created": r["created"],
                "updated": r["updated"],
                "unchanged": r["unchanged"],
                "duplicates": r["duplicates"] + r["near_duplicates"],
                "errors": r["error_count"],
                "unknown_categories": r["unknown_categories"],
                "collections": result["collections"],
            }
        )
    )
    return 0


async def _kb_reindex() -> int:
    import json

    import careerpilot.models  # noqa: F401
    from careerpilot.core.llm import LLMUnavailableError
    from careerpilot.modules.content.seed import content_root
    from careerpilot.modules.kb import service as kb

    async with SessionFactory() as db:
        notes = await kb.seed_notes(db, content_root())
        questions = await kb.index_question_explanations(db)
        try:
            embedded = await kb.embed_missing(db)
        except LLMUnavailableError as exc:
            print(f"Embeddings skipped (keyword search still works): {exc}", file=sys.stderr)
            embedded = 0
    print(json.dumps({"notes_changed": notes, "questions_changed": questions, "chunks_embedded": embedded}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="careerpilot")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="create an admin account, or promote an existing user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Admin")
    sub.add_parser("seed", help="taxonomy, sources, original questions and curated tests (idempotent)")
    sub.add_parser("kb-reindex", help="re-index the coach knowledge base and add missing embeddings")
    c = sub.add_parser("import-captures", help="import your PRIVATE captured tests (visible only to you)")
    c.add_argument("--owner", required=True, help="email of the account that owns the captures")
    c.add_argument(
        "--path",
        default=os.environ.get("PRIVATE_CONTENT_DIR") or "",
        help="folder with the capture YAML files (default: $PRIVATE_CONTENT_DIR)",
    )
    args = parser.parse_args(argv)

    async def run(coro: object) -> int:
        try:
            return await coro  # type: ignore[misc, no-any-return]
        finally:
            await engine.dispose()

    if args.command == "seed":
        return asyncio.run(run(_seed()))
    if args.command == "kb-reindex":
        return asyncio.run(run(_kb_reindex()))
    if args.command == "import-captures":
        if not args.path:
            parser.error("--path is required (or set PRIVATE_CONTENT_DIR)")
        from careerpilot.core.config import get_settings

        get_settings().private_content_dir = args.path  # allow the importer to read this folder
        return asyncio.run(run(_import_captures(args.owner, args.path)))

    if args.command == "create-admin":

        async def go() -> int:
            try:
                return await _create_admin(args.email, args.name)
            finally:
                await engine.dispose()

        return asyncio.run(go())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
