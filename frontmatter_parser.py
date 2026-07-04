"""Frontmatter-Parser – SSOT (Single Source of Truth) für YAML-Frontmatter.

Vor dem Refactoring gab es **vier** verschiedene Frontmatter-Regex-Parser
in `book_studio.py`, `pre_processor.py`, `yaml_engine.py` (drei Stellen!),
`Sanitizer.py` und `export_manager.py`. Sie parsen leicht unterschiedlich
(BOM, fehlender Schließer, doppelte Starttrenner, CrLf vs. Lf) und sind
nicht untereinander konsistent.

Dieses Modul bündelt die Logik aus `Sanitizer._split_frontmatter` /
`_validate_and_repair_frontmatter` in einer stabilen, gut getesteten API.

API:
    parse(content)                  → FrontmatterParts
    parse_file(path)                → FrontmatterParts
    extract_field(content, key)     → Optional[str]
    validate_and_repair(...)        → (content, changes, is_valid)
    is_yaml_delimiter(line)         → bool

Referenz: .doc/refactoring-master.md, Batch B2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover - PyYAML ist harte Abhängigkeit
    yaml = None  # type: ignore[assignment]


# --- Konstanten -------------------------------------------------------------

FRONTMATTER_DELIMITER = "---"
KEY_VALUE_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:\s*(.*)$")


# --- Hilfsfunktionen --------------------------------------------------------


def is_yaml_delimiter(line: str) -> bool:
    """True, wenn die Zeile ein YAML-Frontmatter-Trenner ist.

    Akzeptiert `---`, `--- `, `---\\r` und ähnliche Whitespace-Varianten,
    aber **nicht** `----` (vier oder mehr Bindestriche, das wäre Pandoc-Setext).
    """
    return line.strip() == FRONTMATTER_DELIMITER


def _detect_newline(content: str) -> str:
    """Erkennt die Zeilenende-Konvention eines Textes."""
    if "\r\n" in content:
        return "\r\n"
    if "\r" in content:
        return "\r"
    return "\n"


# --- Datenklasse ------------------------------------------------------------


@dataclass
class FrontmatterParts:
    """Ergebnis eines Frontmatter-Splits."""

    bom: str = ""
    header: Optional[str] = None
    body: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def has_frontmatter(self) -> bool:
        return self.header is not None

    @property
    def duplicate_opening_count(self) -> int:
        return int(self.meta.get("duplicate_opening_count", 0))

    @property
    def had_closing_delimiter(self) -> bool:
        return bool(self.meta.get("had_closing_delimiter", False))

    def parsed(self) -> dict:
        """Parst den Header als YAML. Liefert `{}` bei leerem/defektem
        Header. Setzt `yaml is None` voraus — Aufrufer sollten das
        vorab prüfen, wenn das ein Fehlerfall ist."""
        if self.header is None:
            return {}
        if yaml is None:
            return {}
        try:
            data = yaml.safe_load(self.header) if self.header.strip() else {}
        except (yaml.YAMLError, ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}


# --- Parser -----------------------------------------------------------------


def parse(content: str) -> FrontmatterParts:
    """Zerlegt Markdown-Text in BOM, Frontmatter-Header, Body und Meta.

    Konsistent mit der bisherigen `Sanitizer._split_frontmatter`:
    - BOM (`\\ufeff`) am Anfang wird separat geliefert.
    - Frontmatter muss am Dateianfang stehen (nach BOM).
    - Doppelte Starttrenner (`---\\n---\\n…`) werden erkannt und gezählt.
    - Fehlender Endtrenner wird via Heuristik (erster Leerabsatz = Body)
      aufgefangen.
    """
    bom = ""
    if content.startswith("\ufeff"):
        bom = "\ufeff"
        content = content[1:]

    if not content.startswith(FRONTMATTER_DELIMITER):
        return FrontmatterParts(bom=bom, body=content)

    lines = content.splitlines(keepends=True)
    if not lines:
        return FrontmatterParts(bom=bom, body=content)

    if lines[0].strip() != FRONTMATTER_DELIMITER:
        return FrontmatterParts(bom=bom, body=content)

    # Doppelte/dreifache Starttrenner konsumieren
    idx = 1
    duplicate_opening_count = 0
    while idx < len(lines) and lines[idx].strip() == FRONTMATTER_DELIMITER:
        duplicate_opening_count += 1
        idx += 1

    closing_idx: Optional[int] = None
    for i in range(idx, len(lines)):
        if is_yaml_delimiter(lines[i]):
            closing_idx = i
            break

    meta = {
        "duplicate_opening_count": duplicate_opening_count,
        "had_closing_delimiter": closing_idx is not None,
    }

    if closing_idx is None:
        # Heuristik: erster Leerabsatz trennt Header von Body
        header_lines = []
        body_lines = []
        in_body = False
        for line in lines[idx:]:
            if not in_body:
                if line.strip() == "":
                    in_body = True
                    continue
                header_lines.append(line)
            else:
                body_lines.append(line)
        return FrontmatterParts(
            bom=bom,
            header="".join(header_lines),
            body="".join(body_lines),
            meta=meta,
        )

    return FrontmatterParts(
        bom=bom,
        header="".join(lines[idx:closing_idx]),
        body="".join(lines[closing_idx + 1:]),
        meta=meta,
    )


def parse_file(path: Path | str) -> FrontmatterParts:
    """Liest eine Datei und parst ihr Frontmatter.

    Liest nur die ersten 64 KiB — für den Header reicht das, und
    gleichzeitig vermeiden wir Speicherprobleme bei riesigen Dateien.
    """
    p = Path(path)
    try:
        with p.open("r", encoding="utf-8") as f:
            content = f.read(65536)
    except (OSError, UnicodeDecodeError):
        return FrontmatterParts()
    return parse(content)


# --- Extraktion einzelner Felder --------------------------------------------


def extract_field(content: str, key: str) -> Optional[str]:
    """Extrahiert den Wert eines Top-Level-YAML-Felds aus dem Frontmatter.

    Ersetzt das bisherige `re.search(r'^title:\\s*...')`-Muster aus
    `yaml_engine.py`. Unterstützt optionale Anführungszeichen und Whitespace.
    """
    parts = parse(content)
    if not parts.has_frontmatter:
        return None
    pattern = re.compile(
        rf"^{re.escape(key)}\s*:\s*[\"']?(.*?)[\"']?\s*$",
        re.MULTILINE,
    )
    match = pattern.search(parts.header or "")
    if not match:
        return None
    return match.group(1).strip()


# --- Validierung / Reparatur -------------------------------------------------


def _salvage_simple_yaml_mapping(header_text: str) -> dict:
    """Defensiver Fallback, falls `yaml.safe_load` scheitert.

    Wird von `validate_and_repair` im `repair`-Modus benutzt, um aus
    einem defekten Block wenigstens `key: value`-Paare zu retten.
    """
    result: dict = {}
    for raw_line in header_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = KEY_VALUE_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        result[key] = value.strip().strip('"').strip("'")
    return result


def validate_and_repair(
    content: str,
    header_mode: str = "repair",
    preserve_style_in_repair: bool = False,
) -> Tuple[str, list[str], bool]:
    """Validiert und repariert das Frontmatter.

    Übernommen aus `Sanitizer._validate_and_repair_frontmatter`. Liefert
    `(content, changes, is_valid)`:
    - `content`: reparierter Text (oder unverändert, je nach Modus)
    - `changes`: Liste der vorgenommenen Änderungen als Klartext-Markierungen
    - `is_valid`: True, wenn der YAML-Block parst

    Modi:
    - `repair`: repariert Struktur und ggf. Inhalt (konservativ)
    - `preserve`: nur Struktur-Fixes (doppelte `---`, fehlender Schließer)
    - `strict`: keine Reparatur; `is_valid=False` blockt das Schreiben
    """
    if header_mode not in ("repair", "preserve", "strict"):
        raise ValueError(f"Unbekannter header_mode: {header_mode}")

    changes: list[str] = []
    is_valid = True

    parts = parse(content)
    if not parts.has_frontmatter:
        return content, changes, is_valid

    newline = _detect_newline(content)

    if parts.duplicate_opening_count > 0:
        changes.append(
            "Frontmatter repariert: Doppelte YAML-Starttrenner auf einen reduziert"
        )
    if not parts.had_closing_delimiter:
        changes.append("Frontmatter repariert: Fehlender YAML-Endtrenner ergänzt")

    parsed_data = None
    yaml_repaired = False
    parse_attempted = False

    if yaml is not None:
        parse_attempted = True
        try:
            parsed_data = yaml.safe_load(parts.header) if (parts.header or "").strip() else {}
        except (yaml.YAMLError, ValueError, TypeError):
            parsed_data = None

    if isinstance(parsed_data, dict):
        if header_mode == "repair":
            if preserve_style_in_repair:
                changes.append(
                    "Frontmatter validiert (repair + preserve-style: Inhalt unverändert)"
                )
                normalized_header = parts.header
            else:
                normalized_header = yaml.safe_dump(
                    parsed_data,
                    allow_unicode=True,
                    sort_keys=False,
                )
                if normalized_header != parts.header:
                    changes.append(
                        "Frontmatter normalisiert (repair: Inhalt neu serialisiert)"
                    )
        else:
            normalized_header = parts.header
            if header_mode != "preserve":
                changes.append("Frontmatter validiert (preserve-mode: Inhalt unverändert)")
    else:
        is_valid = False
        if header_mode == "repair":
            if preserve_style_in_repair:
                changes.append(
                    "CAVEAT: Frontmatter YAML ungültig (repair + preserve-style: unverändert belassen)"
                )
                normalized_header = parts.header
            else:
                salvaged = _salvage_simple_yaml_mapping(parts.header or "")
                if salvaged:
                    normalized_header = yaml.safe_dump(
                        salvaged,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                    yaml_repaired = True
                    changes.append(
                        "Frontmatter repariert: YAML war defekt und wurde konservativ rekonstruiert"
                    )
                else:
                    normalized_header = parts.header
                    changes.append(
                        "Frontmatter repariert: YAML war defekt, Rekonstruktion nicht möglich"
                    )
        elif header_mode == "strict":
            changes.append("STRICT-MODUS: Datei wegen ungültigem Frontmatter nicht geschrieben")
            return content, changes, False
        else:
            normalized_header = parts.header
            changes.append("CAVEAT: Frontmatter erkannt, aber nicht parsebar/reparierbar")

    # Zusammensetzen
    header_text = (normalized_header or "").rstrip("\r\n") + newline
    if not parts.had_closing_delimiter:
        closing = f"---{newline}"
    else:
        closing = f"---{newline}"

    body_text = parts.body
    if not body_text.startswith(("\n", "\r")) and body_text:
        body_text = newline + body_text
    if body_text and not body_text.endswith(("\n", "\r")):
        body_text = body_text + newline

    new_content = (
        parts.bom
        + "---" + newline
        + header_text
        + closing
        + body_text
    )
    if not new_content.endswith(("\n", "\r")):
        new_content = new_content + newline

    if not parse_attempted:
        changes.append("CAVEAT: PyYAML nicht verfügbar — Validierung übersprungen")
        is_valid = False
    _ = yaml_repaired  # derzeit nur dokumentarisch verwendet

    return new_content, changes, is_valid


def repair_hidden_yaml_dividers(content: str) -> Tuple[str, bool]:
    """Ersetzt eigenständige ``---``-Zeilen im Markdown-Body durch ``***``.

    Quarto/Pandoc interpretieren ``---`` als YAML-Frontmatter-Grenze und
    brechen beim Rendern ab. Der Buch-Doktor markiert diese Zeilen als
    kritischen Befund; diese Funktion repariert sie automatisch.
    """
    parts = parse(content)
    if not parts.has_frontmatter:
        return content, False

    newline = _detect_newline(content)
    new_body_lines = []
    changed = False
    for line in parts.body.splitlines():
        if is_yaml_delimiter(line):
            new_body_lines.append("***")
            changed = True
        else:
            new_body_lines.append(line)

    if not changed:
        return content, False

    new_body = newline.join(new_body_lines)
    if parts.body.endswith(("\n", "\r\n", "\r")) and not new_body.endswith(("\n", "\r")):
        new_body += newline

    header_text = (parts.header or "").rstrip("\r\n") + newline
    closing = f"---{newline}"
    body_text = new_body
    if not body_text.startswith(("\n", "\r")) and body_text:
        body_text = newline + body_text

    new_content = parts.bom + "---" + newline + header_text + closing + body_text
    if not new_content.endswith(("\n", "\r")):
        new_content += newline
    return new_content, True


__all__ = [
    "FRONTMATTER_DELIMITER",
    "FrontmatterParts",
    "is_yaml_delimiter",
    "parse",
    "parse_file",
    "extract_field",
    "validate_and_repair",
    "repair_hidden_yaml_dividers",
]
