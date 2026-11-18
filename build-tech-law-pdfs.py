#!/usr/bin/env python3
"""Build tech-law PDFs per law topic and one combined PDF per round date.

Outputs (under data/{YYYY-MM-DD}/):
  - pdfs/{NN}_{title}.pdf          one file per law / topic heading
  - {YYYY-MM-DD}_tech-law.pdf      combined round PDF (OneDrive / Daily-News)

Also mirrors copies into Documents/รอบวันที่_{date}/ when that folder exists:
  - {date}_tech-law.pdf
  - {NN}_.../5_เอกสารสรุปและเปรียบเทียบข้อกฎหมาย.pdf

Requires: fpdf2 + a Thai TrueType font on Windows (Leelawadee UI / Tahoma).
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = REPO / "data"
DOCROOT = REPO / "Documents"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROUND_RE = re.compile(r"^รอบวันที่_(\d{4}-\d{2}-\d{2})$")
SAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\LeelawUI.ttf"),
    Path(r"C:\Windows\Fonts\leelawad.ttf"),
    Path(r"C:\Windows\Fonts\tahoma.ttf"),
    Path(r"C:\Windows\Fonts\cordia.ttc"),
]
FONT_BOLD_CANDIDATES = [
    Path(r"C:\Windows\Fonts\LeelaUIb.ttf"),
    Path(r"C:\Windows\Fonts\leelawdb.ttf"),
    Path(r"C:\Windows\Fonts\tahomabd.ttf"),
]


class _HtmlToBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._buf: list[str] = []
        self._in_li = False
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._skip = True
            return
        if tag in {"br", "hr"}:
            self._flush("p")
        elif tag in {"h1", "h2", "h3", "h4", "strong", "b"}:
            self._flush("p")
            self._pending_style = "h" if tag.startswith("h") else "b"
        elif tag == "li":
            self._flush("p")
            self._in_li = True
        elif tag in {"p", "tr", "div", "table", "ul", "ol"}:
            self._flush("p")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._skip = False
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self._flush("h")
        elif tag in {"p", "div", "tr"}:
            self._flush("p")
        elif tag == "li":
            self._flush("li")
            self._in_li = False
        elif tag in {"strong", "b"}:
            # keep running; style applied at flush if whole block was bold
            pass

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.replace("\xa0", " ")
        if text.strip():
            self._buf.append(text)

    def _flush(self, style: str) -> None:
        text = "".join(self._buf).strip()
        self._buf.clear()
        if not text:
            return
        if self._in_li and style == "p":
            style = "li"
        if style == "li" and not text.startswith("•"):
            text = f"• {text}"
        self.blocks.append((style, text))

    def close(self) -> None:
        self._flush("li" if self._in_li else "p")
        super().close()


def html_to_blocks(raw_html: str) -> list[tuple[str, str]]:
    parser = _HtmlToBlocks()
    parser.feed(raw_html or "")
    parser.close()
    if parser.blocks:
        return parser.blocks
    plain = re.sub(r"<[^>]+>", " ", raw_html or "")
    plain = html_lib.unescape(re.sub(r"\s+", " ", plain)).strip()
    return [("p", plain)] if plain else []


def pick_font() -> tuple[Path, Path | None]:
    regular = next((p for p in FONT_CANDIDATES if p.is_file()), None)
    if regular is None:
        raise FileNotFoundError("ไม่พบฟอนต์ไทยใน C:\\Windows\\Fonts (Leelawadee/Tahoma)")
    bold = next((p for p in FONT_BOLD_CANDIDATES if p.is_file()), None)
    return regular, bold


def safe_filename(name: str, max_len: int = 120) -> str:
    cleaned = SAFE_NAME_RE.sub("_", name).strip(" ._")
    cleaned = re.sub(r"\s+", "_", cleaned)
    if not cleaned:
        cleaned = "เอกสาร"
    return cleaned[:max_len]


def sanitize_pdf_text(text: str) -> str:
    """Normalize text so fpdf2 can wrap Thai runs that lack spaces."""
    if not text:
        return ""
    text = html_lib.unescape(text)
    # Replace characters that often break layout / missing from UI fonts
    replacements = {
        "\u00a0": " ",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00ad": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[\r\t]+", " ", text)
    # Drop emoji / symbols missing from Leelawadee so fpdf2 does not warn/fail
    text = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF"
        r"\U0001F1E0-\U0001F1FF\uFE0F\u20E3\u2610\u2611\u2705\u274C\u2B50]+",
        "",
        text,
    )
    text = re.sub(r" +", " ", text).strip()
    # Insert soft wrap hints every 28 chars inside long space-less chunks (Thai)
    parts: list[str] = []
    for chunk in re.split(r"(\s+)", text):
        if not chunk or chunk.isspace():
            parts.append(chunk)
            continue
        if len(chunk) <= 28:
            parts.append(chunk)
            continue
        pieces = [chunk[i : i + 28] for i in range(0, len(chunk), 28)]
        parts.append("\u200b".join(pieces))
    return "".join(parts)


def cell(pdf, text: str, *, bold: bool = False, size: int = 11, h: float = 6.5) -> None:
    from fpdf.enums import XPos, YPos

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Thai", "B" if bold else "", size)
    safe = sanitize_pdf_text(text)
    if not safe:
        return
    try:
        pdf.multi_cell(0, h, safe, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    except Exception:
        # Last resort: hard-wrap ASCII-safe chunks
        for i in range(0, len(safe), 40):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, h, safe[i : i + 40], new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def load_content(date: str) -> dict:
    path = DATA / date / "content.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_image(date: str, rel: str | None) -> Path | None:
    if not rel:
        return None
    path = (DATA / date / rel).resolve()
    try:
        path.relative_to((DATA / date).resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def make_pdf() -> "FPDF":
    from fpdf import FPDF

    regular, bold = pick_font()
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    pdf.add_font("Thai", "", str(regular))
    if bold:
        pdf.add_font("Thai", "B", str(bold))
    else:
        pdf.add_font("Thai", "B", str(regular))
    return pdf


def write_header(pdf, title: str, subtitle: str) -> None:
    cell(pdf, title, bold=True, size=16, h=9)
    pdf.ln(1)
    pdf.set_text_color(80, 80, 80)
    cell(pdf, subtitle, size=11, h=7)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def write_blocks(pdf, blocks: list[tuple[str, str]]) -> None:
    for style, text in blocks:
        if style == "h":
            pdf.ln(2)
            cell(pdf, text, bold=True, size=13, h=7)
            pdf.ln(1)
        elif style == "li":
            cell(pdf, text, size=11, h=6.5)
        else:
            cell(pdf, text, size=11, h=6.5)
            pdf.ln(1)


def write_image(pdf, path: Path | None, caption: str, max_w: float = 120) -> None:
    if path is None or not path.is_file():
        return
    pdf.ln(2)
    cell(pdf, caption, bold=True, size=11, h=6)
    pdf.set_x(pdf.l_margin)
    try:
        pdf.image(str(path), w=max_w)
    except Exception as exc:  # noqa: BLE001 - keep PDF even if one image fails
        cell(pdf, f"(ใส่ภาพไม่สำเร็จ: {path.name} - {exc})", size=10, h=6)
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)


def write_comments(pdf, comments: list[str]) -> None:
    if not comments:
        return
    pdf.add_page()
    cell(pdf, "เนื้อหาโพสต์โซเชียล / ความเห็น", bold=True, size=13, h=7)
    pdf.ln(2)
    for item in comments:
        cell(pdf, item.strip(), size=11, h=6.5)
        pdf.ln(3)


def build_post_pdf(date: str, post: dict, out_path: Path) -> Path:
    pdf = make_pdf()
    pdf.add_page()
    title = str(post.get("title") or post.get("id") or "กฎหมายไอที")
    announce = post.get("announcement_date") or date
    source = post.get("source_url") or "-"
    write_header(
        pdf,
        title.replace("_", " "),
        f"รอบวันที่ {date} | วันที่ประกาศ: {announce}\nแหล่งอ้างอิง: {source}",
    )
    write_blocks(pdf, html_to_blocks(post.get("content_html") or ""))
    write_image(pdf, resolve_image(date, post.get("infographic_image")), "ภาพอินโฟกราฟิก 9:16", max_w=100)
    write_image(pdf, resolve_image(date, post.get("relationship_image")), "แผนผังความสัมพันธ์", max_w=170)
    write_comments(pdf, list(post.get("comments") or []))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def build_round_pdf(date: str, posts: list[dict], out_path: Path) -> Path:
    pdf = make_pdf()
    pdf.add_page()
    write_header(
        pdf,
        f"สรุปกฎหมายไอที — รอบวันที่ {date}",
        f"จำนวนฉบับในรอบนี้: {len(posts)} | Tech-Law Thailand",
    )
    cell(pdf, "สารบัญตามหัวข้อ", bold=True, size=12, h=7)
    pdf.ln(1)
    for i, post in enumerate(posts, start=1):
        title = str(post.get("title") or post.get("id")).replace("_", " ")
        cell(pdf, f"{i}. {title}", size=11, h=6.5)
    for i, post in enumerate(posts, start=1):
        pdf.add_page()
        title = str(post.get("title") or post.get("id")).replace("_", " ")
        announce = post.get("announcement_date") or date
        source = post.get("source_url") or "-"
        write_header(
            pdf,
            f"{i}. {title}",
            f"วันที่ประกาศ: {announce}\nแหล่งอ้างอิง: {source}",
        )
        write_blocks(pdf, html_to_blocks(post.get("content_html") or ""))
        write_image(pdf, resolve_image(date, post.get("infographic_image")), "ภาพอินโฟกราฟิก 9:16", max_w=100)
        write_image(pdf, resolve_image(date, post.get("relationship_image")), "แผนผังความสัมพันธ์", max_w=170)
        comments = list(post.get("comments") or [])
        if comments:
            pdf.ln(2)
            cell(pdf, "โพสต์โซเชียล (ย่อ)", bold=True, size=12, h=7)
            snippet = comments[0].strip()
            if len(snippet) > 1200:
                snippet = snippet[:1200] + "..."
            cell(pdf, snippet, size=10, h=6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def mirror_to_documents(date: str, post_pdfs: list[tuple[dict, Path]], round_pdf: Path) -> None:
    round_dir = DOCROOT / f"รอบวันที่_{date}"
    if not round_dir.is_dir():
        return
    dest_round = round_dir / f"{date}_tech-law.pdf"
    dest_round.write_bytes(round_pdf.read_bytes())
    print(f"[DOC] {dest_round.relative_to(REPO)}")
    folders = sorted(p for p in round_dir.iterdir() if p.is_dir())
    by_prefix: dict[str, Path] = {}
    for folder in folders:
        m = re.match(r"^(\d+)_", folder.name)
        if m:
            by_prefix[m.group(1)] = folder
    for post, pdf_path in post_pdfs:
        pid = str(post.get("id") or "")
        prefix = pid.split("-", 1)[0] if pid else ""
        folder = by_prefix.get(prefix)
        if folder is None and folders:
            # fallback: match by title fragment
            title = str(post.get("title") or "")
            folder = next((f for f in folders if title and title in f.name), None)
        if folder is None:
            continue
        dest = folder / "5_เอกสารสรุปและเปรียบเทียบข้อกฎหมาย.pdf"
        dest.write_bytes(pdf_path.read_bytes())
        print(f"[DOC] {dest.relative_to(REPO)}")


def build_for_date(date: str, also_documents: bool = True) -> dict:
    if not DATE_RE.match(date):
        raise ValueError(f"invalid date: {date}")
    doc = load_content(date)
    posts = list(doc.get("posts") or [])
    if not posts:
        raise ValueError(f"no posts in data/{date}/content.json")

    pdf_dir = DATA / date / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    post_pdfs: list[tuple[dict, Path]] = []
    for post in posts:
        pid = str(post.get("id") or "post")
        name = safe_filename(pid) + ".pdf"
        out = pdf_dir / name
        build_post_pdf(date, post, out)
        post_pdfs.append((post, out))
        print(f"[PDF] {out.relative_to(REPO)}")

    round_pdf = DATA / date / f"{date}_tech-law.pdf"
    build_round_pdf(date, posts, round_pdf)
    print(f"[PDF] {round_pdf.relative_to(REPO)}")

    if also_documents:
        mirror_to_documents(date, post_pdfs, round_pdf)

    return {
        "date": date,
        "posts": len(posts),
        "round_pdf": round_pdf.as_posix(),
        "post_pdfs": [p.as_posix() for _, p in post_pdfs],
    }


def discover_dates(explicit: list[str] | None) -> list[str]:
    if explicit:
        return explicit
    dates: list[str] = []
    if DATA.is_dir():
        for path in sorted(DATA.iterdir()):
            if path.is_dir() and DATE_RE.match(path.name) and (path / "content.json").is_file():
                dates.append(path.name)
    return dates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="สร้าง PDF รายกฎหมายและรายรอบวันที่ลง data/")
    parser.add_argument("--date", action="append", dest="dates", help="YYYY-MM-DD (repeatable)")
    parser.add_argument(
        "--date-dir",
        action="append",
        dest="date_dirs",
        help="Documents/รอบวันที่_YYYY-MM-DD (ใช้วันที่จากชื่อโฟลเดอร์)",
    )
    parser.add_argument("--all", action="store_true", help="สร้างทุกวันที่มี content.json")
    parser.add_argument("--no-documents", action="store_true", help="ไม่คัดลอก PDF ไป Documents/")
    args = parser.parse_args(argv)

    dates: list[str] = list(args.dates or [])
    for raw in args.date_dirs or []:
        path = Path(raw)
        m = ROUND_RE.match(path.name)
        if not m:
            print(f"ERROR: bad --date-dir {raw}", file=sys.stderr)
            return 2
        dates.append(m.group(1))
    if args.all or not dates:
        dates = discover_dates(dates if dates else None)
    # unique preserve order
    seen: set[str] = set()
    ordered = []
    for d in dates:
        if d not in seen:
            seen.add(d)
            ordered.append(d)

    if not ordered:
        print("ERROR: no dates with content.json", file=sys.stderr)
        return 2

    results = []
    errors = 0
    for date in ordered:
        try:
            results.append(build_for_date(date, also_documents=not args.no_documents))
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"[FAIL] {date}: {exc}", file=sys.stderr)

    print(json.dumps({"ok": len(results), "fail": errors, "results": results}, ensure_ascii=False))
    return 0 if results and errors == 0 else (1 if results else 2)


if __name__ == "__main__":
    raise SystemExit(main())
