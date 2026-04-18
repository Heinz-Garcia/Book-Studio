import argparse
import re
import unicodedata
import importlib
import logging
import sys
import subprocess
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    tomllib = importlib.import_module("tomllib")
except ModuleNotFoundError:
    try:
        tomllib = importlib.import_module("tomli")
    except ModuleNotFoundError:
        tomllib = None

try:
    yaml = importlib.import_module("yaml")
except ModuleNotFoundError:
    yaml = None

# Dieses Skript durchsucht rekursiv ein Verzeichnis nach Markdown-Dateien,
# wendet Bereinigungen für Quarto/Pandoc/Typst an und überschreibt die Originaldateien.
# Die YAML-Frontmatter (---) bleiben absolut unangetastet, AUßER sie sind fehlerhaft gedoppelt!
# Es wird automatisch ein Logfile im Zielverzeichnis erstellt.

# Statische Ersetzungen (strukturelle Fehler und Typst-inkompatible Steuerzeichen)
# HINWEIS: Um Parser-Fehler zu vermeiden, werden Backticks als Unicode \x60 geschrieben.
REPLACEMENTS = {
    "## ## ": ("## ", "Doppelte Überschriften-Tags repariert"),
    "\x60\x60\x60text\n\n\x60\x60\x60\n": ("", "Leeren Code-Block (LF) entfernt"),
    "\x60\x60\x60text\r\n\r\n\x60\x60\x60\r\n": (
        "",
        "Leeren Code-Block (CRLF) entfernt",
    ),
    "\u200b": ("", "Zero-Width Space entfernt"),
    "\u00ad": ("", "Soft Hyphen entfernt"),
    "\u00a0": (" ", "Non-Breaking Space durch Leerzeichen ersetzt"),
    "\ufeff": ("", "BOM (Byte Order Mark) entfernt"),
}

# Weitere Unicode-Steuerzeichen, die in Quarto/Pandoc -> Typst oft Probleme verursachen.
UNICODE_STRIP_RANGES = [
    (0x200B, 0x200F),  # Zero-width + LRM/RLM
    (0x202A, 0x202E),  # bidi embedding/override
    (0x2060, 0x206F),  # word joiner + directional isolates + invisibles
]

DIV_OPEN_PATTERN = re.compile(r"^\s*:::+\s*\{[^}]+\}\s*$")
DIV_CLOSE_PATTERN = re.compile(r"^\s*:::+\s*$")
ANSWER_DIV_OPEN_PATTERN = re.compile(r"^\s*:::+\s*\{[^}]*\B\.answer\b[^}]*\}\s*$")


def _load_config(config_path=None):
    """Lädt die Sanitizer-Konfiguration aus TOML-Datei."""
    if config_path is None:
        config_path = Path(__file__).parent / "sanitizer_config.toml"

    _defaults = {
        "tags": {
            "C": ".author",
            "Q": ".Inquirer",
            "A": ".answer",
            "MONO": ".monospace",
        },
        "features": {
            "normalize_headings": True,
            "convert_bold_tags": True,
            "remove_double_delimiters": True,
            "convert_inline_tags": True,
            "repair_encoding": True,
            "prompt_unclosed_answer_div": False,
            "only_unclosed_answer_div_check": False,
            "preserve_frontmatter_style_in_repair": True,
        },
        "logging": {"verbose": True},
    }

    if not config_path.exists():
        logger.warning("Sanitizer-Config nicht gefunden, nutze Defaults: %s", config_path)
        return _defaults

    if tomllib is None:
        logger.warning("tomllib/tomli nicht verfügbar, Sanitizer nutzt Defaults")
        return _defaults

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        return config
    except (OSError, ValueError) as error:
        logger.warning("Sanitizer-Config konnte nicht gelesen werden (%s): %s", config_path, error)
        return _defaults


def _repair_encoding(content):
    """Repariert Mojibake: UTF-8-Text, der als Windows-1252 (CP1252) gelesen/gespeichert wurde.
    Beispiel: 'Ã¤' -> 'ä', 'â€ž' -> '„'
    Gibt (content, changes) zurück. Wenn keine Reparatur möglich, bleibt content unverändert."""
    changes = []
    try:
        repaired = content.encode("cp1252").decode("utf-8")
        if repaired != content:
            changes.append("Encoding-Fehler repariert (UTF-8 Mojibake/CP1252 behoben)")
            return repaired, changes
    except (UnicodeEncodeError, UnicodeDecodeError) as error:
        # Kein Mojibake oder gemischtes Encoding – unverändert lassen
        logger.debug("Encoding-Reparatur übersprungen: %s", error)
    return content, changes


