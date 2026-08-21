"""Noun extraction for Cover-Schlagwortwolken (spaCy POS) — SSOT.

Language-aware: German and English models. When „Nur Substantive“ is on,
function words must not leak through — even if the wrong spaCy model
mis-tags foreign text as NOUN/PROPN.
"""

from __future__ import annotations

import importlib
import re
import sys
from functools import lru_cache
from typing import Any, Iterator, Literal

from tools.stylecloud.stopwords_de import GERMAN_STOPWORDS

# Universal Dependencies POS tags kept for cover keywords.
NOUN_POS_TAGS: frozenset[str] = frozenset({"NOUN", "PROPN"})

DEFAULT_SPACY_MODEL = "de_core_news_sm"
ENGLISH_SPACY_MODEL = "en_core_web_sm"

# spaCy default max is 1_000_000; chunk before that for book-sized inputs.
_CHUNK_CHARS = 80_000

# Compact English function-word set (WordCloud-style) — blocks DE-model-on-EN leaks.
ENGLISH_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
        # Frequent prompt noise
        "also",
        "get",
        "got",
        "just",
        "like",
        "make",
        "need",
        "please",
        "really",
        "will",
    }
)

_FUNCTION_STOPWORDS: frozenset[str] = frozenset(
    w.casefold() for w in (GERMAN_STOPWORDS | ENGLISH_STOPWORDS)
)

_DE_HINTS = frozenset(
    {
        "der",
        "die",
        "das",
        "und",
        "ich",
        "nicht",
        "mit",
        "sich",
        "auf",
        "für",
        "eine",
        "einem",
        "einer",
        "wie",
        "auch",
        "oder",
        "aber",
        "wenn",
        "bei",
        "nach",
        "wird",
        "sind",
        "kann",
        "werden",
        "haben",
        "wurde",
        "über",
    }
)
_EN_HINTS = frozenset(
    {
        "the",
        "and",
        "to",
        "of",
        "in",
        "is",
        "for",
        "that",
        "with",
        "you",
        "are",
        "this",
        "from",
        "have",
        "what",
        "how",
        "can",
        "does",
        "do",
        "should",
        "if",
        "my",
        "or",
        "at",
        "when",
        "your",
        "will",
        "would",
        "could",
    }
)

TextLanguage = Literal["de", "en"]


class SpacyNounFilterError(RuntimeError):
    """spaCy or the required language model is missing / unusable."""


def _install_hint(model: str) -> str:
    exe = sys.executable
    return f'"{exe}" -m pip install spacy\n"{exe}" -m spacy download {model}'


@lru_cache(maxsize=4)
def _load_nlp(model_name: str) -> Any:
    """Load and cache a spaCy pipeline (tagger only — no parser/NER)."""
    try:
        spacy = importlib.import_module("spacy")
    except ModuleNotFoundError as exc:
        raise SpacyNounFilterError(
            "spaCy ist nicht installiert (nur für Substantiv-Filter nötig).\n"
            f"Aktuelles Python: {sys.executable}\n"
            f"Bitte ausführen:\n{_install_hint(model_name)}"
        ) from exc

    try:
        return spacy.load(model_name, disable=["parser", "ner"])
    except OSError as exc:
        raise SpacyNounFilterError(
            f"spaCy-Modell „{model_name}“ fehlt.\n"
            f"Aktuelles Python: {sys.executable}\n"
            f"Bitte ausführen:\n{_install_hint(model_name)}"
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


def detect_text_language(text: str) -> TextLanguage:
    """Heuristic DE vs EN from common function-word hits (no extra dependency)."""
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß']+", (text or "").casefold())
    if not tokens:
        return "de"
    sample = tokens[:4000]
    de_hits = sum(1 for t in sample if t in _DE_HINTS)
    en_hits = sum(1 for t in sample if t in _EN_HINTS)
    if en_hits > de_hits:
        return "en"
    return "de"


def model_for_language(lang: TextLanguage) -> str:
    return ENGLISH_SPACY_MODEL if lang == "en" else DEFAULT_SPACY_MODEL


def _is_kept_noun_lemma(lemma: str) -> bool:
    key = lemma.casefold().strip()
    if len(key) < 2:
        return False
    if key in _FUNCTION_STOPWORDS:
        return False
    return True


def extract_nouns(
    text: str,
    *,
    language: TextLanguage | None = None,
    model: str | None = None,
    include_proper_nouns: bool = True,
) -> str:
    """Return space-separated noun lemmas (frequency kept).

    Always strips DE+EN function stopwords after POS filtering so „Nur
    Substantive“ stays reliable for Freie Form / Cover-dicht / every path.
    """
    source = (text or "").strip()
    if not source:
        return ""

    lang = language or detect_text_language(source)
    model_name = model or model_for_language(lang)
    allowed = NOUN_POS_TAGS if include_proper_nouns else frozenset({"NOUN"})
    nlp = _load_nlp(model_name)
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
            if lemma and _is_kept_noun_lemma(lemma):
                nouns.append(lemma)

    return " ".join(nouns)


def extract_german_nouns(
    text: str,
    *,
    model: str | None = None,
    include_proper_nouns: bool = True,
) -> str:
    """Back-compat: language-aware noun extract (DE/EN). Prefer ``extract_nouns``."""
    return extract_nouns(
        text,
        model=model,
        include_proper_nouns=include_proper_nouns,
    )


def clear_nlp_cache() -> None:
    """Drop cached spaCy pipelines (tests / model switch)."""
    _load_nlp.cache_clear()
