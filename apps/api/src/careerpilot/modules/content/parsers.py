"""Format parsers: JSON, YAML, CSV, Markdown and plain text (incl. text extracted from PDFs).

Each parser turns raw content into canonical `QuestionIn` items and reports every row it could not use,
so an import never fails silently. Add a format by writing a function and registering it in `PARSERS`.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import yaml
from pydantic import ValidationError

from careerpilot.modules.content.canonical import QuestionIn, normalize_text
from careerpilot.modules.content.models import QuestionType

LETTERS = "ABCDEFGHIJKL"


@dataclass
class ParseResult:
    items: list[QuestionIn] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def extend(self, other: ParseResult) -> None:
        self.items += other.items
        self.errors += other.errors


@dataclass(frozen=True)
class ParseContext:
    path: str = ""
    default_categories: tuple[str, ...] = ()
    default_companies: tuple[str, ...] = ()
    default_language: str = "en"


def slugify(value: str) -> str:
    return normalize_text(value).replace(" ", "-")


def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _normalize_options(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if isinstance(raw, dict):  # {"A": "text", "B": "text"}
        return [{"id": str(k).strip(), "text": str(v)} for k, v in raw.items()]
    out = []
    for i, opt in enumerate(raw):
        if isinstance(opt, dict):
            oid = str(_first(opt, "id", "key", "letter") or LETTERS[i])
            out.append({"id": oid, "text": str(_first(opt, "text", "label", "value", "option") or "")})
        else:
            out.append({"id": LETTERS[i], "text": str(opt)})
    return out


def _normalize_answer(raw: Any, options: list[dict[str, str]]) -> list[str] | None:
    """Accepts letters ("B", "A,C"), 0-based indexes, or the option text itself."""
    if raw is None or raw == "" or raw == []:
        return None
    values = raw if isinstance(raw, list) else re.split(r"[,;|]", str(raw)) if isinstance(raw, str) else [raw]
    ids = {o["id"] for o in options}
    by_text = {o["text"].strip().lower(): o["id"] for o in options}
    result = []
    for v in values:
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            if 0 <= v < len(options):
                result.append(options[v]["id"])
            continue
        s = str(v).strip()
        if s in ids:
            result.append(s)
        elif s.upper() in ids:
            result.append(s.upper())
        elif s.lower() in by_text:
            result.append(by_text[s.lower()])
        else:
            result.append(s)  # left as-is so validation reports it
    return result or None


def _categories(d: dict[str, Any], ctx: ParseContext) -> list[str]:
    raw = _first(d, "categories", "category", "tags", "topic", "domain")
    if raw is None:
        return list(ctx.default_categories)
    values = raw if isinstance(raw, list) else re.split(r"[,;|]", str(raw))
    return [str(v).strip().lower() for v in values if str(v).strip()]


def _infer_type(declared: Any, options: list[dict[str, str]], answer: list[str] | None) -> str:
    if declared:
        return str(declared).strip().lower()
    if not options:
        return QuestionType.OPEN_ENDED.value
    texts = [o["text"].strip().lower() for o in options]
    if texts in (["true", "false"], ["vrai", "faux"]):
        return QuestionType.TRUE_FALSE.value
    if answer and len(answer) > 1:
        return QuestionType.MCQ_MULTI.value
    return QuestionType.MCQ_SINGLE.value


def record_to_question(d: dict[str, Any], ctx: ParseContext, ref: str) -> QuestionIn:
    """Map one loosely-structured record (JSON/YAML/CSV row) to the canonical format."""
    options = _normalize_options(_first(d, "options", "choices", "answers_list"))
    if not options:  # CSV style: option_a, option_b, …
        flat = [(k, v) for k, v in d.items() if re.fullmatch(r"(option|choice)_?[a-l]", str(k).lower()) and v]
        options = [{"id": str(k)[-1].upper(), "text": str(v)} for k, v in sorted(flat)]
    answer = _normalize_answer(
        _first(d, "answer", "answer_key", "correct", "correct_answer", "answers"), options
    )
    return QuestionIn.model_validate(
        {
            "external_id": _first(d, "id", "external_id", "qid"),
            "type": _infer_type(_first(d, "type", "question_type"), options, answer),
            "stem": _first(d, "stem", "question", "prompt", "title"),
            "context": _first(d, "context", "scenario", "passage", "code"),
            "options": options,
            "answer": answer,
            "explanation": _first(d, "explanation", "rationale", "solution"),
            "distractor_explanations": _first(d, "distractor_explanations") or {},
            "difficulty": _first(d, "difficulty", "level") or 2,
            "categories": _categories(d, ctx),
            "companies": [slugify(str(c)) for c in (_first(d, "companies") or ctx.default_companies)],
            "language": _first(d, "language", "lang") or ctx.default_language,
            "time_limit_s": _first(d, "time_limit_s"),
            "source_ref": ref,
        }
    )


def _collect(records: Iterable[tuple[str, Any]], ctx: ParseContext) -> ParseResult:
    result = ParseResult()
    for ref, record in records:
        if not isinstance(record, dict):
            result.errors.append({"ref": ref, "error": "record is not an object"})
            continue
        try:
            result.items.append(record_to_question(record, ctx, ref))
        except ValidationError as exc:
            msgs = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'item'}: {e['msg']}" for e in exc.errors())
            result.errors.append({"ref": ref, "error": msgs})
    return result


def _file_context(data: Any, ctx: ParseContext) -> ParseContext:
    """File-level metadata (`company`, `category`, `language`) applies to every record in the file."""
    if not isinstance(data, dict):
        return ctx
    from dataclasses import replace

    company, category, language = data.get("company"), data.get("category"), data.get("language")
    return replace(
        ctx,
        default_companies=(slugify(str(company)),) if company else ctx.default_companies,
        default_categories=(str(category).lower(),) if category else ctx.default_categories,
        default_language=str(language) if language else ctx.default_language,
    )


def _records_from_structure(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("questions", "items", "data", "quiz"):
            if isinstance(data.get(key), list):
                return list(data[key])
        # A single question object; other documents (e.g. an interview report) contain no questions.
        return [data] if any(k in data for k in ("stem", "question", "prompt")) else []
    return []


def parse_json(text: str, ctx: ParseContext) -> ParseResult:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ParseResult(
            errors=[{"ref": ctx.path, "error": f"invalid JSON: {exc.msg} (line {exc.lineno})"}]
        )
    records, ctx = _records_from_structure(data), _file_context(data, ctx)
    return _collect(((f"{ctx.path}#{i}", r) for i, r in enumerate(records)), ctx)


def parse_yaml(text: str, ctx: ParseContext) -> ParseResult:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return ParseResult(errors=[{"ref": ctx.path, "error": f"invalid YAML: {exc}"}])
    records, ctx = _records_from_structure(data), _file_context(data, ctx)
    return _collect(((f"{ctx.path}#{i}", r) for i, r in enumerate(records)), ctx)


def parse_csv(text: str, ctx: ParseContext) -> ParseResult:
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for i, row in enumerate(reader, start=2):  # line 1 is the header
        record: dict[str, Any] = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if isinstance(record.get("options"), str) and "|" in record["options"]:
            record["options"] = [o.strip() for o in record["options"].split("|")]
        rows.append((f"{ctx.path}:{i}", record))
    return _collect(rows, ctx)


# Markdown quiz convention used by many GitHub banks:
#   #### Q1. Question text            (any heading level 2-6; "Q1." / "1." / "Question:" prefixes optional)
#   - [ ] wrong option
#   - [x] correct option
#   Explanation / ```code``` / text between heading and options = context
_MD_HEADING = re.compile(r"^#{2,6}\s+(?:Q(?:uestion)?\s*\d*[.:)]?\s*|\d+[.)]\s*)?(?P<stem>.+?)\s*$")
_MD_OPTION = re.compile(r"^\s*[-*]\s+\[(?P<mark>[ xX])\]\s+(?P<text>.+?)\s*$")
_MD_EXPLANATION = re.compile(
    r"^\s*(?:>\s*)?\**(?:explanation|answer explanation|why)\**\s*[:：]\s*(?P<text>.+)$",
    re.I,
)


def parse_markdown(text: str, ctx: ParseContext) -> ParseResult:
    result = ParseResult()
    blocks: list[tuple[int, str, list[str]]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _MD_HEADING.match(line)
        if m:
            blocks.append((lineno, m.group("stem"), []))
        elif blocks:
            blocks[-1][2].append(line)
    for lineno, stem, body in blocks:
        options: list[dict[str, str]] = []
        correct: list[str] = []
        context_lines: list[str] = []
        explanation: list[str] = []
        in_code = False
        for line in body:
            if line.strip().startswith("```"):
                in_code = not in_code
                context_lines.append(line)
                continue
            opt = None if in_code else _MD_OPTION.match(line)
            if opt:
                oid = LETTERS[len(options)] if len(options) < len(LETTERS) else str(len(options))
                options.append({"id": oid, "text": opt.group("text")})
                if opt.group("mark").lower() == "x":
                    correct.append(oid)
                continue
            exp = None if in_code else _MD_EXPLANATION.match(line)
            if exp:
                explanation.append(exp.group("text"))
            elif options and line.strip() and not in_code:
                explanation.append(line.strip().lstrip("> "))
            elif not options:
                context_lines.append(line)
        if not options:
            continue  # a heading without a task list is a section title, not a question
        record = {
            "stem": stem,
            "context": "\n".join(context_lines).strip() or None,
            "options": options,
            "answer": correct or None,
            "type": QuestionType.MCQ_MULTI.value if len(correct) > 1 else None,
            "explanation": " ".join(explanation).strip() or None,
        }
        result.extend(_collect([(f"{ctx.path}:{lineno}", record)], ctx))
    return result


# Plain text / PDF text layout:  "12. Question" or "Q12 — Question", options "   A. text"
_TXT_Q = re.compile(r"^\s{0,3}(?:Q(?P<qn>\d+)\s*[—–:.-]\s*|(?P<n>\d+)[.)]\s+)(?P<stem>\S.*)$")
_TXT_OPT = re.compile(r"^\s+(?P<id>[A-L])[.)]\s+(?P<text>\S.*)$")
_TXT_ANSWER = re.compile(
    r"^\s*(?:answer|correct answer|réponse)\s*[:：]\s*(?P<ans>[A-L](?:\s*[,;]\s*[A-L])*)\s*$",
    re.I,
)


def parse_text(text: str, ctx: ParseContext) -> ParseResult:
    records: list[tuple[str, dict[str, Any]]] = []
    cur: dict[str, Any] | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        opt = _TXT_OPT.match(line)
        q = None if opt else _TXT_Q.match(line)
        if q:
            cur = {"stem": q.group("stem").strip(), "context": [], "options": []}
            records.append((f"{ctx.path}:{lineno}", cur))
        elif cur is None:
            continue
        elif opt:
            cur["options"].append({"id": opt.group("id"), "text": opt.group("text").strip()})
        elif (ans := _TXT_ANSWER.match(line)) is not None:
            cur["answer"] = [a.strip() for a in re.split(r"[,;]", ans.group("ans"))]
        elif cur["options"] and line.startswith("     "):
            cur["options"][-1]["text"] += " " + line.strip()  # wrapped option line
        elif cur["options"]:
            continue
        elif line.startswith(" "):
            cur["context"].append(line.strip())
        else:
            cur["stem"] += " " + line.strip()
    for _, rec in records:
        rec["context"] = "\n".join(rec["context"]) or None
    return _collect(records, ctx)


def parse_pdf(data: bytes, ctx: ParseContext) -> ParseResult:
    """Extract text from a PDF (only for sources whose licence allows it), then use the text parser."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
    return parse_text(text, ctx)


TextParser = Callable[[str, ParseContext], ParseResult]
PARSERS: dict[str, TextParser] = {
    "json": parse_json,
    "yaml": parse_yaml,
    "yml": parse_yaml,
    "csv": parse_csv,
    "md": parse_markdown,
    "markdown": parse_markdown,
    "txt": parse_text,
}
SUPPORTED_EXTENSIONS = frozenset({*PARSERS, "pdf"})


def parse_bytes(data: bytes, fmt: str, ctx: ParseContext) -> ParseResult:
    fmt = fmt.lower().lstrip(".")
    if fmt == "pdf":
        return parse_pdf(data, ctx)
    parser = PARSERS.get(fmt)
    if parser is None:
        return ParseResult(errors=[{"ref": ctx.path, "error": f"unsupported format: {fmt}"}])
    return parser(data.decode("utf-8-sig", errors="replace"), ctx)
