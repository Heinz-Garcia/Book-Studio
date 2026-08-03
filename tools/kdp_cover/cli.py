"""CLI für ``python -m tools.kdp_cover`` — Phase-1 Wrap-PDF-Export."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.cover_size.calculator import (
    DEFAULT_PAPER_TYPE_ID,
    get_trim_size,
    inch_to_mm,
)
from tools.kdp_cover.constants import DEFAULT_EXPORT_DPI
from tools.kdp_cover.export_pdf import export_wrap_pdf
from tools.kdp_cover.geometry import build_geometry
from tools.kdp_cover.model import CoverLayout, load_layout, save_layout
from tools.kdp_specs import studio_paperback_preset


def _default_trim_mm() -> tuple[float, float]:
    preset = studio_paperback_preset()
    trim = preset.get("trim_mm") or {}
    return float(trim.get("width", 135)), float(trim.get("height", 215))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.kdp_cover",
        description=(
            "Erzeugt ein KDP-konformes Wrap-Cover-PDF "
            "(Rückseite + Rücken + Vorderseite inkl. Bleed)."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    geo = sub.add_parser("geometry", help="Maße berechnen und ausgeben (kein Export).")
    geo.add_argument("--pages", type=int, required=True)
    geo.add_argument("--paper", default=DEFAULT_PAPER_TYPE_ID)
    geo.add_argument("--trim-id", default="", help="KDP-Trim-ID, z. B. 6x9")
    geo.add_argument("--trim-width-mm", type=float, default=0.0)
    geo.add_argument("--trim-height-mm", type=float, default=0.0)

    exp = sub.add_parser("export", help="Wrap-PDF erzeugen.")
    exp.add_argument("--pages", type=int, required=True)
    exp.add_argument("--paper", default=DEFAULT_PAPER_TYPE_ID)
    exp.add_argument("--trim-id", default="")
    exp.add_argument("--trim-width-mm", type=float, default=0.0)
    exp.add_argument("--trim-height-mm", type=float, default=0.0)
    exp.add_argument("--front", default="", help="Pfad zum Vorderseiten-Bild")
    exp.add_argument("--back", default="", help="Optional: Rückseiten-Bild")
    exp.add_argument("--back-color", default="#FFFFFF")
    exp.add_argument("--spine-color", default="#222222")
    exp.add_argument("--title", default="")
    exp.add_argument("--author", default="")
    exp.add_argument("--spine-text", default="")
    exp.add_argument("--mode", choices=("safe", "free"), default="safe")
    exp.add_argument("--dpi", type=float, default=float(DEFAULT_EXPORT_DPI))
    exp.add_argument(
        "--out",
        required=True,
        help="Ziel-PDF (z. B. export/kdp_cover/Cover-Wrap.pdf)",
    )
    exp.add_argument(
        "--validation-json",
        default="",
        help="Optional: Validierungsbericht als JSON schreiben",
    )
    exp.add_argument(
        "--allow-warnings-only",
        action="store_true",
        help="Wie Modus free: Errors blockieren weiter; nur für spätere Nutzung reserviert",
    )
    exp.add_argument(
        "--save-project",
        default="",
        help="Optional: cover_project.json speichern",
    )
    exp.add_argument(
        "--from-project",
        default="",
        help="Layout aus cover_project.json laden (CLI-Flags überschreiben)",
    )
    return p


def _resolve_trim(args: argparse.Namespace) -> tuple[float, float]:
    if args.trim_width_mm > 0 and args.trim_height_mm > 0:
        return float(args.trim_width_mm), float(args.trim_height_mm)
    if args.trim_id:
        trim = get_trim_size(args.trim_id)
        if trim is None:
            raise SystemExit(f"Unbekannte Trim-ID: {args.trim_id!r}")
        return inch_to_mm(trim.width_in), inch_to_mm(trim.height_in)
    return _default_trim_mm()


def _cmd_geometry(args: argparse.Namespace) -> int:
    tw, th = _resolve_trim(args)
    geo = build_geometry(
        page_count=args.pages,
        paper_type_id=args.paper,
        trim_width_mm=tw,
        trim_height_mm=th,
    )
    print(f"trim_mm:          {geo.trim_width_mm:g} x {geo.trim_height_mm:g}")
    print(f"spine_mm:         {geo.spine_width_mm:g}")
    print(f"bleed_mm:         {geo.bleed_mm:g}")
    print(f"cover_mm:         {geo.cover_width_mm:g} x {geo.cover_height_mm:g}")
    print(f"safe_zone_mm:     {geo.safe_zone_mm:g}")
    print(f"back_panel_mm:    x={geo.back_panel.x:g} w={geo.back_panel.width:g}")
    print(f"spine_panel_mm:   x={geo.spine_panel.x:g} w={geo.spine_panel.width:g}")
    print(f"front_panel_mm:   x={geo.front_panel.x:g} w={geo.front_panel.width:g}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    if args.from_project:
        layout = load_layout(Path(args.from_project))
        if args.front:
            layout.front_image = args.front
        if args.back:
            layout.back_image = args.back
        if args.title:
            layout.title = args.title
        if args.author:
            layout.author = args.author
        if args.spine_text:
            layout.spine_text = args.spine_text
        layout.page_count = args.pages
        layout.paper_type_id = args.paper
        tw, th = _resolve_trim(args)
        layout.trim_width_mm = tw
        layout.trim_height_mm = th
        layout.mode = args.mode
    else:
        if not args.front:
            raise SystemExit("export: --front ist erforderlich (oder --from-project).")
        tw, th = _resolve_trim(args)
        layout = CoverLayout(
            page_count=args.pages,
            paper_type_id=args.paper,
            trim_width_mm=tw,
            trim_height_mm=th,
            mode=args.mode,
            front_image=args.front,
            back_image=args.back,
            back_color=args.back_color,
            spine_color=args.spine_color,
            title=args.title,
            author=args.author,
            spine_text=args.spine_text,
        )
    if not layout.front_image.strip():
        raise SystemExit("export: Vorderseiten-Bild fehlt.")

    if args.save_project:
        save_layout(layout, Path(args.save_project))

    require_safe = layout.mode == "safe"
    try:
        out, report = export_wrap_pdf(
            layout,
            Path(args.out),
            dpi=float(args.dpi),
            resolve_base=Path.cwd(),
            validation_json=Path(args.validation_json) if args.validation_json else None,
            require_safe=require_safe,
        )
    except ValueError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    print(f"PDF: {out}")
    if report.warnings:
        print(f"Warnungen: {len(report.warnings)}")
        for w in report.warnings:
            print(f"  - [{w.code}] {w.message}")
    if report.errors:
        print(f"Errors (free-Modus): {len(report.errors)}")
        for e in report.errors:
            print(f"  - [{e.code}] {e.message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "geometry":
        return _cmd_geometry(args)
    if args.command == "export":
        return _cmd_export(args)
    parser.error(f"Unbekannter Befehl: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
