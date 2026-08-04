"""Serialisierbares Layout-Modell für ein KDP-Wrap-Cover.

Phase 1–3: Basis-Felder + freie Text-Offsets (nur Modus ``free``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

Mode = Literal["safe", "free"]
SpineBadgePosition = Literal["before", "after"]


@dataclass
class SpineBadgeSpec:
    """Optionales Reihen-/Themen-Badge auf dem Buchrücken.

    Rechteckige Fläche mit weißem Text (z. B. „MEDIZIN“), Position relativ
    zu Textelement 2 (oben verankert). Lesrichtung immer unten→oben.
    ``scale_step`` skaliert Text und Hintergrund gemeinsam in Stufen (0 = 100 %).
    """

    enabled: bool = False
    text: str = ""
    color: str = "#9B2C3E"
    text_color: str = "#FFFFFF"
    position: SpineBadgePosition = "before"
    scale_step: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "text": str(self.text or ""),
            "color": str(self.color or "#9B2C3E"),
            "text_color": str(self.text_color or "#FFFFFF"),
            "position": "after" if self.position == "after" else "before",
            "scale_step": int(self.scale_step),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SpineBadgeSpec:
        from tools.kdp_cover.constants import SPINE_BADGE_SCALE_STEPS

        d = data if isinstance(data, dict) else {}
        pos = str(d.get("position") or "before").strip().lower()
        if pos not in ("before", "after"):
            pos = "before"
        try:
            step = int(d.get("scale_step", 0))
        except (TypeError, ValueError):
            step = 0
        max_step = max(0, len(SPINE_BADGE_SCALE_STEPS) - 1)
        step = max(0, min(max_step, step))
        return cls(
            enabled=bool(d.get("enabled", False)),
            text=str(d.get("text") or ""),
            color=str(d.get("color") or "#9B2C3E"),
            text_color=str(d.get("text_color") or "#FFFFFF"),
            position=pos,  # type: ignore[arg-type]
            scale_step=step,
        )

    def is_active(self) -> bool:
        return bool(self.enabled and str(self.text or "").strip())

    def scale_factor(self) -> float:
        from tools.kdp_cover.constants import SPINE_BADGE_SCALE_STEPS

        max_step = max(0, len(SPINE_BADGE_SCALE_STEPS) - 1)
        step = max(0, min(max_step, int(self.scale_step)))
        return float(SPINE_BADGE_SCALE_STEPS[step])


@dataclass
class CoverLayout:
    """Wrap-Layout.

    Front: Vollbild (cover-fit) im Front-Panel inkl. Bleed-Überhang.
    Back: einfarbig oder optionales Bild.
    Spine: einfarbig; optionaler Text nur wenn Seitenzahl es erlaubt.
    Titel/Autor: reine Metadaten (PDF-Info / cover_project), nicht aufs Bild
    — außer experimentellem ``front_compose`` (sichtbare Vorderseiten-Layer).
    Rücken-Text: zwei optionale Elemente mit **gleicher** Lesrichtung
    (unten→oben): ``spine_text`` unten verankert, ``spine_text_down`` oben
    verankert (Badge vor/nach Element 2). ``spine_padding_mm`` setzt parallel
    den Abstand vom Kopf- und Fußrand (Texte zusammen-/auseinanderrücken).
    spine_badge: optionales Rechteck-Label an Element 2.
    Offsets betreffen nur noch den Rücken-Inhalt im Frei-Modus.
    """

    page_count: int
    paper_type_id: str
    trim_width_mm: float
    trim_height_mm: float
    mode: Mode = "safe"
    front_image: str = ""
    back_image: str = ""
    # Vorderseite: Cover-Fit + Zoom (≥1) + Verschiebung des Ausschnitts (mm).
    front_image_zoom: float = 1.0
    front_image_offset_x_mm: float = 0.0
    front_image_offset_y_mm: float = 0.0
    # Rückseite: Contain-Skalierung (≤1), zentriert; optional Rahmen.
    back_image_scale: float = 1.0
    back_image_frame: bool = False
    back_image_frame_mm: float = 2.0
    back_image_frame_color: str = "#000000"
    back_color: str = "#FFFFFF"
    spine_color: str = "#222222"
    title: str = ""
    author: str = ""
    spine_text: str = ""  # Element 1: unten verankert, Lesrichtung unten → oben
    spine_text_down: str = ""  # Element 2: oben verankert, Lesrichtung unten → oben
    # Paralleler Abstand vom Kopf- und Fußrand (mm) — größer = Texte näher zusammen.
    spine_padding_mm: float = 1.6
    title_color: str = "#FFFFFF"
    # Frei-Modus: Offsets relativ zur Standard-Safe-Slot-Position (mm).
    # Positiv X = nach rechts, positiv Y = nach unten.
    title_offset_x_mm: float = 0.0
    title_offset_y_mm: float = 0.0
    author_offset_x_mm: float = 0.0
    author_offset_y_mm: float = 0.0
    spine_offset_y_mm: float = 0.0
    title_scale: float = 1.0
    spine_badge: SpineBadgeSpec = field(default_factory=SpineBadgeSpec)
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
        if not str(data.get("spine_text_down") or "").strip():
            data.pop("spine_text_down", None)
        badge = data.get("spine_badge")
        if isinstance(badge, dict) and not (
            badge.get("enabled") or str(badge.get("text") or "").strip()
        ):
            data.pop("spine_badge", None)
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
        raw_badge = data.get("spine_badge")
        spine_badge = SpineBadgeSpec.from_dict(
            raw_badge if isinstance(raw_badge, dict) else None
        )

        return cls(
            page_count=int(data["page_count"]),
            paper_type_id=str(data.get("paper_type_id") or "white_bw"),
            trim_width_mm=float(data["trim_width_mm"]),
            trim_height_mm=float(data["trim_height_mm"]),
            mode=mode,  # type: ignore[arg-type]
            front_image=str(data.get("front_image") or ""),
            back_image=str(data.get("back_image") or ""),
            front_image_zoom=max(1.0, _f("front_image_zoom", 1.0)),
            front_image_offset_x_mm=_f("front_image_offset_x_mm"),
            front_image_offset_y_mm=_f("front_image_offset_y_mm"),
            back_image_scale=max(0.05, min(1.0, _f("back_image_scale", 1.0) or 1.0)),
            back_image_frame=bool(data.get("back_image_frame", False)),
            back_image_frame_mm=max(0.0, _f("back_image_frame_mm", 2.0)),
            back_image_frame_color=str(data.get("back_image_frame_color") or "#000000"),
            back_color=str(data.get("back_color") or "#FFFFFF"),
            spine_color=str(data.get("spine_color") or "#222222"),
            title=str(data.get("title") or ""),
            author=str(data.get("author") or ""),
            spine_text=str(data.get("spine_text") or ""),
            spine_text_down=str(data.get("spine_text_down") or ""),
            spine_padding_mm=max(0.0, _f("spine_padding_mm", 1.6)),
            title_color=str(data.get("title_color") or "#FFFFFF"),
            title_offset_x_mm=_f("title_offset_x_mm"),
            title_offset_y_mm=_f("title_offset_y_mm"),
            author_offset_x_mm=_f("author_offset_x_mm"),
            author_offset_y_mm=_f("author_offset_y_mm"),
            spine_offset_y_mm=_f("spine_offset_y_mm"),
            title_scale=scale,
            spine_badge=spine_badge,
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
    ensure_cover_layout_dict(raw)
    return CoverLayout.from_dict(raw)


def ensure_cover_layout_dict(data: dict[str, Any]) -> None:
    """Wirft ValueError, wenn die Datei kein Cover-Layout ist."""
    kind = data.get("kind")
    if kind == "kdp_front_elementset":
        raise ValueError(
            "Das ist ein Elementset (Vorderseiten-Elemente), kein Cover-Layout. "
            "Bitte „Elementset laden…“ verwenden."
        )
    if "ok_for_safe_export" in data and "issues" in data:
        raise ValueError(
            "Das ist ein Validierungsbericht (*_validation.json), kein Cover-Layout."
        )
    # Elementset ohne kind, aber mit front_compose und ohne Maße
    if (
        "front_compose" in data
        and "page_count" not in data
        and "trim_width_mm" not in data
    ):
        raise ValueError(
            "Das sieht nach einem Elementset aus, nicht nach einem Cover-Layout. "
            "Bitte „Elementset laden…“ verwenden."
        )
    for key in ("page_count", "trim_width_mm", "trim_height_mm"):
        if key not in data:
            raise ValueError(
                f"Kein Cover-Layout: Pflichtfeld „{key}“ fehlt. "
                "Erwartet: *_kdp_cover.json oder *_kdp_wrap_project.json."
            )


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
    "SpineBadgePosition",
    "SpineBadgeSpec",
    "CoverLayout",
    "save_layout",
    "load_layout",
    "ensure_cover_layout_dict",
    "cover_export_dir",
    "sanitize_book_filename_stem",
    "legacy_project_path",
    "default_project_path",
    "default_wrap_pdf_path",
    "resolve_existing_project_path",
]
