"""Schutz vor Publish-Sammelmappen (Idiotensicherheit)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFolderCheck:
    """Ergebnis der Prüfung, ob ein Ordner als GG-Export taugt."""

    path: Path
    is_publish_hub: bool
    reason: str = ""
    publish_run_dirs: tuple[str, ...] = ()
    markdown_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.is_publish_hub


def _publish_run_children(root: Path) -> list[str]:
    names: list[str] = []
    try:
        for child in root.iterdir():
            if child.is_dir() and child.name.lower().startswith("publish_"):
                names.append(child.name)
    except OSError:
        return []
    return sorted(names)


def _count_markdown(root: Path, *, limit: int = 200) -> int:
    n = 0
    try:
        for path in root.rglob("*.md"):
            if any(part.startswith(".") for part in path.parts):
                continue
            n += 1
            if n >= limit:
                return n
    except OSError:
        return n
    return n


def check_source_folder(path: Path | str) -> SourceFolderCheck:
    """Erkennt Publish-Sammelmappen (viele Publish_*-Läufe), die nicht als Quelle taugen."""
    root = Path(path)
    if not root.is_dir():
        return SourceFolderCheck(
            path=root,
            is_publish_hub=True,
            reason="Ordner existiert nicht.",
        )

    runs = _publish_run_children(root)
    md_count = _count_markdown(root)
    name = root.name.casefold()

    # Klassischer Fall: …/Publish mit mehreren Publish_* darunter
    if len(runs) >= 2:
        return SourceFolderCheck(
            path=root,
            is_publish_hub=True,
            reason=(
                f"Das ist die Publish-Sammelmappe ({len(runs)} Export-Läufe, "
                f"{md_count}+ Markdown-Dateien). "
                "Bitte eine konkrete .md-Datei aus einem einzelnen Publish_*-Ordner wählen — "
                "nicht die Sammelmappe."
            ),
            publish_run_dirs=tuple(runs),
            markdown_count=md_count,
        )

    if name == "publish" and md_count > 15:
        return SourceFolderCheck(
            path=root,
            is_publish_hub=True,
            reason=(
                f"Ordner „Publish“ mit {md_count}+ Markdown-Dateien ist zu breit. "
                "Bitte die konkrete Quell-.md aus einem Publish_*-Lauf wählen."
            ),
            publish_run_dirs=tuple(runs),
            markdown_count=md_count,
        )

    return SourceFolderCheck(
        path=root,
        is_publish_hub=False,
        publish_run_dirs=tuple(runs),
        markdown_count=md_count,
    )


def is_publish_hub(path: Path | str) -> bool:
    return check_source_folder(path).is_publish_hub
