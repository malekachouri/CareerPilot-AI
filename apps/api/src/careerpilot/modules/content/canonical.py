"""Canonical question format every parser produces, plus normalisation used for deduplication."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from careerpilot.modules.content.models import OPTION_TYPES, QuestionType

DIFFICULTY_WORDS = {
    "beginner": 1,
    "easy": 1,
    "junior": 1,
    "intermediate": 2,
    "medium": 2,
    "mid": 2,
    "advanced": 3,
    "hard": 3,
    "senior": 3,
    "expert": 4,
}


class OptionIn(BaseModel):
    id: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=4000)


class QuestionIn(BaseModel):
    """One question as produced by a parser, the generator or a human. Validated before anything is stored."""

    external_id: str | None = Field(default=None, max_length=200)
    type: QuestionType = QuestionType.MCQ_SINGLE
    stem: str = Field(min_length=3, max_length=8000)
    context: str | None = Field(default=None, max_length=20000)
    options: list[OptionIn] = Field(default_factory=list, max_length=12)
    answer: list[str] | None = None  # option ids; None when the source gives no key
    explanation: str | None = Field(default=None, max_length=8000)
    distractor_explanations: dict[str, str] = Field(default_factory=dict)
    difficulty: int = Field(default=2, ge=1, le=4)
    categories: list[str] = Field(default_factory=list, max_length=8)
    companies: list[str] = Field(default_factory=list, max_length=8)
    language: str = Field(default="en", max_length=8)
    time_limit_s: int | None = Field(default=None, ge=5, le=3600)
    source_ref: str | None = Field(default=None, max_length=500)

    @field_validator("difficulty", mode="before")
    @classmethod
    def _difficulty_words(cls, v: object) -> object:
        if isinstance(v, str):
            word = v.strip().lower()
            if word in DIFFICULTY_WORDS:
                return DIFFICULTY_WORDS[word]
            if word.isdigit():
                return int(word)
        return v

    @field_validator("answer", mode="before")
    @classmethod
    def _answer_as_list(cls, v: object) -> object:
        if isinstance(v, str):
            parts = [p.strip() for p in re.split(r"[,;| ]+", v) if p.strip()]
            return parts or None
        return v

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("option ids must be unique")
        texts = [option_key(o.text) for o in self.options]
        if len(set(texts)) != len(texts):
            raise ValueError("options must be distinct")
        if self.type in OPTION_TYPES and len(self.options) < 2:
            raise ValueError(f"type {self.type.value} needs at least 2 options")
        if self.answer is not None:
            unknown = [a for a in self.answer if a not in ids]
            if unknown:
                raise ValueError(f"answer refers to unknown options: {unknown}")
            if not self.answer:
                self.answer = None
            elif (
                self.type
                in {
                    QuestionType.MCQ_SINGLE,
                    QuestionType.TRUE_FALSE,
                    QuestionType.TRUE_FALSE_UNDETERMINED,
                    QuestionType.SCENARIO,
                }
                and len(self.answer) != 1
            ):
                raise ValueError(f"type {self.type.value} needs exactly one correct option")
        if self.type == QuestionType.SURVEY:
            self.answer = None  # questionnaires are never scored
        return self


_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, punctuation and extra whitespace: robust key for duplicate detection."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _PUNCT.sub(" ", text.lower())
    return _WS.sub(" ", text).strip()


def option_key(text: str) -> str:
    """Options keep symbols and case: `$` vs `#`, `{foo}` vs `{{foo}}`, `-b` vs `-B` are different."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


def content_hash(q: QuestionIn) -> str:
    """Same stem + same set of options (any order) = same question."""
    parts = [normalize_text(q.stem), normalize_text(q.context or "")]
    parts += sorted(option_key(o.text) for o in q.options)
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
