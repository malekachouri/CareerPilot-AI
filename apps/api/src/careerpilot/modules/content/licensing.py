"""Licence policy (docs/11 §2): decides whether a source's content may be imported or only linked.

Conservative by design: anything unknown, missing or restrictive becomes `link_only`.
"""

from __future__ import annotations

from dataclasses import dataclass

from careerpilot.modules.content.models import SourceStatus


@dataclass(frozen=True)
class LicenceDecision:
    status: SourceStatus
    reason: str
    commercial_use_allowed: bool | None
    derivatives_allowed: bool | None
    share_alike: bool


PERMISSIVE = {
    "CC0-1.0",
    "MIT",
    "MIT-0",
    "APACHE-2.0",
    "BSD-2-CLAUSE",
    "BSD-3-CLAUSE",
    "ISC",
    "UNLICENSE",
    "0BSD",
    "CC-BY-4.0",
    "CC-BY-3.0",
    "ZLIB",
    "PDDL-1.0",
    "ODC-BY-1.0",
}
SHARE_ALIKE = {"CC-BY-SA-4.0", "CC-BY-SA-3.0", "ODBL-1.0"}
NON_COMMERCIAL = {"CC-BY-NC-4.0", "CC-BY-NC-3.0", "CC-BY-NC-SA-4.0", "CC-BY-NC-SA-3.0"}
NO_DERIVATIVES = {"CC-BY-ND-4.0", "CC-BY-ND-3.0", "CC-BY-NC-ND-4.0", "CC-BY-NC-ND-3.0"}
COPYLEFT_CODE = {
    "GPL-2.0",
    "GPL-3.0",
    "AGPL-3.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "MPL-2.0",
    "EPL-2.0",
    "GPL-2.0-ONLY",
    "GPL-3.0-ONLY",
    "GPL-3.0-OR-LATER",
    "AGPL-3.0-ONLY",
    "AGPL-3.0-OR-LATER",
}
PUBLIC_DOMAIN_MARKERS = {"PUBLIC-DOMAIN", "US-GOV-WORK"}


def decide(spdx: str | None, *, commercial_mode: bool = False) -> LicenceDecision:
    """Map an SPDX id (as GitHub reports it) to an import decision."""
    lid = (spdx or "").strip().upper()
    if not lid or lid in {"NOASSERTION", "NONE", "OTHER", "UNKNOWN"}:
        return LicenceDecision(
            SourceStatus.LINK_ONLY,
            "No licence found: all rights reserved by default. Only a link is stored.",
            None,
            None,
            False,
        )
    if lid in PERMISSIVE or lid in PUBLIC_DOMAIN_MARKERS:
        return LicenceDecision(
            SourceStatus.APPROVED, f"{spdx}: reuse allowed with attribution.", True, True, False
        )
    if lid in SHARE_ALIKE:
        return LicenceDecision(
            SourceStatus.APPROVED,
            f"{spdx}: reuse allowed with attribution; adaptations stay under the same licence.",
            True,
            True,
            True,
        )
    if lid in NON_COMMERCIAL:
        if commercial_mode:
            return LicenceDecision(
                SourceStatus.LINK_ONLY,
                f"{spdx}: non-commercial only, and this instance runs in commercial mode.",
                False,
                True,
                "SA" in lid,
            )
        return LicenceDecision(
            SourceStatus.APPROVED,
            f"{spdx}: allowed for this non-commercial instance only (flagged).",
            False,
            True,
            "SA" in lid,
        )
    if lid in NO_DERIVATIVES:
        return LicenceDecision(
            SourceStatus.LINK_ONLY,
            f"{spdx}: no derivatives allowed, so questions cannot be adapted. Link only.",
            "NC" not in lid,
            False,
            False,
        )
    if lid in COPYLEFT_CODE:
        return LicenceDecision(
            SourceStatus.PENDING_REVIEW,
            f"{spdx}: a software licence applied to text. A reviewer must decide.",
            True,
            True,
            True,
        )
    return LicenceDecision(
        SourceStatus.PENDING_REVIEW,
        f"{spdx}: not in the policy table. A reviewer must decide.",
        None,
        None,
        False,
    )
