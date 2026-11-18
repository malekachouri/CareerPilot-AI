"""Unit tests: format parsers, canonical validation, deduplication keys and the licence policy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from careerpilot.modules.content.canonical import QuestionIn, content_hash
from careerpilot.modules.content.licensing import decide
from careerpilot.modules.content.models import SourceStatus
from careerpilot.modules.content.parsers import ParseContext, parse_bytes

CTX = ParseContext(path="bank", default_categories=("docker",))


def test_json_with_aliases_letters_and_indexes() -> None:
    data = b"""{"questions": [
      {"question": "Which port does HTTPS use?", "choices": ["80", "443", "22"], "answer": "B",
       "difficulty": "beginner", "category": "networking"},
      {"question": "Pick the container runtimes", "choices": ["containerd", "CRI-O", "nginx"],
       "answer": [0, 1]},
      {"question": "", "choices": ["a", "b"]}
    ]}"""
    result = parse_bytes(data, "json", CTX)
    assert len(result.items) == 2
    first, second = result.items
    assert first.answer == ["B"] and first.difficulty == 1 and first.categories == ["networking"]
    assert second.type.value == "mcq_multi" and second.answer == ["A", "B"]
    assert second.categories == ["docker"]  # source default
    assert len(result.errors) == 1 and "stem" in result.errors[0]["error"]


def test_yaml_file_level_company_and_capture_format() -> None:
    data = b"""
company: Neoshore
questions:
  - id: q1
    type: mcq_single
    domain: containers
    stem: What mount type would you use?
    options: [{id: A, text: bind-mount}, {id: B, text: volumes}]
    answer_key: null
"""
    item = parse_bytes(data, "yaml", ParseContext(path="cap.yaml")).items[0]
    assert item.companies == ["neoshore"]
    assert item.categories == ["containers"]
    assert item.answer is None and item.external_id == "q1"


def test_csv_option_columns_and_pipe_list() -> None:
    data = (
        b"question,option_a,option_b,option_c,answer,explanation,category\n"
        b"What does IaC mean?,Infrastructure as Code,Internet as Cloud,Index as Cache,A,Declared,terraform\n"
    )
    item = parse_bytes(data, "csv", CTX).items[0]
    assert item.options[0].text == "Infrastructure as Code"
    assert item.answer == ["A"] and item.source_ref == "bank:2"

    data2 = b"question,options,answer\nPick one,red|green|blue,green\n"
    item2 = parse_bytes(data2, "csv", CTX).items[0]
    assert item2.answer == ["B"]  # matched by option text


def test_markdown_task_list_quiz() -> None:
    md = b"""# Docker quiz

#### Q1. Which command lists running containers?

- [ ] docker images
- [x] docker ps
- [ ] docker run

Explanation: `docker ps` lists running containers.

#### Q2. Pick the valid volume types

```bash
docker run -v data:/data app
```

- [x] named volume
- [x] bind mount
- [ ] layer cache

## Not a question (no options)
"""
    result = parse_bytes(md, "md", CTX)
    assert len(result.items) == 2
    q1, q2 = result.items
    assert q1.stem == "Which command lists running containers?" and q1.answer == ["B"]
    assert q1.explanation and "lists running" in q1.explanation
    assert q2.type.value == "mcq_multi" and q2.answer == ["A", "B"] and "docker run" in (q2.context or "")


def test_plain_text_layout_like_pdf_extraction() -> None:
    text = b"""DOCKER TEST
Q1 - Which action should you take?
  You must persist app data across container re-creation.
   A. Use a tmpfs mount.
   B. Use a named volume.
Answer: B

2. Which file lists build context exclusions?
   A. .dockerignore
   B. .gitignore
"""
    result = parse_bytes(text, "txt", CTX)
    assert len(result.items) == 2
    assert result.items[0].context and "persist" in result.items[0].context
    assert result.items[0].answer == ["B"] and result.items[1].answer is None


def test_canonical_validation_rules() -> None:
    with pytest.raises(ValidationError, match="unknown options"):
        QuestionIn(stem="Pick", options=[{"id": "A", "text": "x"}, {"id": "B", "text": "y"}], answer=["C"])  # type: ignore[list-item]
    with pytest.raises(ValidationError, match="exactly one"):
        QuestionIn(
            stem="Pick", options=[{"id": "A", "text": "x"}, {"id": "B", "text": "y"}], answer=["A", "B"]
        )  # type: ignore[list-item]
    with pytest.raises(ValidationError, match="at least 2 options"):
        QuestionIn(stem="Pick one", options=[{"id": "A", "text": "x"}])  # type: ignore[list-item]
    # Symbols and case are significant in options.
    ok = QuestionIn(stem="Root prompt char?", options=[{"id": "A", "text": "$"}, {"id": "B", "text": "#"}])  # type: ignore[list-item]
    assert len(ok.options) == 2
    survey = QuestionIn(
        type="survey",
        stem="Preferred mode?",
        answer=["A"],  # type: ignore[arg-type]
        options=[{"id": "A", "text": "Remote"}, {"id": "B", "text": "On site"}],
    )  # type: ignore[list-item]
    assert survey.answer is None  # questionnaires are never scored


def test_content_hash_ignores_option_order_and_case_of_stem() -> None:
    a = QuestionIn(stem="What is a Pod?", options=[{"id": "A", "text": "x"}, {"id": "B", "text": "y"}])  # type: ignore[list-item]
    b = QuestionIn(stem="what is a pod", options=[{"id": "A", "text": "y"}, {"id": "B", "text": "x"}])  # type: ignore[list-item]
    assert content_hash(a) == content_hash(b)


@pytest.mark.parametrize(
    ("spdx", "status"),
    [
        ("MIT", SourceStatus.APPROVED),
        ("CC-BY-4.0", SourceStatus.APPROVED),
        ("CC-BY-SA-4.0", SourceStatus.APPROVED),
        ("CC-BY-NC-4.0", SourceStatus.APPROVED),
        ("CC-BY-NC-ND-3.0", SourceStatus.LINK_ONLY),
        (None, SourceStatus.LINK_ONLY),
        ("NOASSERTION", SourceStatus.LINK_ONLY),
        ("GPL-3.0", SourceStatus.PENDING_REVIEW),
        ("WTFPL", SourceStatus.PENDING_REVIEW),
    ],
)
def test_licence_policy(spdx: str | None, status: SourceStatus) -> None:
    assert decide(spdx).status == status


def test_non_commercial_becomes_link_only_in_commercial_mode() -> None:
    d = decide("CC-BY-NC-SA-4.0", commercial_mode=True)
    assert d.status == SourceStatus.LINK_ONLY and d.commercial_use_allowed is False
    assert decide("CC-BY-SA-4.0").share_alike is True


def _tiny_pdf(lines: list[str]) -> bytes:
    """A minimal valid PDF with one text line per row (no extra dependency needed)."""
    ops = ["BT", "/F1 11 Tf", "14 TL", "50 780 Td"]
    for line in lines:
        ops.append(f"({line.replace('(', '[').replace(')', ']')}) Tj T*")
    ops.append("ET")
    stream = "\n".join(ops).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_pdf_extraction_then_text_parser() -> None:
    pdf = _tiny_pdf(
        ["1. Which command shows disk usage per filesystem?", "   A. df -h", "   B. ls -l", "Answer: A"]
    )
    result = parse_bytes(pdf, "pdf", CTX)
    assert len(result.items) == 1, result.errors
    assert result.items[0].stem.startswith("Which command shows disk usage") and result.items[0].answer == [
        "A"
    ]
