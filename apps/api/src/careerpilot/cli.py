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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="careerpilot")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="create an admin account, or promote an existing user")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Admin")
    args = parser.parse_args(argv)

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
