#!/usr/bin/env python3
"""Fail the Pages deploy when index.html references a missing file."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REF_RE = re.compile(r"""(?:src|href)=["'](\./[^"']+)["']""")


def main() -> int:
    missing: list[str] = []
    index = ROOT / "index.html"
    if not index.is_file():
        missing.append("index.html")
    else:
        for match in REF_RE.findall(index.read_text(encoding="utf-8")):
            relative = match.removeprefix("./")
            if not (ROOT / relative).is_file():
                missing.append(relative)

    manifest_path = ROOT / "data" / "manifest.json"
    if not manifest_path.is_file():
        missing.append("data/manifest.json")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("entries", []):
            content_rel = entry.get("path", "")
            content_path = ROOT / content_rel
            if not content_path.is_file():
                missing.append(content_rel)
                continue
            document = json.loads(content_path.read_text(encoding="utf-8"))
            base = content_path.parent
            for post in document.get("posts", []):
                for key in ("infographic_image", "relationship_image"):
                    image = post.get(key) or ""
                    if image and not (base / image).is_file():
                        missing.append(f"{base.relative_to(ROOT).as_posix()}/{image}")

    if missing:
        print("ไฟล์ที่อ้างอิงไม่พบ:", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 1
    print(f"ตรวจไฟล์อ้างอิงครบ {len(list((ROOT / 'data').rglob('content.json')))} รอบเนื้อหา")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
