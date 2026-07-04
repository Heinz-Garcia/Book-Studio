"""CLI-Einstieg: python -m tools.skeleton <befehl>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cmd_list_profiles(args: argparse.Namespace) -> int:
    from tools.skeleton.config import read_skeleton_settings
    from tools.skeleton.manifest import list_profiles, profile_labels, resolve_library_root

    repo = _repo_root()
    settings = read_skeleton_settings(repo)
    library = resolve_library_root(repo, settings["library_path"])
    profiles = list_profiles(library)
    if not profiles:
        print("Keine Skeleton-Profile gefunden.")
        return 1
    labels = profile_labels(library, profiles)
    default = settings["default_profile"]
    for name in profiles:
        marker = " (Standard)" if name == default else ""
        print(f"- {name}{marker}: {labels.get(name, name)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if str(_repo_root()) not in sys.path:
        sys.path.insert(0, str(_repo_root()))

    parser = argparse.ArgumentParser(description="Skeleton-Bibliothek (Populate, Editor, Profile)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-profiles", help="Skeleton-Profile auflisten")

    populate = sub.add_parser("populate", help="Vorlagen ins Buch kopieren")
    populate.add_argument("--book-path", type=Path, required=True)
    populate.add_argument("--profile", default=None)
    populate.add_argument("--on-conflict", choices=("ask", "skip", "replace"), default=None)
    populate.add_argument("--missing-only", action="store_true")
    populate.add_argument("--yes", action="store_true")

    editor = sub.add_parser("edit", help="Skeleton-Bibliothek bearbeiten")
    editor.add_argument("--profile", default=None)

    args = parser.parse_args(argv)
    if args.command == "list-profiles":
        return _cmd_list_profiles(args)
    if args.command == "populate":
        from tools.skeleton.populate import run

        kwargs = {"book_path": args.book_path, "yes": args.yes}
        if args.profile:
            kwargs["profile"] = args.profile
        if args.on_conflict:
            kwargs["conflict_mode"] = args.on_conflict
        if args.missing_only:
            kwargs["missing_only"] = True
        return run(studio=None, **kwargs)
    if args.command == "edit":
        from tools.skeleton.editor import run

        return run(studio=None, profile=args.profile)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
