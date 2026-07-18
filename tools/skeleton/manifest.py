"""Laden und Validieren von Skeleton-Manifesten (YAML)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

import yaml

import json_io


@dataclass(frozen=True)
class SkeletonFileEntry:
    path: str
    title: str = ""
    order: Optional[str] = None
    optional: bool = False
    include_in_tree: bool = True
    description: str = ""


@dataclass(frozen=True)
class SkeletonManifest:
    name: str
    label: str
    description: str
    root: Path
    files: tuple[SkeletonFileEntry, ...] = field(default_factory=tuple)

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.yaml"


def _normalize_rel_path(path: str) -> str:
    return str(path).replace("\\", "/")


def sanitize_relative_template_path(rel_path: str, profile_dir: Path) -> str:
    """SSOT-Validierung für relative Skeleton-Vorlagenpfade.

    Analog zu `validate_profile_name()`: verhindert Path-Traversal beim
    Anlegen neuer Markdown-Vorlagen (`create_markdown_template`) und beim
    Laden von `manifest.yaml` (`load_manifest`).
    Wirft `ValueError` bei leerem, absolutem, `~`-präfixiertem oder
    traversierendem (`..`-Segment) Pfad, sowie wenn der aufgelöste
    Zielpfad außerhalb von `profile_dir` läge.
    """
    if "\x00" in str(rel_path):
        raise ValueError(f"Ungültiger Pfad (invalid path, NUL-Byte): {rel_path!r}")

    # Absolutheits-/Home-Präfix-Prüfung MUSS vor dem `lstrip("/")` erfolgen,
    # sonst würde z. B. "/etc/evil.md" fälschlich zu einem relativen Pfad
    # normalisiert und die Absolut-Erkennung umgangen.
    normalized = _normalize_rel_path(rel_path).strip()
    if not normalized:
        raise ValueError("Ungültiger Pfad (invalid path): leer.")
    if normalized.startswith("~"):
        raise ValueError(
            f"Ungültiger Pfad (invalid path): Home-Verzeichnis-Präfix '~' nicht erlaubt: {rel_path!r}"
        )
    if re.match(r"^[a-zA-Z]:", normalized):
        raise ValueError(f"Ungültiger absoluter Pfad (invalid absolute path): {rel_path!r}")
    if PureWindowsPath(normalized).is_absolute() or PurePosixPath(normalized).is_absolute():
        raise ValueError(f"Ungültiger absoluter Pfad (invalid absolute path): {rel_path!r}")

    rel = normalized.lstrip("/")
    if not rel:
        raise ValueError("Ungültiger Pfad (invalid path): leer.")
    if any(segment == ".." for segment in rel.split("/")):
        raise ValueError(f"Path-Traversal erkannt (unzulässiges '..'-Segment): {rel_path!r}")

    profile_dir = Path(profile_dir).resolve()
    candidate = (profile_dir / rel).resolve()
    if not candidate.is_relative_to(profile_dir):
        raise ValueError(f"Path-Traversal erkannt (außerhalb des Profilverzeichnisses): {rel_path!r}")

    return rel


def load_manifest(profile_dir: Path) -> SkeletonManifest:
    """Lädt `manifest.yaml` aus einem Skeleton-Profilordner."""
    profile_dir = Path(profile_dir).resolve()
    manifest_path = profile_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Skeleton-Manifest nicht gefunden: {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Ungültiges Manifest: {manifest_path}")

    name = str(raw.get("name") or profile_dir.name).strip()
    label = str(raw.get("label") or name).strip()
    description = str(raw.get("description") or "").strip()

    entries: list[SkeletonFileEntry] = []
    for item in raw.get("files") or []:
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            continue
        try:
            rel = sanitize_relative_template_path(raw_path, profile_dir)
        except ValueError as exc:
            raise ValueError(
                f"Ungültiger Dateipfad in Manifest {manifest_path}: {exc}"
            ) from exc
        order_val = item.get("order")
        order = str(order_val).strip() if order_val is not None and str(order_val).strip() else None
        title = str(item.get("title") or Path(rel).stem).strip()
        entries.append(
            SkeletonFileEntry(
                path=rel,
                title=title,
                order=order,
                optional=bool(item.get("optional", False)),
                include_in_tree=bool(item.get("include_in_tree", True)),
                description=str(item.get("description") or title).strip(),
            )
        )

    if not entries:
        raise ValueError(f"Manifest enthält keine Dateien: {manifest_path}")

    return SkeletonManifest(
        name=name,
        label=label,
        description=description,
        root=profile_dir,
        files=tuple(entries),
    )


def resolve_profile_dir(library_root: Path, profile_name: str) -> Path:
    profile_name = validate_profile_name(profile_name)
    library_root = Path(library_root).resolve()
    profile_dir = library_root / profile_name
    if not profile_dir.is_dir():
        raise FileNotFoundError(
            f"Skeleton-Profil '{profile_name}' nicht gefunden unter {library_root}"
        )
    return profile_dir


def list_profiles(library_root: Path) -> list[str]:
    library_root = Path(library_root)
    if not library_root.is_dir():
        return []
    profiles: list[str] = []
    for child in sorted(library_root.iterdir()):
        if child.is_dir() and (child / "manifest.yaml").is_file():
            profiles.append(child.name)
    return profiles


def manifest_to_dict(manifest: SkeletonManifest) -> dict:
    files: list[dict] = []
    for entry in manifest.files:
        item: dict = {
            "path": _normalize_rel_path(entry.path),
            "title": entry.title,
        }
        if entry.order:
            item["order"] = entry.order
        if entry.optional:
            item["optional"] = True
        if not entry.include_in_tree:
            item["include_in_tree"] = False
        if entry.description and entry.description != entry.title:
            item["description"] = entry.description
        files.append(item)
    return {
        "name": manifest.name,
        "label": manifest.label,
        "description": manifest.description,
        "files": files,
    }


def save_manifest(manifest: SkeletonManifest) -> None:
    """Schreibt Manifest zurück nach `manifest.root/manifest.yaml`.

    Atomar via Temp-Datei + `os.replace`, damit ein Abbruch während des
    Schreibens das Profil nicht unbrauchbar macht.
    """
    data = manifest_to_dict(manifest)
    target = manifest.manifest_path
    text = yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    json_io.write_text_atomic(target, text)


def replace_manifest_entries(profile_dir: Path, entries: list[SkeletonFileEntry], **meta: str) -> SkeletonManifest:
    """Ersetzt die Dateiliste eines Profils und speichert das Manifest."""
    current = load_manifest(profile_dir)
    manifest = SkeletonManifest(
        name=str(meta.get("name") or current.name),
        label=str(meta.get("label") or current.label),
        description=str(meta.get("description") or current.description),
        root=Path(profile_dir).resolve(),
        files=tuple(entries),
    )
    save_manifest(manifest)
    return manifest


_PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")
_PROFILE_SEGMENT_RE = _PROFILE_NAME_RE


def validate_profile_name(name: str) -> str:
    """Validiert einen Profil-Namen gegen Path-Traversal und ungültige Zeichen.

    Erlaubt sind einzelne Segmente (Buchstaben, Ziffern, Unterstrich,
    Bindestrich) sowie verschachtelte Profile mit `/`- oder `\\`-Trennern
    (z. B. `"kategorie/profil"`), solange kein Segment `.`/`..` ist, der Name
    nicht mit `~` beginnt und kein absoluter Pfad (führendes `/`, `\\` oder
    Laufwerksbuchstabe) übergeben wird. Wirft `ValueError` (invalid) bei
    jedem unzulässigen Namen — Aufrufer unterscheiden so zwischen
    syntaktisch ungültigen Namen und lediglich fehlenden, aber gültig
    benannten Profilen (`FileNotFoundError`, siehe `resolve_profile_dir()`).
    """
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("Profilname ungültig (invalid): darf nicht leer sein.")
    if cleaned.startswith("~"):
        raise ValueError(
            f"Profilname ungültig (invalid): Home-Verzeichnis-Präfix '~' nicht erlaubt: {cleaned!r}"
        )
    if re.match(r"^[a-zA-Z]:", cleaned) or cleaned.startswith(("/", "\\")):
        raise ValueError(f"Profilname ungültig (invalid, absolute Pfade nicht erlaubt): {cleaned!r}")

    segments = re.split(r"[/\\]+", cleaned)
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValueError(f"Profilname ungültig (invalid, Path-Traversal/leeres Segment): {cleaned!r}")
    if not all(_PROFILE_SEGMENT_RE.match(segment) for segment in segments):
        raise ValueError(
            f"Profilname ungültig (invalid). Erlaubt: Buchstaben, Ziffern, Unterstrich, "
            f"Bindestrich (optional mit '/'-getrennten Segmenten): {cleaned!r}"
        )
    return "/".join(segments)


def duplicate_profile(
    library_root: Path,
    source_name: str,
    dest_name: str,
    *,
    label: Optional[str] = None,
) -> Path:
    """Kopiert ein Skeleton-Profil inkl. aller Dateien."""
    library_root = Path(library_root).resolve()
    source_name = validate_profile_name(source_name)
    dest_name = validate_profile_name(dest_name)
    source_dir = resolve_profile_dir(library_root, source_name)
    dest_dir = library_root / dest_name
    if dest_dir.exists():
        raise FileExistsError(f"Profil existiert bereits: {dest_dir}")
    shutil.copytree(source_dir, dest_dir)
    manifest = load_manifest(dest_dir)
    new_label = label or f"{manifest.label} (Kopie)"
    updated = SkeletonManifest(
        name=dest_name,
        label=new_label,
        description=manifest.description,
        root=dest_dir,
        files=manifest.files,
    )
    save_manifest(updated)
    return dest_dir


def create_markdown_template(
    profile_dir: Path,
    rel_path: str,
    *,
    title: str,
    order: Optional[str] = None,
    body: str = "",
) -> Path:
    """Legt eine neue Markdown-Vorlage im Profil an."""
    profile_dir = Path(profile_dir).resolve()
    rel = sanitize_relative_template_path(rel_path, profile_dir)
    if not rel.lower().endswith(".md"):
        rel += ".md"
    target = profile_dir / rel
    if target.exists():
        raise FileExistsError(f"Datei existiert bereits: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # YAML-konform serialisieren, damit Anführungszeichen im Titel/Beschreibung
    # das Frontmatter nicht corrupt machen (statt manueller String-Interpolation).
    meta = {"title": title, "description": title, "status": "bookstudio"}
    if order:
        meta["order"] = order
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip("\n")
    target.write_text(
        "---\n" + front + "\n---\n\n" + (body or f"# {title}") + "\n",
        encoding="utf-8",
    )
    return target


def resolve_library_root(repo_root: Path, configured_path: str) -> Path:
    root = Path(configured_path)
    if not root.is_absolute():
        root = (repo_root / root).resolve()
    return root


def update_manifest_meta(
    profile_dir: Path,
    *,
    label: Optional[str] = None,
    description: Optional[str] = None,
) -> SkeletonManifest:
    manifest = load_manifest(profile_dir)
    updated = SkeletonManifest(
        name=manifest.name,
        label=label if label is not None else manifest.label,
        description=description if description is not None else manifest.description,
        root=manifest.root,
        files=manifest.files,
    )
    save_manifest(updated)
    return updated


_PROTECTED_PROFILES = frozenset({"standard"})


def delete_profile(
    library_root: Path,
    profile_name: str,
    *,
    protected: frozenset[str] = _PROTECTED_PROFILES,
) -> None:
    name = validate_profile_name(profile_name)
    if name in protected:
        raise ValueError(f"Profil '{name}' ist geschützt und kann nicht gelöscht werden.")
    target = Path(library_root).resolve() / name
    if not target.is_dir():
        raise FileNotFoundError(f"Profil nicht gefunden: {name}")
    shutil.rmtree(target)


def profile_labels(library_root: Path, profiles: Optional[list[str]] = None) -> dict[str, str]:
    names = profiles if profiles is not None else list_profiles(library_root)
    labels: dict[str, str] = {}
    for name in names:
        try:
            labels[name] = load_manifest(Path(library_root) / name).label
        except (OSError, ValueError):
            labels[name] = name
    return labels
