#!/usr/bin/env python3
"""Prune local tech-law news older than N days WITHOUT deleting from GitHub.

- Deletes local data/{YYYY-MM-DD}/ trees older than keep_days
- Deletes local Documents/รอบวันที่_{YYYY-MM-DD}/ trees (and matching zip) older than keep_days
- Marks tracked paths skip-worktree so git status/push never stages the deletion
- Never touches data/manifest.json, never git rm / commit / push

Cloud/GitHub Pages keeps full history. Local PC frees disk space.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = REPO / "data"
DOCROOT = REPO / "Documents"
DATE_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
ROUND_DIR_RE = re.compile(r"^รอบวันที่_(\d{4}-\d{2}-\d{2})$")
ROUND_ZIP_RE = re.compile(r"^รอบวันที่_(\d{4}-\d{2}-\d{2})\.zip$", re.IGNORECASE)


def parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def skip_worktree(rel: str) -> None:
    run_git("update-index", "--skip-worktree", "--", rel)


def tracked_under(prefix: str) -> list[str]:
    result = run_git("ls-files", "--", prefix)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def dir_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if not path.is_dir():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def bytes_mb(n: int) -> float:
    return n / (1024 * 1024)


def prune_data_dirs(cutoff: date, dry_run: bool) -> tuple[int, int]:
    removed = 0
    freed = 0
    if not DATA.is_dir():
        return 0, 0
    for path in sorted(DATA.iterdir()):
        if not path.is_dir():
            continue
        m = DATE_DIR_RE.match(path.name)
        if not m:
            continue
        d = parse_date(m.group(1))
        if not d or d >= cutoff:
            continue
        size = dir_bytes(path)
        rel = f"data/{path.name}"
        print(f"[DATA] remove local {rel}/ (date={d} < {cutoff})")
        if dry_run:
            removed += 1
            freed += size
            continue
        for tracked in tracked_under(rel):
            skip_worktree(tracked)
        try:
            shutil.rmtree(path)
            removed += 1
            freed += size
        except OSError as e:
            print(f"[WARN] could not delete {path}: {e}")
    return removed, freed


def prune_documents(cutoff: date, dry_run: bool) -> tuple[int, int]:
    removed = 0
    freed = 0
    if not DOCROOT.is_dir():
        return 0, 0
    for path in sorted(DOCROOT.iterdir()):
        date_str = None
        if path.is_dir():
            m = ROUND_DIR_RE.match(path.name)
            if m:
                date_str = m.group(1)
        elif path.is_file():
            m = ROUND_ZIP_RE.match(path.name)
            if m:
                date_str = m.group(1)
        if not date_str:
            continue
        d = parse_date(date_str)
        if not d or d >= cutoff:
            continue
        size = dir_bytes(path)
        rel = f"Documents/{path.name}"
        kind = "dir" if path.is_dir() else "zip"
        print(f"[DOC] remove local {rel} ({kind}, date={d} < {cutoff})")
        if dry_run:
            removed += 1
            freed += size
            continue
        if path.is_dir():
            for tracked in tracked_under(rel):
                skip_worktree(tracked)
            try:
                shutil.rmtree(path)
                removed += 1
                freed += size
            except OSError as e:
                print(f"[WARN] could not delete {path}: {e}")
        else:
            for tracked in tracked_under(rel):
                skip_worktree(tracked)
            try:
                path.unlink(missing_ok=True)
                removed += 1
                freed += size
            except OSError as e:
                print(f"[WARN] could not delete {path}: {e}")
    return removed, freed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local-only prune of tech-law news older than N days (cloud untouched)"
    )
    parser.add_argument("--days", type=int, default=180, help="Keep last N days locally (default 180)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be removed")
    parser.add_argument(
        "--no-documents",
        action="store_true",
        help="Only prune data/{date}/, leave Documents/",
    )
    args = parser.parse_args()

    if args.days < 30:
        print("ERROR: --days must be >= 30 for safety")
        return 2

    today = date.today()
    cutoff = today - timedelta(days=args.days)
    print(f"[START] local prune keep_days={args.days} cutoff={cutoff} dry_run={args.dry_run}")
    print(f"        REPO={REPO}")
    print(f"        DOCROOT={DOCROOT}")
    print("[INFO] GitHub/cloud is NOT modified — local disk only")
    print("[INFO] data/manifest.json is never rewritten by this tool")

    n1, b1 = prune_data_dirs(cutoff, args.dry_run)
    n2, b2 = (0, 0) if args.no_documents else prune_documents(cutoff, args.dry_run)

    print(
        f"[OK] removed={n1 + n2} items "
        f"(data={n1}, documents={n2}) freed~{bytes_mb(b1 + b2):.1f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