def _remove_double_delimiters(body):
    """Entfernt doppelte --- Trennlinien am Anfang des Body.
    Der Body kann direkt mit --- oder mit \\n--- starten, je nach Dateistruktur."""
    changes = []

    # Alle vier möglichen Varianten am Body-Anfang:
    # 1. Kein Leerzeichen davor, LF:    "---\n..."
    # 2. Kein Leerzeichen davor, CRLF:  "---\r\n..."
    # 3. Leerzeile davor, LF:           "\n---\n..."
    # 4. Leerzeile davor, CRLF:         "\r\n---\r\n..."
    for prefix, triple_dash in [
        ("", "---\n"),
        ("", "---\r\n"),
        ("\n", "---\n"),
        ("\r\n", "---\r\n"),
    ]:
        candidate = prefix + triple_dash
        if body.startswith(candidate):
            body = prefix + body[len(candidate) :]
            changes.append("Doppelte '---' Trennlinie nach Frontmatter gelöscht")
            break

    return body, changes


def _convert_bold_tags(body, config):
    """Konvertiert **[TAG]: Text.** Blöcke zu ::: {.class} ... ::: Divs.
    Handhabt auch blockquote-prefixed Varianten: > **[TAG]: Text**
    Der Blockquote-Marker > wird dabei entfernt."""
    changes = []
    tags = config.get("tags", {})

    for tag, div_class in tags.items():
        # Regex: optional blockquote-prefix (wird ignoriert/entfernt), dann bold-tag mit Text.
        # ^ = Zeilenanfang
        # [ \t]* = Optional führendes Whitespace (z.B. versehentliche Einrückungen)
        # (?:>[ \t]*)? = Optional Blockquote-Prefix > (wird entfernt)
        # \*\*\[{tag}\]:? = **[TAG]: oder **[TAG]:
        # \s* = Whitespace nach Doppelpunkt
        # ([^\n]*?) = Text bis Zeilenende (non-greedy, Gruppe 1)
        # \*\*\s*$ = **-Ende und Zeilenende
        pattern = re.compile(
            rf"^[ \t]*(?:>[ \t]*)?\*\*\[{tag}\]:?\s*([^\n]*?)\*\*\s*$",
            re.IGNORECASE | re.MULTILINE,
        )

        if pattern.search(body):
            # Factory-Funktion, um die Closure korrekt zu binden
            def make_replacer(cls_name):
                def replacer(m):
                    text = m.group(1).strip()
                    return f"::: {{{cls_name}}}\n{text}\n:::"

                return replacer

            body = pattern.sub(make_replacer(div_class), body)
            changes.append(f"**[{tag}]:** Blöcke zu ::: {{{div_class}}} konvertiert")

    return body, changes


def _convert_inline_tags(body, config):
    """Konvertiert [TAG]: Absatzblöcke robust zu ::: {.class} ... ::: Divs."""
    changes = []
    tags = config.get("tags", {})

    for tag, div_class in tags.items():
        # Strikt: nur Zeilenstart (optional mit Blockquote) und verpflichtendem Doppelpunkt.
        pattern = re.compile(
            rf"^(?P<prefix>(?:>[ \t]*)*)\[{tag}\]:[ \t]*(?P<text>.*)$",
            re.IGNORECASE,
        )

        lines = body.splitlines(keepends=True)
        i = 0
        out = []
        changed_for_tag = False

        while i < len(lines):
            line = lines[i]
            m = pattern.match(line.rstrip("\r\n"))
            if not m:
                out.append(line)
                i += 1
                continue

            para_lines = [m.group("text")]
            i += 1
            while i < len(lines):
                next_line = lines[i]
                raw = next_line.rstrip("\r\n")
                if raw.strip() == "":
                    break
                # Entfernt nur führende Blockquote-Pfeile im laufenden Absatz.
                raw = re.sub(r"^>[ \t]*", "", raw)
                para_lines.append(raw)
                i += 1

            block_text = "\n".join(x.strip() for x in para_lines).strip()
            out.append(f"::: {{{div_class}}}\n{block_text}\n:::")
            changed_for_tag = True

            # Leerzeile nach Absatz unverändert übernehmen.
            if i < len(lines) and lines[i].strip() == "":
                out.append(lines[i])
                i += 1

        if changed_for_tag:
            body = "".join(out)
            changes.append(f"[{tag}]-Tags in ::: {{{div_class}}} konvertiert")

    return body, changes


