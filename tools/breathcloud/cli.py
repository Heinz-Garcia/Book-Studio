"""CLI: ``python -m tools.breathcloud``."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.breathcloud.engine import BreathcloudOptions, generate_breathcloud


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="breathcloud",
        description=(
            "Organische Wortwolke um ein Kernwort — freie Form, dichter Versatz, "
            "Farbverlauf. Unabhängig von Cover-Schlagwortwolke (stylecloud)."
        ),
    )
    parser.add_argument(
        "--text",
        "-t",
        default="",
        help="Begleittext (Wörter der Wolke). Alternativ --text-file.",
    )
    parser.add_argument("--text-file", "-f", type=Path, help="Textdatei laden.")
    parser.add_argument(
        "--hub",
        "-H",
        required=True,
        help="Kernwort (frei definierbar) — die Wolke schart sich darum.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("breathcloud.png"),
        help="Ausgabe-PNG.",
    )
    parser.add_argument(
        "--gradient",
        "-g",
        default="#1e5f8a,#2ec4b6,#c8f542",
        help="Farbverlauf als Hex-Liste, z.B. #1e5f8a,#2ec4b6,#c8f542",
    )
    parser.add_argument("--hub-size", type=int, default=140, help="Schriftgröße Kernwort.")
    parser.add_argument("--max-font", type=int, default=72, help="Max. Begleit-Schrift.")
    parser.add_argument("--min-font", type=int, default=14, help="Min. Begleit-Schrift.")
    parser.add_argument("--max-words", type=int, default=180)
    parser.add_argument("--canvas", type=int, default=1600, help="Arbeitsfläche (px).")
    parser.add_argument("--export-side", type=int, default=1600, help="Längste Kante Export.")
    parser.add_argument("--bg", default="#ffffff", help="Hintergrundfarbe.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-stopwords", action="store_true")
    args = parser.parse_args(argv)

    text = args.text or ""
    if args.text_file is not None:
        text = args.text_file.read_text(encoding="utf-8")
    if not text.strip():
        parser.error("Text fehlt (--text oder --text-file).")

    def progress(pct: int, msg: str) -> None:
        line = f"[{pct:3d}%] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))

    path = generate_breathcloud(
        BreathcloudOptions(
            text=text,
            hub_word=args.hub,
            output_path=args.output,
            canvas_size=args.canvas,
            hub_font_size=args.hub_size,
            max_font_size=args.max_font,
            min_font_size=args.min_font,
            max_words=args.max_words,
            gradient=args.gradient,
            background_color=args.bg,
            random_state=args.seed,
            use_stopwords=not args.no_stopwords,
            export_max_side=args.export_side,
        ),
        progress=progress,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
