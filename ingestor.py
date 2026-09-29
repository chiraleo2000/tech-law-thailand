#!/usr/bin/env python3
"""Convert รอบวันที่_* law folders into data/{date}/content.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from content_schema import validate_document, validate_post

DOCX_NAME = "1_เอกสารสรุปและเปรียบเทียบข้อกฎหมาย.docx"
INFO_NAME = "2_ภาพอินโฟกราฟิก_แนวตั้ง_9ต่อ16.png"
REL_NAME = "4_แผนผังความสัมพันธ์กฎหมายและบุคคล.png"
SOCIAL_NAME = "3_เนื้อหาโพสต์เฟซบุ๊ก_โซเชียลมีเดีย.txt"
ROUND_RE = re.compile(r"^รอบวันที่_(\d{4}-\d{2}-\d{2})$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOMAIN_RE = re.compile(
    r"(?:https?://)?((?:[a-z0-9-]+\.)+(?:go\.th|or\.th|ac\.th|co\.th|com|io|net|org)(?:/[^\s;,)）]*)?)",
    re.IGNORECASE,
)
HASHTAG_RE = re.compile(r"#([\w\u0E00-\u0E7F]+)", re.UNICODE)
THAI_MONTHS = {
    "มกราคม": 1,
    "กุมภาพันธ์": 2,
    "มีนาคม": 3,
    "เมษายน": 4,
    "พฤษภาคม": 5,
    "มิถุนายน": 6,
    "กรกฎาคม": 7,
    "สิงหาคม": 8,
    "กันยายน": 9,
    "ตุลาคม": 10,
    "พฤศจิกายน": 11,
    "ธันวาคม": 12,
}


class DocxConversionError(Exception):
    """Raised when the summary document cannot be read."""


class CopyMismatchError(Exception):
    """Raised when a copied image does not match the source byte for byte."""


@dataclass
class IngestResult:
    date: str
    written: bool = False
    manifest_ready: bool = False
    content_path: str = ""
    ids: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def derive_title(folder_name: str) -> str:
    """Drop a leading sequence number and underscore."""
    match = re.match(r"^\d+_(.+)$", folder_name)
    title = match.group(1) if match else folder_name.lstrip("_")
    return title


def derive_slug(title: str) -> str:
    slug = title.strip().replace("_", "-")
    slug = re.sub(r"\s+", "-", slug).strip("-")
    if not slug:
        slug = "เนื้อหา"
    return slug[:200]


def derive_id(folder_name: str, date: str) -> str:
    match = re.match(r"^(\d+)_", folder_name)
    prefix = match.group(1) if match else "00"
    slug = derive_slug(derive_title(folder_name))
    base = f"{prefix}-{slug}"
    if len(base) <= 128:
        return base
    digest = hashlib.sha256(f"{date}/{folder_name}".encode("utf-8")).hexdigest()[:8]
    return f"{base[:119]}-{digest}"


def parse_round_date(date_dir: Path) -> str:
    match = ROUND_RE.match(date_dir.name)
    if not match:
        raise ValueError(f"ชื่อโฟลเดอร์ต้องเป็น รอบวันที่_YYYY-MM-DD: {date_dir.name}")
    return match.group(1)


def convert_docx_to_html(docx_path: Path) -> str:
    html, _raw = _convert(docx_path)
    return html


def read_comments(txt_path: Path | None) -> list[str]:
    if txt_path is None or not txt_path.is_file():
        return []
    text = txt_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [text]


def announcement_date_from_text(text: str, fallback: str) -> str:
    labeled = re.search(r"วันที่ประกาศ:\s*(\d{4}-\d{2}-\d{2})", text)
    if labeled:
        return labeled.group(1)
    gazette = _thai_date_after(text, "ราชกิจจานุเบกษา")
    if gazette:
        return gazette
    issued = _thai_date_after(text, "ลงวันที่")
    if issued:
        return issued
    if ISO_DATE.match(fallback):
        return fallback
    return ""


def _thai_date_after(text: str, marker: str) -> str:
    pattern = rf"{marker}\s+(\d{{1,2}})\s+([ก-๙\.]+)\s+(\d{{4}})"
    match = re.search(pattern, text)
    if not match:
        return ""
    day = int(match.group(1))
    month = THAI_MONTHS.get(match.group(2))
    year = int(match.group(3))
    if not month or not 1 <= day <= 31:
        return ""
    if year > 2400:
        year -= 543
    return f"{year:04d}-{month:02d}-{day:02d}"


def extract_source_url(*chunks: str) -> str:
    text = "\n".join(chunk for chunk in chunks if chunk)
    direct = re.search(r"https?://[^\s<>\"']+", text)
    if direct:
        return direct.group(0).rstrip(").,;")
    preferred = []
    others = []
    for row in text.splitlines():
        match = DOMAIN_RE.search(row)
        if not match:
            continue
        url = match.group(0).rstrip(").,;")
        if not url.lower().startswith("http"):
            url = "https://" + url
        if "อ้างอิง" in row:
            preferred.append(url)
        else:
            others.append(url)
    if preferred:
        return preferred[0]
    if others:
        return others[0]
    return ""


def extract_tags(text: str) -> list[str]:
    seen: list[str] = []
    for tag in HASHTAG_RE.findall(text or ""):
        if tag not in seen:
            seen.append(tag)
        if len(seen) == 50:
            break
    return seen


def _image_dest_name(folder_name: str, source_name: str) -> str:
    match = re.match(r"^(\d+)_", folder_name)
    prefix = match.group(1) if match else "00"
    stem = re.sub(r"^\d+_", "", source_name)
    return f"{prefix}_{stem}"


def resolve_image(folder: Path, filename: str, dest_dir: Path) -> tuple[str, bool]:
    """Copy a PNG when present. Return relative path and whether the copy matched."""
    source = folder / filename
    if not source.is_file():
        return "", True
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _image_dest_name(folder.name, filename)
    payload = source.read_bytes()
    dest.write_bytes(payload)
    if dest.read_bytes() != payload:
        dest.unlink(missing_ok=True)
        raise CopyMismatchError(filename)
    return f"images/{dest.name}", True


def build_post(folder: Path, date: str, image_dir: Path) -> dict | None:
    docx = folder / DOCX_NAME
    if not docx.is_file():
        print(f"[ข้าม] {folder.name}: ไม่พบไฟล์เนื้อหาหลัก", file=sys.stderr)
        return None
    try:
        html, raw = _convert(docx)
    except DocxConversionError as exc:
        print(f"[ข้าม] {folder.name}: แปลงเอกสารไม่ได้ ({exc})", file=sys.stderr)
        return None

    social = folder / SOCIAL_NAME
    social_text = ""
    if social.is_file():
        social_text = social.read_text(encoding="utf-8")
    info_path, _info_ok = resolve_image(folder, INFO_NAME, image_dir)
    rel_path, _rel_ok = resolve_image(folder, REL_NAME, image_dir)

    title = derive_title(folder.name)
    post = {
        "id": derive_id(folder.name, date),
        "slug": derive_slug(title),
        "title": title,
        "announcement_date": announcement_date_from_text(f"{raw}\n{social_text}", date),
        "content_html": html,
        "infographic_image": info_path,
        "relationship_image": rel_path,
        "comments": read_comments(social if social.is_file() else None),
        "source_url": extract_source_url(raw, social_text),
        "tags": extract_tags(social_text),
    }
    errors = validate_post(post, 0)
    if errors:
        print(f"[ข้าม] {folder.name}: {'; '.join(errors)}", file=sys.stderr)
        return None
    return post


def _convert(docx_path: Path) -> tuple[str, str]:
    try:
        import mammoth
    except ImportError as exc:
        raise DocxConversionError("ไม่พบไลบรารี mammoth") from exc
    try:
        with docx_path.open("rb") as handle:
            html_result = mammoth.convert_to_html(handle)
        with docx_path.open("rb") as handle:
            text_result = mammoth.extract_raw_text(handle)
    except Exception as exc:
        raise DocxConversionError(str(exc)) from exc
    html = (html_result.value or "").strip()
    if not html:
        raise DocxConversionError("เอกสารว่าง")
    return html, text_result.value or ""


def _unique_ids(posts: list[dict], date: str) -> list[dict]:
    seen: set[str] = set()
    ready: list[dict] = []
    for post in posts:
        base = post["id"]
        candidate = base
        suffix = 2
        while candidate in seen:
            extra = f"-{suffix}"
            candidate = f"{base[: 128 - len(extra)]}{extra}"
            suffix += 1
        post["id"] = candidate
        seen.add(candidate)
        ready.append(post)
    return ready


def ingest_date(date_dir: Path, out_dir: Path, generated_at: str | None = None) -> IngestResult:
    date = parse_round_date(date_dir)
    result = IngestResult(date=date)
    image_dir = out_dir / date / "images"
    posts: list[dict] = []
    folders = sorted(path for path in date_dir.iterdir() if path.is_dir())
    try:
        for folder in folders:
            post = build_post(folder, date, image_dir)
            if post is None:
                result.skipped.append(folder.name)
                continue
            posts.append(post)
    except CopyMismatchError as exc:
        print(f"[ไม่เขียนทับ] {date_dir.name}: คัดลอกภาพไม่ตรงทุกไบต์ ({exc})", file=sys.stderr)
        return result
    if not posts:
        print(f"[ข้ามรอบ] {date_dir.name}: ไม่มีบทความที่ผ่านการตรวจ", file=sys.stderr)
        return result

    posts = _unique_ids(posts, date)
    document = {
        "date": date,
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "posts": posts,
    }
    errors = validate_document(document)
    dest = out_dir / date / "content.json"
    if errors:
        print(f"[ไม่เขียนทับ] {dest}: {'; '.join(errors)}", file=sys.stderr)
        return result

    dest.parent.mkdir(parents=True, exist_ok=True)
    _write_json(dest, document)
    result.written = True
    result.manifest_ready = True
    result.content_path = dest.as_posix()
    result.ids = [post["id"] for post in posts]
    return result


def ingest_dates(date_dirs: list[Path], out_dir: Path) -> list[IngestResult]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    for date_dir in date_dirs:
        results.append(ingest_date(date_dir, out_dir, generated_at=stamp))
    return results


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    parser = argparse.ArgumentParser(description="แปลงโฟลเดอร์รอบวันที่เป็น content.json")
    parser.add_argument("--date-dir", action="append", required=True, dest="date_dirs")
    parser.add_argument("--out", default="data")
    args = parser.parse_args(argv)
    results = ingest_dates([Path(item) for item in args.date_dirs], Path(args.out))
    ready = [item.content_path for item in results if item.manifest_ready]
    print(json.dumps({"ready": ready, "dates": [item.date for item in results]}, ensure_ascii=False))
    return 0 if ready else 2


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
