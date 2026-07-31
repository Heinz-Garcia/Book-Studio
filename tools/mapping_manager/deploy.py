"""PDF-Deploy: markierte Fertig-PDF in konfigurierbaren Zielordner kopieren.

Der WEB.DE-/MagentaCLOUD-Pfad enthält oft eine Account-UUID, die bei
Neuinstallation wechseln kann. ``resolve_pdf_deploy_folder`` bevorzugt den
konfigurierten Pfad und fällt sonst auf die Suche unter
``~/WEB.DE Online-Speicher/*/__Projekte/IFJN/PDF`` zurück.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

_WEBDE_DIRNAME = "WEB.DE Online-Speicher"
_IFJN_PDF_PARTS = ("__Projekte", "IFJN", "PDF")


def discover_webde_ifjn_pdf(home: Optional[Path] = None) -> Optional[Path]:
    """Findet ``…/WEB.DE Online-Speicher/<uuid>/__Projekte/IFJN/PDF`` unter home."""
    root = (home or Path.home()) / _WEBDE_DIRNAME
    if not root.is_dir():
        return None
    matches: list[Path] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return None
    for child in children:
        try:
            if not child.is_dir():
                continue
        except OSError:
            continue
        if child.name.startswith(".") or child.name.lower() == "desktop.ini":
            continue
        candidate = child.joinpath(*_IFJN_PDF_PARTS)
        try:
            if candidate.is_dir():
                matches.append(candidate)
        except OSError:
            continue
    if not matches:
        return None
    matches.sort(key=lambda p: str(p).casefold())
    return matches[0]


def _looks_like_webde_ifjn_pdf(path: Path) -> bool:
    parts = [p.casefold() for p in path.parts]
    marker = _WEBDE_DIRNAME.casefold()
    if marker not in parts:
        return False
    suffix = [p.casefold() for p in _IFJN_PDF_PARTS]
    return parts[-len(suffix) :] == suffix if len(parts) >= len(suffix) else False


def resolve_pdf_deploy_folder(
    configured: str | Path | None,
    *,
    home: Optional[Path] = None,
) -> Optional[Path]:
    """Löst den Deploy-Zielordner aus Config und/oder WEB.DE-Discovery.

    Reihenfolge:
    1. Konfigurierter Pfad, falls er als Verzeichnis existiert
    2. Bei WEB.DE-/IFJN-Layout und fehlendem UUID-Ordner: Discovery
    3. Konfigurierter Pfad, falls das Elternverzeichnis existiert (wird beim
       Deploy angelegt)
    4. Discovery bei leerer Config
    """
    raw = str(configured or "").strip()
    home_path = home or Path.home()
    if raw:
        path = Path(raw).expanduser()
        try:
            if path.is_dir():
                return path.resolve()
        except OSError:
            pass
        if _looks_like_webde_ifjn_pdf(path):
            discovered = discover_webde_ifjn_pdf(home_path)
            if discovered is not None:
                return discovered
        try:
            if path.parent.is_dir():
                return path
        except OSError:
            pass
        return None
    return discover_webde_ifjn_pdf(home_path)


def deploy_pdf(
    source: Path,
    dest_dir: Path,
    *,
    overwrite: bool = True,
) -> Path:
    """Kopiert ``source`` nach ``dest_dir/<dateiname>``. Gibt den Zielpfad zurück."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"PDF nicht gefunden: {source}")
    dest_dir = Path(dest_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Deploy-Ordner nicht anlegbar: {dest_dir} ({exc})") from exc
    dest = dest_dir / source.name
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Datei existiert bereits: {dest.name}")
    try:
        shutil.copy2(source, dest)
    except OSError as exc:
        raise OSError(f"Kopieren nach {dest} fehlgeschlagen: {exc}") from exc
    return dest
