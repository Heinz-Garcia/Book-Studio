import bisect
import re
from pathlib import Path


_INLINE_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_REF_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]")
_REF_DEF_PATTERN = re.compile(r"^\s*\[([^\]]+)\]:\s*(.+?)\s*$", re.MULTILINE)
_URL_SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _extract_target(raw_target):
    target = str(raw_target or "").strip()
    if not target:
        return ""

    if target.startswith("<") and ">" in target:
        target = target[1:target.find(">")].strip()
    else:
        target = target.split(None, 1)[0].strip()

    if "#" in target:
        target = target.split("#", 1)[0]
    if "?" in target:
        target = target.split("?", 1)[0]

    return target.strip()


def _is_local_asset_target(target):
    if not target:
        return False
    lower = target.lower()
    if lower.startswith(("http://", "https://", "data:", "mailto:")):
        return False
    if _URL_SCHEME_PATTERN.match(target):
        return False
    return True


def _build_line_starts(text):
    starts = [0]
    for idx, char in enumerate(text):
        if char == "\n":
            starts.append(idx + 1)
    return starts


def _line_for_index(index, line_starts):
    return bisect.bisect_right(line_starts, index)


def collect_image_targets(markdown_text):
    text = str(markdown_text or "")
    reference_map = {}

    for ref_name, raw_target in _REF_DEF_PATTERN.findall(text):
        normalized_name = ref_name.strip().lower()
        reference_map[normalized_name] = _extract_target(raw_target)

    targets = []

    for raw_target in _INLINE_IMAGE_PATTERN.findall(text):
        target = _extract_target(raw_target)
        if target:
            targets.append(target)

    for raw_ref in _REF_IMAGE_PATTERN.findall(text):
        ref_name = raw_ref.strip().lower()
        if not ref_name:
            continue
        target = reference_map.get(ref_name, "")
        if target:
            targets.append(target)

    return targets


def collect_image_refs(markdown_text):
    text = str(markdown_text or "")
    line_starts = _build_line_starts(text)
    reference_map = {}

    for ref_name, raw_target in _REF_DEF_PATTERN.findall(text):
        normalized_name = ref_name.strip().lower()
        reference_map[normalized_name] = _extract_target(raw_target)

    refs = []

    for match in _INLINE_IMAGE_PATTERN.finditer(text):
        target = _extract_target(match.group(1))
        if target:
            refs.append((target, _line_for_index(match.start(), line_starts)))

    for match in _REF_IMAGE_PATTERN.finditer(text):
        alt_text = match.group(1).strip().lower()
        raw_ref = match.group(2).strip().lower()
        ref_name = raw_ref if raw_ref else alt_text
        if not ref_name:
            continue
        target = reference_map.get(ref_name, "")
        if target:
            refs.append((target, _line_for_index(match.start(), line_starts)))

    return refs


def find_missing_image_refs(markdown_text, markdown_file_path, book_root_path):
    markdown_path = Path(markdown_file_path)
    book_root = Path(book_root_path)
    missing_refs = []

    for target, line_number in collect_image_refs(markdown_text):
        if not _is_local_asset_target(target):
            continue

        normalized_target = target.replace("\\", "/")
        candidates = []

        if normalized_target.startswith("/"):
            candidates.append(book_root / normalized_target.lstrip("/"))
        else:
            candidates.append(markdown_path.parent / normalized_target)
            candidates.append(book_root / normalized_target)

        exists = any(candidate.exists() and candidate.is_file() for candidate in candidates)
        if not exists:
            missing_refs.append((line_number, target))

    unique_refs = sorted(set(missing_refs), key=lambda item: (item[0], item[1].lower()))
    return unique_refs


def find_missing_images(markdown_text, markdown_file_path, book_root_path):
    missing_refs = find_missing_image_refs(markdown_text, markdown_file_path, book_root_path)
    return sorted({target for _, target in missing_refs})
