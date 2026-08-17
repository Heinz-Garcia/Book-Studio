"""German noun extraction for Cover-Schlagwortwolken (spaCy POS) — SSOT.

Kept entirely under ``tools/stylecloud`` so the main app stays free of NLP
imports. Callers pass plain text in and get a noun-only string out.
"""

from __future__ import annotations

import importlib
import sys
from functools import lru_cache
from typing import Any, Iterator

# Universal Dependencies POS tags kept for cover keywords.
NOUN_POS_TAGS: frozenset[str] = frozenset({"NOUN", "PROPN"})

# Default German pipeline (small, fast). Install:
#   python -m spacy download de_core_news_sm
DEFAULT_SPACY_MODEL = "de_core_news_sm"

# spaCy default max is 1_000_000; chunk before that for book-sized inputs.
_CHUNK_CHARS = 80_000


class SpacyNounFilterError(RuntimeError):
    """spaCy or the German model is missing / unusable."""


def _install_hint() -> str:
    exe = sys.executable
    return (
        f'"{exe}" -m pip install spacy\n'
        f'"{exe}" -m spacy download {DEFAULT_SPACY_MODEL}'
    )


@lru_cache(maxsize=2)
def _load_nlp(model_name: str) -> Any:
    """Load and cache a spaCy pipeline (tagger only — no parser/NER)."""
    try:
        spacy = importlib.import_module("spacy")
    except ModuleNotFoundError as exc:
        raise SpacyNounFilterError(
            "spaCy ist nicht installiert (nur für Substantiv-Filter nötig).\n"
            f"Aktuelles Python: {sys.executable}\n"
            f"Bitte ausführen:\n{_install_hint()}"
        ) from exc

    try:
        return spacy.load(model_name, disable=["parser", "ner"])
    except OSError as exc:
        raise SpacyNounFilterError(
            f"spaCy-Modell „{model_name}“ fehlt.\n"
            f"Aktuelles Python: {sys.executable}\n"
            f"Bitte ausführen:\n"
            f'"{sys.executable}" -m spacy download {model_name}'
        ) from exc


def _iter_text_chunks(text: str, chunk_chars: int = _CHUNK_CHARS) -> Iterator[str]:
    """Yield roughly paragraph-aware chunks for long book texts."""
    cleaned = (text or "").strip()
    if not cleaned:
        return
    if len(cleaned) <= chunk_chars:
        yield cleaned
        return
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + chunk_chars, length)
        if end < length:
            split_at = cleaned.rfind("\n", start, end)
            if split_at <= start:
                split_at = cleaned.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        chunk = cleaned[start:end].strip()
        if chunk:
            yield chunk
        start = end


def extract_german_nouns(
    text: str,
    *,
    model: str = DEFAULT_SPACY_MODEL,
    include_proper_nouns: bool = True,
) -> str:
    """Return a space-separated string of German noun lemmas (frequency kept).

    Each noun occurrence is emitted once so ``stylecloud`` / ``word_cloud`` can
    weight by frequency. Empty / non-alpha tokens are dropped.
    """
    source = (text or "").strip()
    if not source:
        return ""

    allowed = NOUN_POS_TAGS if include_proper_nouns else frozenset({"NOUN"})
    nlp = _load_nlp(model)
    nouns: list[str] = []
    for chunk in _iter_text_chunks(source):
        doc = nlp(chunk)
        for token in doc:
            if token.pos_ not in allowed:
                continue
            if token.is_space or token.is_punct or not token.is_alpha:
                continue
            if len(token.text) < 2:
                continue
            lemma = (token.lemma_ or token.text).strip()
            if lemma:
                nouns.append(lemma)

    return " ".join(nouns)


def clear_nlp_cache() -> None:
    """Drop cached spaCy pipelines (tests / model switch)."""
    _load_nlp.cache_clear()
