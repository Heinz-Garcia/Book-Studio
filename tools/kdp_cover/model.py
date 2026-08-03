"""Serialisierbares Layout-Modell für ein KDP-Wrap-Cover.

Phase 1–3: Basis-Felder + freie Text-Offsets (nur Modus ``free``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Optional

Mode = Literal["safe", "free"]


@dataclass
class CoverLayout:
    """Wrap-Layout.

    Front: Vollbild (cover-fit) im Front-Panel inkl. Bleed-Überhang.
    Back: einfarbig oder optionales Bild.
    Spine: einfarbig; optionaler Text nur wenn Seitenzahl es erlaubt.
    Titel/Autor: reine Metadaten (PDF-Info / cover_project), nicht aufs Bild
    — außer experimentellem ``front_compose`` (sichtbare Vorderseiten-Layer).
    Rücken-Text: optionaler sichtbarer Text auf dem Wrap (ab 79 Seiten).
    Offsets betreffen nur noch den Rücken-Text im Frei-Modus.
    """

    page_count: int
    paper_type_id: str
    trim_width_mm: float
    trim_height_mm: float
    mode: Mode = "safe"
    front_image: str = ""
    back_image: str = ""
    back_color: str = "#FFFFFF"
    spine_color: str = "#222222"
    title: str = ""
    author: str = ""
    spine_text: str = ""
    title_color: str = "#FFFFFF"
    # Frei-Modus: Offsets relativ zur Standard-Safe-Slot-Position (mm).
    # Positiv X = nach rechts, positiv Y = nach unten.
    title_offset_x_mm: float = 0.0
    title_offset_y_mm: float = 0.0
    author_offset_x_mm: float = 0.0
    author_offset_y_mm: float = 0.0
    spine_offset_y_mm: float = 0.0
    title_scale: float = 1.0
    # Experimentell / wegwerfbar — siehe tools.kdp_cover.compose_front
    front_compose: Optional[dict[str, Any]] = None
    # Relativer Pfad zum zuletzt am Buch hinterlegten Wrap-PDF (optional)
    wrap_pdf: str = ""

    def effective_offsets(self) -> dict[str, float]:
        """Im Sicher-Modus immer 0 / Scale 1 — Slots sind fest."""
        if self.mode != "free":
            return {
                "title_offset_x_mm": 0.0,
                "title_offset_y_mm": 0.0,
                "author_offset_x_mm": 0.0,
                "author_offset_y_mm": 0.0,
                "spine_offset_y_mm": 0.0,
                "title_scale": 1.0,
            }
        scale = float(self.title_scale) if self.title_scale > 0 else 1.0
        return {
            "title_offset_x_mm": float(self.title_offset_x_mm),
            "title_offset_y_mm": float(self.title_offset_y_mm),
            "author_offset_x_mm": float(self.author_offset_x_mm),
            "author_offset_y_mm": float(self.author_offset_y_mm),
            "spine_offset_y_mm": float(self.spine_offset_y_mm),
            "title_scale": scale,
        }

    def reset_free_placement(self) -> None:
        self.title_offset_x_mm = 0.0
        self.title_offset_y_mm = 0.0
        self.author_offset_x_mm = 0.0
        self.author_offset_y_mm = 0.0
        self.spine_offset_y_mm = 0.0
        self.title_scale = 1.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data.get("front_compose"):
            data.pop("front_compose", None)
        if not data.get("wrap_pdf"):
            data.pop("wrap_pdf", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverLayout:
        mode = data.get("mode", "safe")
        if mode not in ("safe", "free"):
            mode = "safe"
        try:
            scale = float(data.get("title_scale", 1.0))
        except (TypeError, ValueError):
            scale = 1.0
        if scale <= 0:
            scale = 1.0

        def _f(key: str, default: float = 0.0) -> float:
            try:
                return float(data.get(key, default))
            except (TypeError, ValueError):
                return default

        raw_compose = data.get("front_compose")
        front_compose = raw_compose if isinstance(raw_compose, dict) else None

        return cls(
            page_count=int(data["page_count"]),
            paper_type_id=str(data.get("paper_type_id") or "white_bw"),
            trim_width_mm=float(data["trim_width_mm"]),
            trim_height_mm=float(data["trim_height_mm"]),
            mode=mode,  # type: ignore[arg-type]
            front_image=str(data.get("front_image") or ""),
            back_image=str(data.get("back_image") or ""),
            back_color=str(data.get("back_color") or "#FFFFFF"),
            spine_color=str(data.get("spine_color") or "#222222"),
            title=str(data.get("title") or ""),
            author=str(data.get("author") or ""),
            spine_text=str(data.get("spine_text") or ""),
            title_color=str(data.get("title_color") or "#FFFFFF"),
            title_offset_x_mm=_f("title_offset_x_mm"),
            title_offset_y_mm=_f("title_offset_y_mm"),
            author_offset_x_mm=_f("author_offset_x_mm"),
            author_offset_y_mm=_f("author_offset_y_mm"),
            spine_offset_y_mm=_f("spine_offset_y_mm"),
            title_scale=scale,
            front_compose=front_compose,
            wrap_pdf=str(data.get("wrap_pdf") or ""),
        )


def save_layout(layout: CoverLayout, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(layout.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_layout(path: Path) -> CoverLayout:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Cover-Layout-JSON muss ein Objekt sein.")
    return CoverLayout.from_dict(raw)


def cover_export_dir(book_root: Path) -> Path:
    return Path(book_root) / "export" / "kdp_cover"


def sanitize_book_filename_stem(name: str) -> str:
    """Dateisicherer Stem aus dem Buchordnernamen."""
    raw = (name or "").strip() or "book"
    out: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in "-_.":
            out.append(ch)
        elif ch in " \t":
            out.append("_")
        else:
            out.append("_")
    stem = "".join(out).strip("._") or "book"
    return stem[:120]


def legacy_project_path(book_root: Path) -> Path:
    """Früherer fester Name (Autoload-Fallback)."""
    return cover_export_dir(book_root) / "cover_project.json"


def default_project_path(book_root: Path) -> Path:
    """Kanonischer Cover-Layout-Pfad: ``{Buchname}_kdp_cover.json``."""
    root = Path(book_root)
    stem = sanitize_book_filename_stem(root.name)
    return cover_export_dir(root) / f"{stem}_kdp_cover.json"


def default_wrap_pdf_path(book_root: Path) -> Path:
    """Vorschlags-PDF: ``{Buchname}_kdp_wrap.pdf`` unter ``export/kdp_cover/``."""
    root = Path(book_root)
    stem = sanitize_book_filename_stem(root.name)
    return cover_export_dir(root) / f"{stem}_kdp_wrap.pdf"


def resolve_existing_project_path(book_root: Path) -> Path | None:
    """Vorhandene Layout-Datei: kanonisch bevorzugt, sonst Legacy."""
    canonical = default_project_path(book_root)
    if canonical.is_file():
        return canonical
    legacy = legacy_project_path(book_root)
    if legacy.is_file():
        return legacy
    return None


__all__ = [
    "Mode",
    "CoverLayout",
    "save_layout",
    "load_layout",
    "cover_export_dir",
    "sanitize_book_filename_stem",
    "legacy_project_path",
    "default_project_path",
    "default_wrap_pdf_path",
    "resolve_existing_project_path",
]
