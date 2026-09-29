"""Schema checks for law-content JSON. Content, not news."""

from __future__ import annotations

import re
from typing import Any

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

POST_KEYS = (
    "id",
    "slug",
    "title",
    "announcement_date",
    "content_html",
    "infographic_image",
    "relationship_image",
    "comments",
    "source_url",
    "tags",
)


def validate_post(post: Any, index: int = 0, seen_ids: set[str] | None = None) -> list[str]:
    """Return field errors. Empty list means the post is valid."""
    label = f"posts[{index}]"
    errors: list[str] = []
    if not isinstance(post, dict):
        return [f"{label}: ต้องเป็นวัตถุ"]
    for key in POST_KEYS:
        if key not in post:
            errors.append(f"{label}.{key}: ขาดฟิลด์")
    if errors:
        return errors

    errors.extend(_text(post, "id", label, 1, 128))
    errors.extend(_text(post, "slug", label, 1, 200))
    errors.extend(_text(post, "title", label, 1, 500))
    if not isinstance(post["announcement_date"], str) or not ISO_DATE.match(post["announcement_date"]):
        errors.append(f"{label}.announcement_date: ต้องเป็น YYYY-MM-DD")
    if not isinstance(post["content_html"], str) or not post["content_html"].strip():
        errors.append(f"{label}.content_html: ต้องมีข้อความ")
    if not isinstance(post["infographic_image"], str):
        errors.append(f"{label}.infographic_image: ต้องเป็นข้อความ")
    if not isinstance(post["relationship_image"], str):
        errors.append(f"{label}.relationship_image: ต้องเป็นข้อความ")
    if not isinstance(post["source_url"], str) or not post["source_url"].strip():
        errors.append(f"{label}.source_url: ต้องมีค่า")
    errors.extend(_string_list(post, "comments", label, 1000))
    errors.extend(_string_list(post, "tags", label, 50))

    if isinstance(post.get("id"), str) and seen_ids is not None:
        if post["id"] in seen_ids:
            errors.append(f"{label}.id: ซ้ำภายในรอบวันที่เดียวกัน")
        else:
            seen_ids.add(post["id"])
    return errors


def validate_document(document: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document: ต้องเป็นวัตถุ"]
    if not isinstance(document.get("date"), str) or not ISO_DATE.match(document.get("date", "")):
        errors.append("date: ต้องเป็น YYYY-MM-DD")
    if not isinstance(document.get("generated_at"), str) or not ISO_STAMP.match(document.get("generated_at", "")):
        errors.append("generated_at: ต้องเป็น YYYY-MM-DDThh:mm:ssZ")
    posts = document.get("posts")
    if not isinstance(posts, list):
        errors.append("posts: ต้องเป็นอาร์เรย์")
        return errors
    seen: set[str] = set()
    for index, post in enumerate(posts):
        errors.extend(validate_post(post, index, seen))
    return errors


def _text(post: dict, key: str, label: str, low: int, high: int) -> list[str]:
    value = post.get(key)
    if not isinstance(value, str) or not (low <= len(value) <= high):
        return [f"{label}.{key}: ความยาวต้องอยู่ระหว่าง {low} ถึง {high}"]
    return []


def _string_list(post: dict, key: str, label: str, high: int) -> list[str]:
    value = post.get(key)
    if not isinstance(value, list) or len(value) > high or any(not isinstance(item, str) for item in value):
        return [f"{label}.{key}: ต้องเป็นอาร์เรย์ของข้อความความยาว 0 ถึง {high}"]
    return []