def _normalize_headings(body):
    """
    Normalisiert Überschriftsebenen: erste Ebene wird #, zweite ##, etc.
    Beispiel: ##, ###, #### wird zu #, ##, ###
    """
    changes = []
    lines = body.splitlines(keepends=True)
    heading_levels_found = {}

    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.+)$", line)
        if m:
            original_level = len(m.group(1))
            content = m.group(2)

            if original_level not in heading_levels_found:
                heading_levels_found[original_level] = len(heading_levels_found) + 1

            new_level = heading_levels_found[original_level]
            new_hashes = "#" * new_level
            lines[i] = f"{new_hashes} {content}\n"

    if heading_levels_found:
        for orig, norm in sorted(heading_levels_found.items()):
            changes.append(
                f"Überschriftsebene {'#' * orig} -> {'#' * norm} normalisiert"
            )

    body = "".join(lines)
    return body, changes


def _detect_newline(text):
    if "\r\n" in text:
        return "\r\n"
    return "\n"


def _is_yaml_delimiter(line):
    return line.strip() in {"---", "..."}


def _split_frontmatter(content):
    """
    Trennt Frontmatter vom Body.
    Erkennt Frontmatter nur am Dateianfang (optional mit BOM).
    """
    bom = ""
    if content.startswith("\ufeff"):
        bom = "\ufeff"
        content = content[1:]

    if not content.startswith("---"):
        return bom, None, None, content

    lines = content.splitlines(keepends=True)
    if not lines:
        return bom, None, None, content

    first = lines[0].strip()
    if first != "---":
        return bom, None, None, content

    idx = 1
    duplicate_opening_count = 0
    while idx < len(lines) and lines[idx].strip() == "---":
        duplicate_opening_count += 1
        idx += 1

    closing_idx = None
    for i in range(idx, len(lines)):
        if _is_yaml_delimiter(lines[i]):
            closing_idx = i
            break

    if closing_idx is None:
        # Heuristik: Wenn der Endtrenner fehlt, endet der Header meist am ersten Leerabsatz.
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

        header_text = "".join(header_lines)
        body_text = "".join(body_lines)
        has_closing = False
    else:
        header_text = "".join(lines[idx:closing_idx])
        body_text = "".join(lines[closing_idx + 1 :])
        has_closing = True

    meta = {
        "duplicate_opening_count": duplicate_opening_count,
        "had_closing_delimiter": has_closing,
    }
    return bom, header_text, body_text, meta


def _salvage_simple_yaml_mapping(header_text):
    """Ein defensiver Fallback, falls YAML nicht parsebar ist."""
    result = {}
    for raw_line in header_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        result[key] = value.strip().strip('"').strip("'")
    return result


