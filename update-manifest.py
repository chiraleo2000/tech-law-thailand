#!/usr/bin/env python3
"""Add content rounds to manifest.json without deleting or overwriting entries."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from content_schema import validate_document


class ManifestParseError(Exception):
    """Raised when the current manifest cannot be parsed."""


@dataclass
class UpdateResult:
    changed: bool = False
    error: str = ""
    ids_added: list[str] = field(default_factory=list)


def load_manifest(path: Path) -> dict:
    if not path.is_file():
        return {"entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestParseError(f"อ่าน manifest ไม่สำเร็จ: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ManifestParseError("manifest ไม่มี entries ที่เป็นอาร์เรย์")
    return data


def merge_entry(manifest: dict, date: str, content_path: str, ids: list[str]) -> dict:
    """Prepend unseen ids. Existing entries stay in place and keep their fields."""
    entries = [dict(entry) for entry in manifest.get("entries", [])]
    known = {
        item
        for entry in entries
        if entry.get("date") == date
        for item in entry.get("ids", [])
    }
    fresh = [item for item in ids if item not in known]
    if not fresh and any(entry.get("date") == date for entry in entries):
        return {"entries": entries}
    if not fresh and not entries:
        fresh = list(ids)
    if not fresh:
        return {"entries": entries}
    new_entry = {"date": date, "path": content_path, "ids": fresh}
    return {"entries": [new_entry, *entries]}


def update_manifest(manifest_path: Path, content_json_paths: list[Path]) -> UpdateResult:
    result = UpdateResult()
    loaded: list[tuple[Path, dict]] = []
    for content_path in content_json_paths:
        if not content_path.is_file():
            result.error = f"ไม่พบไฟล์เนื้อหา: {content_path}"
            return result
        try:
            document = json.loads(content_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            result.error = f"อ่านไฟล์เนื้อหาไม่ได้: {content_path} ({exc})"
            return result
        errors = validate_document(document)
        if errors:
            result.error = f"{content_path}: {'; '.join(errors)}"
            return result
        loaded.append((content_path, document))

    try:
        original_bytes = manifest_path.read_bytes() if manifest_path.is_file() else None
        manifest = load_manifest(manifest_path)
    except ManifestParseError as exc:
        result.error = str(exc)
        return result

    loaded.sort(key=lambda item: item[1]["date"], reverse=True)
    fresh_entries = []
    added: list[str] = []
    known_by_date: dict[str, set[str]] = {}
    for entry in manifest.get("entries", []):
        known_by_date.setdefault(entry.get("date", ""), set()).update(entry.get("ids", []))
    for content_path, document in loaded:
        date = document["date"]
        known = known_by_date.setdefault(date, set())
        fresh = [post["id"] for post in document["posts"] if post["id"] not in known]
        if not fresh:
            continue
        fresh_entries.append({
            "date": date,
            "path": _relative_content_path(content_path),
            "ids": fresh,
        })
        added.extend(fresh)
        known.update(fresh)
    if not fresh_entries:
        return result

    merged = {"entries": fresh_entries + [dict(entry) for entry in manifest.get("entries", [])]}

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    manifest_path.write_text(text, encoding="utf-8")
    if original_bytes is not None:
        # Existing entries remain. A failed write is already an exception.
        pass
    result.changed = True
    result.ids_added = added
    return result


def _relative_content_path(path: Path) -> str:
    parts = path.as_posix().split("/")
    if "data" in parts:
        index = parts.index("data")
        return "/".join(parts[index:])
    return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="เพิ่ม content.json เข้า manifest แบบเพิ่มอย่างเดียว")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--content", action="append", required=True)
    args = parser.parse_args(argv)
    outcome = update_manifest(Path(args.manifest), [Path(item) for item in args.content])
    if outcome.error:
        print(outcome.error, file=sys.stderr)
        return 1
    print(json.dumps({"changed": outcome.changed, "ids_added": outcome.ids_added}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
