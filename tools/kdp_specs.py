"""Amazon-KDP-Spezifikationen — SSOT-Loader für ``kdp_specs.json``.

Alle Zahlen (Bleed, Papierdicken, Trim-Katalog, Innenrand-Stufen,
Studio-Paperback-Presets) leben in der JSON-Datei im Repo-Root. Dieses
Modul lädt sie, merged fehlende Keys mit eingebetteten Defaults und stellt
Accessoren bereit. Cover-Rechner, Compliance und Layout-Profile lesen
ausschließlich hierüber.

Rückwärtskompatibel: ``BLEED_MM`` bleibt als Modul-Attribut (wird bei
``reload_specs()`` aktualisiert).
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    "meta": {
        "verified": "2026-08-02",
        "sources": [
            "https://kdp.amazon.com/de_DE/help/topic/GVBQ3CMEQW3W2VL6",
            "https://kdp.amazon.com/de_DE/help/topic/G201953020",
            "https://kdp.amazon.com/de_DE/help/topic/G201834180",
        ],
    },
    "mm_per_inch": 25.4,
    "bleed_mm": 3.2,
    "paperback": {
        "min_page_count": 24,
        "max_page_count": 828,
        "min_outer_margin_in": 0.25,
    },
    "paper_types": [
        {"id": "white_bw", "label": "Weiß (Schwarz/Weiß-Druck)", "mm_per_page": 0.0572},
        {"id": "cream_bw", "label": "Cremefarben (Schwarz/Weiß-Druck)", "mm_per_page": 0.0635},
        {"id": "standard_color", "label": "Standardfarbe", "mm_per_page": 0.0572},
        {"id": "premium_color", "label": "Premiumfarbe", "mm_per_page": 0.0596},
    ],
    "default_paper_type_id": "white_bw",
    "trim_sizes_in": [
        {"id": "5x8", "label": '5" × 8"', "width": 5.0, "height": 8.0},
        {"id": "5.06x7.81", "label": '5,06" × 7,81"', "width": 5.06, "height": 7.81},
        {"id": "5.25x8", "label": '5,25" × 8"', "width": 5.25, "height": 8.0},
        {"id": "5.5x8.5", "label": '5,5" × 8,5"', "width": 5.5, "height": 8.5},
        {
            "id": "6x9",
            "label": '6" × 9" (am weitesten verbreitet)',
            "width": 6.0,
            "height": 9.0,
        },
        {"id": "6.14x9.21", "label": '6,14" × 9,21"', "width": 6.14, "height": 9.21},
        {"id": "6.69x9.61", "label": '6,69" × 9,61"', "width": 6.69, "height": 9.61},
        {"id": "7x10", "label": '7" × 10"', "width": 7.0, "height": 10.0},
        {"id": "7.44x9.69", "label": '7,44" × 9,69"', "width": 7.44, "height": 9.69},
        {"id": "7.5x9.25", "label": '7,5" × 9,25"', "width": 7.5, "height": 9.25},
        {"id": "8x10", "label": '8" × 10"', "width": 8.0, "height": 10.0},
        {"id": "8.25x6", "label": '8,25" × 6"', "width": 8.25, "height": 6.0},
        {"id": "8.25x8.25", "label": '8,25" × 8,25"', "width": 8.25, "height": 8.25},
        {"id": "8.5x8.5", "label": '8,5" × 8,5"', "width": 8.5, "height": 8.5},
        {"id": "8.5x11", "label": '8,5" × 11"', "width": 8.5, "height": 11.0},
        {"id": "8.27x11.69", "label": '8,27" × 11,69" (A4)', "width": 8.27, "height": 11.69},
    ],
    "custom_trim_in": {
        "width_range": [4.0, 8.5],
        "height_range": [6.0, 11.69],
    },
    "inside_margin_mm_by_max_pages": [
        [150, 9.53],
        [300, 12.7],
        [500, 15.88],
        [700, 19.05],
        [828, 22.23],
    ],
    "typst_defaults": {
        "margin_in": {"x": 1.25, "y": 1.25},
        "fallback_papersize": "us-letter",
    },
    "studio_presets": {
        "paperback": {
            "trim_mm": {"width": 135, "height": 215},
            "page_margin_mm": {
                "inside": 20,
                "outside": 16,
                "top": 19,
                "bottom": 20,
            },
            "lines_per_page": 36,
            "chars_per_line": 62,
        },
        "taschenbuch_bod": {
            "papersize": "a5",
            "page_margin_mm": {
                "inside": 20,
                "outside": 16,
                "top": 18,
                "bottom": 20,
            },
        },
    },
}


def default_specs() -> dict[str, Any]:
    """Tiefe Kopie der eingebetteten Defaults (Reset / Fallback)."""
    return copy.deepcopy(_DEFAULTS)


def specs_path(repo_root: Optional[Path] = None) -> Path:
    root = Path(repo_root) if repo_root is not None else _discover_repo_root()
    return root / "kdp_specs.json"


def _discover_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    # tools/kdp_specs.py → Repo-Root
    candidate = here.parent
    if (candidate / "kdp_specs.json").is_file() or (candidate / "app_config.json").is_file():
        return candidate
    return candidate


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    """Validiert/normalisiert kritische Felder; fällt auf Defaults zurück."""
    out = _deep_merge(_DEFAULTS, data if isinstance(data, dict) else {})
    try:
        out["bleed_mm"] = float(out.get("bleed_mm", _DEFAULTS["bleed_mm"]))
    except (TypeError, ValueError):
        out["bleed_mm"] = float(_DEFAULTS["bleed_mm"])
    try:
        out["mm_per_inch"] = float(out.get("mm_per_inch", _DEFAULTS["mm_per_inch"]))
    except (TypeError, ValueError):
        out["mm_per_inch"] = float(_DEFAULTS["mm_per_inch"])

    pb = out.get("paperback") if isinstance(out.get("paperback"), dict) else {}
    try:
        pb["min_page_count"] = int(pb.get("min_page_count", 24))
        pb["max_page_count"] = int(pb.get("max_page_count", 828))
        pb["min_outer_margin_in"] = float(pb.get("min_outer_margin_in", 0.25))
    except (TypeError, ValueError):
        pb = copy.deepcopy(_DEFAULTS["paperback"])
    out["paperback"] = pb

    papers = out.get("paper_types")
    if not isinstance(papers, list) or not papers:
        out["paper_types"] = copy.deepcopy(_DEFAULTS["paper_types"])
    else:
        cleaned_papers: list[dict[str, Any]] = []
        for item in papers:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id") or "").strip()
            if not pid:
                continue
            try:
                mm = float(item.get("mm_per_page"))
            except (TypeError, ValueError):
                continue
            cleaned_papers.append(
                {
                    "id": pid,
                    "label": str(item.get("label") or pid),
                    "mm_per_page": mm,
                }
            )
        out["paper_types"] = cleaned_papers or copy.deepcopy(_DEFAULTS["paper_types"])

    trims = out.get("trim_sizes_in")
    if not isinstance(trims, list) or not trims:
        out["trim_sizes_in"] = copy.deepcopy(_DEFAULTS["trim_sizes_in"])
    else:
        cleaned_trims: list[dict[str, Any]] = []
        for item in trims:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("id") or "").strip()
            if not tid:
                continue
            try:
                w = float(item.get("width"))
                h = float(item.get("height"))
            except (TypeError, ValueError):
                continue
            cleaned_trims.append(
                {
                    "id": tid,
                    "label": str(item.get("label") or tid),
                    "width": w,
                    "height": h,
                }
            )
        out["trim_sizes_in"] = cleaned_trims or copy.deepcopy(_DEFAULTS["trim_sizes_in"])

    tiers = out.get("inside_margin_mm_by_max_pages")
    if not isinstance(tiers, list) or not tiers:
        out["inside_margin_mm_by_max_pages"] = copy.deepcopy(
            _DEFAULTS["inside_margin_mm_by_max_pages"]
        )
    else:
        cleaned_tiers: list[list[float]] = []
        for row in tiers:
            try:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    cleaned_tiers.append([int(row[0]), float(row[1])])
            except (TypeError, ValueError):
                continue
        out["inside_margin_mm_by_max_pages"] = (
            cleaned_tiers or copy.deepcopy(_DEFAULTS["inside_margin_mm_by_max_pages"])
        )

    return out


_specs: dict[str, Any] = default_specs()
_loaded_path: Optional[Path] = None

# Rückwärtskompatibel für ``from tools.kdp_specs import BLEED_MM``.
BLEED_MM: float = float(_specs["bleed_mm"])


def _sync_module_attrs() -> None:
    global BLEED_MM
    BLEED_MM = float(_specs["bleed_mm"])


def load_specs(path: Optional[Path] = None) -> dict[str, Any]:
    """Lädt Specs von Disk (oder Defaults), speichert im Modul-Cache."""
    global _specs, _loaded_path
    target = Path(path) if path is not None else specs_path()
    _loaded_path = target
    if not target.is_file():
        _specs = default_specs()
        _sync_module_attrs()
        return copy.deepcopy(_specs)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        _LOG.warning("kdp_specs.json unlesbar (%s) — Defaults.", exc)
        _specs = default_specs()
        _sync_module_attrs()
        return copy.deepcopy(_specs)
    _specs = _normalize(raw if isinstance(raw, dict) else {})
    _sync_module_attrs()
    return copy.deepcopy(_specs)


def reload_specs(path: Optional[Path] = None) -> dict[str, Any]:
    """Erneut laden und abhängige Kataloge refreshen."""
    data = load_specs(path)
    try:
        from tools.layout_profiles import catalog as layout_catalog

        layout_catalog.refresh_from_kdp_specs()
    except (ImportError, AttributeError):
        pass
    try:
        from tools.publisher_compliance import catalog as pub_catalog

        pub_catalog.refresh_from_kdp_specs()
    except (ImportError, AttributeError):
        pass
    return data


def save_specs(data: dict[str, Any], path: Optional[Path] = None) -> Path:
    """Schreibt Specs (normalisiert) und aktualisiert den Cache."""
    global _specs, _loaded_path
    target = Path(path) if path is not None else (_loaded_path or specs_path())
    normalized = _normalize(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _specs = normalized
    _loaded_path = target
    _sync_module_attrs()
    reload_specs(target)
    return target


def current_specs() -> dict[str, Any]:
    return copy.deepcopy(_specs)


def bleed_mm() -> float:
    return float(_specs["bleed_mm"])


def mm_per_inch() -> float:
    return float(_specs["mm_per_inch"])


def min_page_count() -> int:
    return int(_specs["paperback"]["min_page_count"])


def max_page_count() -> int:
    return int(_specs["paperback"]["max_page_count"])


def min_outer_margin_in() -> float:
    return float(_specs["paperback"]["min_outer_margin_in"])


def default_paper_type_id() -> str:
    return str(_specs.get("default_paper_type_id") or "white_bw")


def paper_types() -> list[dict[str, Any]]:
    return copy.deepcopy(_specs["paper_types"])


def trim_sizes_in() -> list[dict[str, Any]]:
    return copy.deepcopy(_specs["trim_sizes_in"])


def custom_width_range_in() -> tuple[float, float]:
    rng = _specs.get("custom_trim_in", {}).get("width_range", [4.0, 8.5])
    return float(rng[0]), float(rng[1])


def custom_height_range_in() -> tuple[float, float]:
    rng = _specs.get("custom_trim_in", {}).get("height_range", [6.0, 11.69])
    return float(rng[0]), float(rng[1])


def inside_margin_mm_by_max_pages() -> tuple[tuple[int, float], ...]:
    rows = _specs.get("inside_margin_mm_by_max_pages") or []
    return tuple((int(a), float(b)) for a, b in rows)


def typst_default_margin_in() -> dict[str, float]:
    margin = (_specs.get("typst_defaults") or {}).get("margin_in") or {"x": 1.25, "y": 1.25}
    return {"x": float(margin.get("x", 1.25)), "y": float(margin.get("y", 1.25))}


def studio_paperback_preset() -> dict[str, Any]:
    presets = _specs.get("studio_presets") or {}
    pb = presets.get("paperback")
    if isinstance(pb, dict):
        return copy.deepcopy(pb)
    return copy.deepcopy(_DEFAULTS["studio_presets"]["paperback"])


def studio_taschenbuch_bod_preset() -> dict[str, Any]:
    presets = _specs.get("studio_presets") or {}
    bod = presets.get("taschenbuch_bod")
    if isinstance(bod, dict):
        return copy.deepcopy(bod)
    return copy.deepcopy(_DEFAULTS["studio_presets"]["taschenbuch_bod"])


def format_bleed_note() -> str:
    """Kurzer UI-Hinweis mit aktuellem Bleed-Wert."""
    mm = bleed_mm()
    inches = mm / mm_per_inch()
    return (
        f"Beschnittzugabe ({mm:g}mm / {inches:.3f}in) ist in "
        "Gesamt-Coverbreite/-höhe bereits enthalten."
    )


# Initial load at import.
load_specs()

__all__ = [
    "BLEED_MM",
    "default_specs",
    "specs_path",
    "load_specs",
    "reload_specs",
    "save_specs",
    "current_specs",
    "bleed_mm",
    "mm_per_inch",
    "min_page_count",
    "max_page_count",
    "min_outer_margin_in",
    "default_paper_type_id",
    "paper_types",
    "trim_sizes_in",
    "custom_width_range_in",
    "custom_height_range_in",
    "inside_margin_mm_by_max_pages",
    "typst_default_margin_in",
    "studio_paperback_preset",
    "studio_taschenbuch_bod_preset",
    "format_bleed_note",
]