def _validate_and_repair_frontmatter(
    content, header_mode="repair", preserve_style_in_repair=False
):
    """
    Repariert/validiert Frontmatter-Blöcke robust:
    - doppelte Starttrenner werden auf einen reduziert
    - fehlender Endtrenner wird ergänzt
    - YAML wird geparst; im repair-Mode bei Bedarf konservativ rekonstruiert
    - im preserve-Mode bleibt Header-Inhalt unverändert (nur Struktur-Fixes)
    """
    changes = []
    is_valid = True

    bom, header_text, body_text, meta = _split_frontmatter(content)
    if header_text is None:
        return content, changes, is_valid

    newline = _detect_newline(content)

    if meta["duplicate_opening_count"] > 0:
        changes.append(
            "Frontmatter repariert: Doppelte YAML-Starttrenner auf einen reduziert"
        )

    if not meta["had_closing_delimiter"]:
        changes.append("Frontmatter repariert: Fehlender YAML-Endtrenner ergänzt")

    parsed_data = None
    yaml_repaired = False
    parse_attempted = False

    if yaml is not None:
        parse_attempted = True
        try:
            parsed_data = yaml.safe_load(header_text) if header_text.strip() else {}
        except (yaml.YAMLError, ValueError, TypeError):
            parsed_data = None

    if isinstance(parsed_data, dict):
        if header_mode == "repair":
            if preserve_style_in_repair:
                normalized_header = header_text
                changes.append(
                    "Frontmatter validiert (repair + preserve-style: Inhalt unverändert)"
                )
            else:
                normalized_header = (
                    yaml.safe_dump(
                        parsed_data,
                        allow_unicode=True,
                        sort_keys=False,
                        default_flow_style=False,
                    )
                    if yaml is not None
                    else header_text
                )
                yaml_repaired = True
        else:
            normalized_header = header_text
            changes.append("Frontmatter validiert (preserve-mode: Inhalt unverändert)")
    else:
        fallback_data = _salvage_simple_yaml_mapping(header_text)
        if fallback_data and header_mode == "repair":
            if preserve_style_in_repair:
                normalized_header = header_text
                is_valid = False
                changes.append(
                    "CAVEAT: Frontmatter YAML ungültig (repair + preserve-style: unverändert belassen)"
                )
            elif yaml is not None:
                normalized_header = yaml.safe_dump(
                    fallback_data,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
                yaml_repaired = True
                changes.append(
                    "Frontmatter repariert: YAML war defekt und wurde konservativ rekonstruiert"
                )
            else:
                normalized_header = "".join(
                    f"{k}: {v}{newline}" for k, v in fallback_data.items()
                )
                yaml_repaired = True
                changes.append(
                    "Frontmatter repariert: YAML war defekt und wurde konservativ rekonstruiert"
                )
        elif fallback_data and header_mode == "preserve":
            normalized_header = header_text
            is_valid = False
            changes.append(
                "CAVEAT: Frontmatter YAML ungültig (preserve-mode: unverändert belassen)"
            )
        else:
            normalized_header = header_text
            is_valid = False
            changes.append(
                "CAVEAT: Frontmatter erkannt, aber nicht parsebar/reparierbar"
            )

    if not parse_attempted and header_text.strip():
        # Ohne YAML-Library kann nur begrenzt validiert werden.
        fallback_data = _salvage_simple_yaml_mapping(header_text)
        if not fallback_data:
            is_valid = False
            changes.append(
                "CAVEAT: YAML-Validierung nicht möglich (PyYAML fehlt, Header verdächtig)"
            )

    if yaml_repaired and not changes:
        # Kein struktureller Defekt, aber Header wurde erfolgreich validiert/normalisiert.
        changes.append("Frontmatter validiert")

    normalized_header = normalized_header.rstrip("\r\n")
    rebuilt = f"{bom}---{newline}{normalized_header}{newline}---{newline}{body_text}"
    return rebuilt, changes, is_valid


def _strip_problematic_unicode_controls(content):
    removed = {}

    def should_remove(ch):
        cp = ord(ch)
        in_explicit_range = any(
            start <= cp <= end for start, end in UNICODE_STRIP_RANGES
        )
        # Zusätzliche unsichtbare Controls außerhalb klassischer Newlines/Tabs.
        is_control = unicodedata.category(ch) in {"Cf", "Cc"} and ch not in {
            "\n",
            "\r",
            "\t",
        }
        return in_explicit_range or is_control

    out = []
    for ch in content:
        if should_remove(ch):
            removed[ch] = removed.get(ch, 0) + 1
            continue
        out.append(ch)

    if not removed:
        return content, []

    messages = []
    for ch, count in sorted(removed.items(), key=lambda x: ord(x[0])):
        cp = ord(ch)
        name = unicodedata.name(ch, "UNNAMED")
        messages.append(f"Unicode-Control entfernt: U+{cp:04X} ({name}) x{count}")

    return "".join(out), messages


def _split_for_processing(content):
    """
    Liefert strikt typisierte Teile für die Verarbeitung.
    Rückgabe: (has_frontmatter, bom, header, body, newline)
    """
    bom, header_text, body_text, _meta = _split_frontmatter(content)
    newline = _detect_newline(content)

    if header_text is None:
        return False, "", "", content, newline

    return True, bom, header_text, body_text or "", newline


def _find_unclosed_answer_divs(body):
    """Findet ungeschlossene ::: {.answer}-Divs in einem Markdown-Body."""
    stack = []

    for line_number, line in enumerate(body.splitlines(), start=1):
        if DIV_CLOSE_PATTERN.match(line):
            if stack:
                stack.pop()
            continue

        if DIV_OPEN_PATTERN.match(line):
            stack.append(
                {
                    "is_answer": bool(ANSWER_DIV_OPEN_PATTERN.match(line)),
                    "line_number": line_number,
                }
            )

    return [entry for entry in stack if entry["is_answer"]]


def _prompt_and_reveal_file(filepath, unclosed_entries):
    """Warnt interaktiv und markiert betroffene Datei im Windows Explorer."""
    line_numbers = ", ".join(str(item["line_number"]) for item in unclosed_entries)
    print("\n[WARNUNG] Ungeschlossener ::: {.answer}-Block erkannt!")
    print(f"Datei: {filepath}")
    print(f"Betroffene Zeile(n) im Body: {line_numbers}")

    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["explorer", "/select,", str(Path(filepath).resolve())], check=False
            )
            print("Datei wurde im Windows Explorer markiert.")
        except OSError as error:
            print(f"Explorer konnte nicht geöffnet werden: {error}")

    try:
        input("Bitte Datei prüfen und mit Enter fortfahren...")
    except EOFError:
        # Nicht-interaktive Umgebungen dürfen weiterlaufen.
        print("Hinweis: Nicht-interaktive Umgebung erkannt – fortgesetzt ohne Eingabe.")


