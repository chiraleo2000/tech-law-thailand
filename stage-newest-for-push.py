#!/usr/bin/env python3
"""Stage only new/changed tech-law publish paths for push.

Never stages deletions (protects cloud history after local 180-day prune).
Never stages the whole data/ tree blindly — only paths that appear as
added/modified/untracked in git status under allowed prefixes.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent

ALLOWED_PREFIXES = (
    "data/",
    "Documents/",
    "index.html",
    "js/",
    "assets/",
    ".nojekyll",
    "_ประวัติกฎหมายที่ประมวลผลแล้ว.json",
    "_บันทึกสถานะการตรวจสอบ.txt",
)

BLOCKED_PREFIXES = (
    "Logs/",
    ".github-pat",
    "prune-local-old-news.py",
    "stage-newest-for-push.py",
    "build-tech-law-pdfs.py",
    "DailyPush.ps1",
    "Register-DailyPushSchedule.ps1",
    "PUSH.bat",
    "_to_delete/",
    "claude_schedule_prompts.txt",
    "_pdf_test.pdf",
)

DATE_DIR_RE = re.compile(r"^data/(\d{4}-\d{2}-\d{2})(?:/|$)")
ROUND_DIR_RE = re.compile(r"^Documents/รอบวันที่_(\d{4}-\d{2}-\d{2})(?:/|$)")
from datetime import date as _date

TODAY = _date.today().isoformat()


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def is_allowed(path: str) -> bool:
    if any(path == b or path.startswith(b) for b in BLOCKED_PREFIXES):
        return False
    if not any(path == p or path.startswith(p) for p in ALLOWED_PREFIXES):
        return False
    # Cherry-pick: dated folders must be TODAY only (cloud already keeps history).
    m = DATE_DIR_RE.match(path)
    if m and m.group(1) != TODAY:
        print(f"skip historical dated path: {path}")
        return False
    m = ROUND_DIR_RE.match(path)
    if m and m.group(1) != TODAY:
        print(f"skip historical dated path: {path}")
        return False
    return True


def parse_status_paths() -> list[tuple[str, str]]:
    """Return list of (xy_code, path) for porcelain entries under allowed prefixes."""
    result = run_git("status", "--porcelain", "-u", "--", *ALLOWED_PREFIXES)
    if result.returncode != 0:
        print(f"ERROR: git status failed: {result.stderr.strip()}", file=sys.stderr)
        return []
    out: list[tuple[str, str]] = []
    for raw in result.stdout.splitlines():
        if not raw or len(raw) < 4:
            continue
        code = raw[:2]
        path = raw[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[-1].strip()
        path = path.strip('"').replace("\\", "/")
        out.append((code, path))
    return out


def main() -> int:
    # Clear prior index selections so unrelated dirt cannot ride along.
    run_git("reset", "HEAD", "--", ".")

    staged: list[str] = []
    skipped_deletes: list[str] = []

    for code, path in parse_status_paths():
        if not is_allowed(path):
            continue
        # Any delete bit in index or worktree → never stage
        if "D" in code:
            skipped_deletes.append(path)
            print(f"skip delete: {path}")
            continue
        add = run_git("add", "--", path)
        if add.returncode != 0:
            print(f"WARN: git add failed for {path}: {add.stderr.strip()}")
            continue
        staged.append(path)

    # Belt-and-suspenders: unstage any deletion that slipped into the index
    cached = run_git("diff", "--cached", "--name-only", "--diff-filter=D")
    blocked = 0
    for path in cached.stdout.splitlines():
        path = path.strip().replace("\\", "/")
        if not path:
            continue
        print(f"unstage accidental delete: {path}")
        run_git("restore", "--staged", "--", path)
        blocked += 1

    if blocked:
        print(f"ERROR: refused {blocked} staged deletion(s)", file=sys.stderr)
        run_git("reset", "HEAD", "--", ".")
        return 2

    print(f"staged_count={len(staged)}")
    for path in staged:
        print(f"  {path}")
    print(f"skipped_deletes={len(skipped_deletes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