def sanitize_file(filepath, header_mode="repair"):
    """Liest eine Datei ein, wendet Bereinigungen an und liefert Ergebnisdetails zurück."""
    changes_made = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # -1. Encoding-Reparatur VOR allem anderen (betrifft Header + Body gleichmäßig)
        config = _load_config()
        features = config.get("features", {})

        if features.get("only_unclosed_answer_div_check", False):
            _has_frontmatter, _bom, _header_text, body, _newline = _split_for_processing(
                content
            )
            unclosed_answer_divs = _find_unclosed_answer_divs(body)
            if unclosed_answer_divs:
                changes_made.append(
                    "WARNUNG: Ungeschlossener ::: {.answer}-Block erkannt"
                )
                if features.get("prompt_unclosed_answer_div", False):
                    _prompt_and_reveal_file(filepath, unclosed_answer_divs)
            return {"changes": changes_made, "written": False, "skipped": False}

        if features.get("repair_encoding", True):
            content, enc_changes = _repair_encoding(content)
            changes_made.extend(enc_changes)

        # 0. Frontmatter zuerst robust validieren/reparieren.
        content, fm_changes, frontmatter_valid = _validate_and_repair_frontmatter(
            content,
            header_mode=header_mode,
            preserve_style_in_repair=features.get(
                "preserve_frontmatter_style_in_repair", True
            ),
        )
        changes_made.extend(fm_changes)

        if header_mode == "strict" and not frontmatter_valid:
            changes_made.append(
                "STRICT-MODUS: Datei wegen ungültigem Frontmatter nicht geschrieben"
            )
            return {"changes": changes_made, "written": False, "skipped": True}

        # Danach strikt trennen: Nur der Body wird mit Sanitizer-Regeln bearbeitet.
        # Der Frontmatter-Block bleibt (abseits der Reparatur oben) unverändert.
        has_frontmatter, bom, header_text, body, newline = _split_for_processing(
            content
        )

        if features.get("prompt_unclosed_answer_div", False):
            unclosed_answer_divs = _find_unclosed_answer_divs(body)
            if unclosed_answer_divs:
                changes_made.append(
                    "WARNUNG: Ungeschlossener ::: {.answer}-Block erkannt"
                )
                _prompt_and_reveal_file(filepath, unclosed_answer_divs)

        if features.get("remove_double_delimiters"):
            body, dd_changes = _remove_double_delimiters(body)
            changes_made.extend(dd_changes)
        # 1. Statische Ersetzungen anwenden
        for search_string, (replace_string, log_message) in REPLACEMENTS.items():
            if search_string in body:
                body = body.replace(search_string, replace_string)
                changes_made.append(log_message)

        # 1b. Erweiterte Bereinigung unsichtbarer/problematischer Unicode-Steuerzeichen
        body, unicode_changes = _strip_problematic_unicode_controls(body)
        changes_made.extend(unicode_changes)

        if features.get("normalize_headings"):
            body, heading_changes = _normalize_headings(body)
            changes_made.extend(heading_changes)

        if features.get("convert_bold_tags"):
            body, bold_changes = _convert_bold_tags(body, config)
            changes_made.extend(bold_changes)

        # 2. Dynamische Ersetzungen per Regex (HTML Tags)
        if re.search(r"<(\d+)", body):
            body = re.sub(r"<(\d+)", r"< \1", body)
            changes_made.append("Spitze Klammern vor Zahlen maskiert (HTML-Fix)")

        # 3. Inline-Tags ([C]:, [Q]:, [A]:, [MONO]:) in Quarto-Div-Fences konvertieren.
        if features.get("convert_inline_tags", True):
            body, inline_changes = _convert_inline_tags(body, config)
            changes_made.extend(inline_changes)

        # 4. Quarto Div-Fences für ```text Blöcke (analog zu MONO)
        text_block_pattern = r"\x60\x60\x60text[ \t]*\r?\n(.*?)\r?\n\x60\x60\x60"
        if re.search(text_block_pattern, body, flags=re.DOTALL):
            body = re.sub(
                text_block_pattern,
                r"::: {.monospace}\n\1\n:::",
                body,
                flags=re.DOTALL,
            )
            changes_made.append(
                "Code-Blöcke (text) in ::: {.monospace} Div-Fences konvertiert"
            )

        # 5. Quarto Callout-Boxen für [BOX: ...]
        if re.search(r"^::::?\s*\[BOX:\s*(.*?)\]", body, flags=re.MULTILINE):
            body = re.sub(
                r"^::::?\s*\[BOX:\s*(.*?)\]",
                r'::: {.callout-note title="\1"}',
                body,
                flags=re.MULTILINE,
            )
            changes_made.append(
                "BOX-Tags in Quarto Callouts (.callout-note) konvertiert"
            )

        if has_frontmatter:
            normalized_header = header_text.rstrip("\r\n")
            content = f"{bom}---{newline}{normalized_header}{newline}---{newline}{body}"
        else:
            content = body

        # Nur neu speichern, wenn sich tatsächlich etwas geändert hat
        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return {"changes": changes_made, "written": True, "skipped": False}

        return {"changes": changes_made, "written": False, "skipped": False}

    except (OSError, UnicodeError, ValueError) as e:
        print(f"Fehler beim Bearbeiten von '{filepath}': {e}")
        return {
            "changes": [f"FEHLER beim Lesen/Schreiben: {e}"],
            "written": False,
            "skipped": True,
        }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Bereinigt rekursiv Markdown-Dateien fuer eine Quarto (pandoc) -> typst Pipeline, "
            "repariert optional Frontmatter und erstellt ein Logfile."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
        epilog=(
            "\n"
            "Ausfuehrliche Beispiele:\n"
            "  python Sanitizer.py <ordner> --header-mode repair\n"
            "    - Empfohlen fuer Standardlaeufe.\n"
            "    - Frontmatter wird validiert und bei Defekten rekonstruiert.\n"
            "    - Body wird sanitiziert (Typst-/Parser-problematische Zeichen, Marker-Konvertierung).\n"
            "\n"
            "  python Sanitizer.py <ordner> --header-mode preserve\n"
            "    - Frontmatter-Inhalt bleibt unveraendert.\n"
            "    - Nur strukturelle Frontmatter-Reparaturen (z. B. fehlender Endtrenner) sind erlaubt.\n"
            "    - Bei ungueltigem YAML wird ein CAVEAT geloggt.\n"
            "\n"
            "  python Sanitizer.py <ordner> --header-mode strict\n"
            "    - Wenn Frontmatter ungueltig ist, wird die Datei NICHT geschrieben.\n"
            "    - Die Datei wird als UEBERSPRUNGEN protokolliert.\n"
            "\n"
            "Hinweise:\n"
            "  - Hilfe aufrufen mit: -h, --help oder -help\n"
            "  - PyYAML ist Pflicht: pip install pyyaml\n"
            "  - Ausgabe-Log: sanitizer_log.txt im Zielordner\n"
        ),
    )
    parser.add_argument(
        "-h",
        "--help",
        "-help",
        action="help",
        help="Zeigt diese Hilfe mit Erklaerungen und Beispielen an.",
    )
    parser.add_argument(
        "directory", help="Der Pfad zum Verzeichnis, das durchsucht werden soll."
    )
    parser.add_argument(
        "--header-mode",
        choices=["repair", "preserve", "strict"],
        default="repair",
        help=(
            "Steuert die Frontmatter-Behandlung: "
            "repair = validieren + ggf. rekonstruieren/normalisieren, "
            "preserve = nur validieren, Header-Inhalt unverändert lassen, "
            "strict = bei ungültigem Header nicht schreiben."
        ),
    )
    args = parser.parse_args()

    if yaml is None:
        print("Fehler: PyYAML ist erforderlich, aber nicht installiert.")
        print("Installiere es mit: pip install pyyaml")
        sys.exit(2)

    target_dir = Path(args.directory)

    if not target_dir.is_dir():
        print(
            f"Fehler: Das angegebene Verzeichnis '{target_dir}' existiert nicht oder ist kein Ordner."
        )
        return

    # =========================================================================
    # NEU: INTELLIGENTER ORDNER-SCHUTZ
    # =========================================================================
    if (target_dir / "_quarto.yml").exists() and (target_dir / "content").exists():
        scan_dir = target_dir / "content"
        print(f"📚 Book Studio Projekt erkannt! Begrenze Scan strikt auf: {scan_dir.relative_to(target_dir)}\\")
    else:
        scan_dir = target_dir

    print(f"Durchsuche '{scan_dir}' und alle Unterordner nach .md-Dateien...")

    total_files = 0
    changed_files = 0
    skipped_files = 0
    warning_files = 0

    log_path = target_dir / "sanitizer_log.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write("=== SANITIZER LOG ===\n")
        log_file.write(f"Datum/Zeit: {timestamp}\n")
        log_file.write(f"Basis-Verzeichnis: {target_dir.absolute()}\n")
        log_file.write(f"Scan-Verzeichnis: {scan_dir.absolute()}\n") # <-- NEU: Protokolliert echten Scan-Pfad
        log_file.write("=====================\n\n")

        # HIER WIRD JETZT scan_dir STATT target_dir VERWENDET
        for md_file in scan_dir.rglob("*.md"):
            
            # NEU: HARDCORE BLACKLIST FÜR PIPELINE-ORDNER
            if any(forbidden in md_file.parts for forbidden in ['.backups', 'export', 'processed', '.venv', '.git']):
                continue

            total_files += 1
            result = sanitize_file(md_file, header_mode=args.header_mode)
            changes = result["changes"]
            written = result["written"]
            skipped = result["skipped"]

            has_answer_warning = any(
                "Ungeschlossener ::: {.answer}" in c for c in changes
            )

            if written:
                changed_files += 1
                rel_path = md_file.relative_to(target_dir)
                print(f"[BEREINIGT] {rel_path.name} ({len(changes)} Änderungen)")
                log_file.write(f"Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")
            elif skipped:
                skipped_files += 1
                rel_path = md_file.relative_to(target_dir)
                print(f"[ÜBERSPRUNGEN] {rel_path.name} ({len(changes)} Hinweise)")
                log_file.write(f"Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")
            elif has_answer_warning:
                warning_files += 1
                rel_path = md_file.relative_to(target_dir)
                print(f"[WARNUNG] {rel_path.name} — ungeschlossener ::: {{.answer}}-Block!")
                log_file.write(f"[WARNUNG] Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")
            elif changes:
                rel_path = md_file.relative_to(target_dir)
                print(f"[GEPRÜFT] {rel_path.name} ({len(changes)} Hinweise)")
                log_file.write(f"Datei: {rel_path}\n")
                for change in changes:
                    log_file.write(f"  - {change}\n")
                log_file.write("\n")

        log_file.write("--- Zusammenfassung ---\n")
        log_file.write(f"Geprüfte Dateien: {total_files}\n")
        log_file.write(f"Geänderte Dateien: {changed_files}\n")
        log_file.write(f"Übersprungene Dateien: {skipped_files}\n")
        log_file.write(f"Dateien mit ungeschlossenem {{.answer}}-Block: {warning_files}\n")
        if warning_files == 0:
            log_file.write("ERGEBNIS: OK — keine ungeschlossenen {.answer}-Blöcke gefunden.\n")
        else:
            log_file.write(f"ERGEBNIS: {warning_files} Datei(en) mit ungeschlossenem {{.answer}}-Block!\n")

    print("\n--- Vorgang abgeschlossen ---")
    print(f"Geprüfte .md-Dateien gesamt:        {total_files}")
    print(f"Davon bereinigt und überschrieben:  {changed_files}")
    print(f"Davon übersprungen (strict/Fehler): {skipped_files}")
    if warning_files == 0:
        print("✅  Keine ungeschlossenen {.answer}-Blöcke gefunden.")
    else:
        print(f"⚠️   {warning_files} Datei(en) mit ungeschlossenem {{.answer}}-Block!")
    print(f"Logfile: {log_path}")

if __name__ == "__main__":
    main()
