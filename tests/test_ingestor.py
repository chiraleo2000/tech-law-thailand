import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

import ingestor
from content_schema import validate_post
from ingestor import (
    CopyMismatchError,
    announcement_date_from_text,
    derive_id,
    derive_slug,
    derive_title,
    ingest_date,
    ingest_dates,
    read_comments,
    resolve_image,
)

manifest_spec = importlib.util.spec_from_file_location(
    "update_manifest",
    Path(__file__).resolve().parents[1] / "update-manifest.py",
)
update_manifest_mod = importlib.util.module_from_spec(manifest_spec)
sys.modules["update_manifest"] = update_manifest_mod
manifest_spec.loader.exec_module(update_manifest_mod)

THAI = st.text(alphabet="กขคงจฉชกฎหมายไอที", min_size=1, max_size=12)


def write_docx(path: Path, paragraphs: list[str]) -> None:
    import zipfile

    body = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def law_folder(root: Path, name: str, *, info: bool = True, diagram: bool = True, social: bool = True) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    write_docx(
        folder / ingestor.DOCX_NAME,
        ["วันที่ประกาศ: 2026-07-08", "แหล่งอ้างอิง: https://ratchakitcha.soc.go.th/a", "เนื้อหากฎหมาย"],
    )
    if info:
        (folder / ingestor.INFO_NAME).write_bytes(b"png-info")
    if diagram:
        (folder / ingestor.REL_NAME).write_bytes(b"png-rel")
    if social:
        (folder / ingestor.SOCIAL_NAME).write_text("โพสต์ #กฎหมายไอที", encoding="utf-8")
    return folder


@settings(max_examples=100)
@given(number=st.integers(min_value=0, max_value=99), name=THAI)
def test_property_1_derive_title(number, name):
    title = derive_title(f"{number:02d}_{name}")
    assert title == name
    assert not title[:1].isdigit()
    assert not title.startswith("_")


@settings(max_examples=100)
@given(
    info=st.booleans(),
    diagram=st.booleans(),
    social=st.booleans(),
)
def test_property_2_optional_files(tmp_path_factory, info, diagram, social):
    root = tmp_path_factory.mktemp("round")
    date_dir = root / "รอบวันที่_2026-09-28"
    law_folder(date_dir, "01_กฎหมายทดสอบ", info=info, diagram=diagram, social=social)
    result = ingest_date(date_dir, root / "data", generated_at="2026-09-28T00:00:00Z")
    document = json.loads((root / "data" / "2026-09-28" / "content.json").read_text(encoding="utf-8"))
    post = document["posts"][0]
    assert result.written
    assert post["infographic_image"] == ("" if not info else "images/01_ภาพอินโฟกราฟิก_แนวตั้ง_9ต่อ16.png")
    assert post["relationship_image"] == ("" if not diagram else "images/01_แผนผังความสัมพันธ์กฎหมายและบุคคล.png")
    assert post["comments"] == ([] if not social else ["โพสต์ #กฎหมายไอที"])


def test_property_3_skip_folder_without_docx(tmp_path, capsys):
    date_dir = tmp_path / "รอบวันที่_2026-09-28" / "02_ไม่มีเอกสาร"
    date_dir.mkdir(parents=True)
    (date_dir / "note.txt").write_text("ว่าง", encoding="utf-8")
    assert ingestor.build_post(date_dir, "2026-09-28", tmp_path / "images") is None
    assert "ไม่พบไฟล์เนื้อหาหลัก" in capsys.readouterr().err


def _valid_post():
    return {
        "id": "01-กฎหมาย",
        "slug": "กฎหมาย",
        "title": "กฎหมาย",
        "announcement_date": "2026-07-08",
        "content_html": "<p>เนื้อหา</p>",
        "infographic_image": "",
        "relationship_image": "",
        "comments": [],
        "source_url": "https://ratchakitcha.soc.go.th/a",
        "tags": [],
    }


@settings(max_examples=100)
@given(
    field=st.sampled_from(["id", "slug", "title", "announcement_date", "content_html", "source_url"]),
    mode=st.sampled_from(["missing", "blank", "type"]),
)
def test_property_4_schema(field, mode):
    post = _valid_post()
    assert validate_post(post, 0) == []
    broken = dict(post)
    if mode == "missing":
        broken.pop(field)
    elif mode == "blank":
        broken[field] = "" if field != "announcement_date" else "ไม่ใช่วันที่"
    else:
        broken[field] = 1
    errors = validate_post(broken, 0)
    assert errors
    assert any(field in error for error in errors)


def test_property_5_and_6_manifest_add_only():
    manifest = {"entries": [{"date": "2026-09-28", "path": "data/2026-09-28/content.json", "ids": ["01-เดิม"]}]}
    merged = update_manifest_mod.merge_entry(
        manifest,
        "2026-09-28",
        "data/2026-09-28/content.json",
        ["01-เดิม", "02-ใหม่"],
    )
    assert merged["entries"][1] == manifest["entries"][0]
    assert "01-เดิม" not in merged["entries"][0]["ids"]
    assert merged["entries"][0]["ids"] == ["02-ใหม่"]
    again = update_manifest_mod.merge_entry(merged, "2026-09-28", "data/2026-09-28/content.json", ["01-เดิม", "02-ใหม่"])
    assert again["entries"] == merged["entries"]


@settings(max_examples=100)
@given(text=st.text(alphabet="กขค ABC 123", min_size=0, max_size=40))
def test_property_7_utf8_roundtrip(text):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "content.json"
        path.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8"))["text"] == text


@settings(max_examples=100)
@given(payload=st.binary(min_size=1, max_size=80))
def test_property_11_copy_bytes(tmp_path_factory, payload):
    root = tmp_path_factory.mktemp("copy")
    folder = root / "03_ทดสอบ"
    folder.mkdir()
    source = folder / ingestor.INFO_NAME
    source.write_bytes(payload)
    relative, ok = resolve_image(folder, ingestor.INFO_NAME, root / "images")
    assert ok
    assert (root / "images" / Path(relative).name).read_bytes() == payload


def test_copy_mismatch_does_not_write_content(tmp_path, monkeypatch):
    date_dir = tmp_path / "รอบวันที่_2026-09-28"
    law_folder(date_dir, "01_กฎหมายทดสอบ")
    manifest = tmp_path / "data" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text("{}\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise CopyMismatchError("ภาพ")

    monkeypatch.setattr(ingestor, "resolve_image", boom)
    result = ingest_date(date_dir, tmp_path / "data", generated_at="2026-09-28T00:00:00Z")
    assert result.manifest_ready is False
    assert not (tmp_path / "data" / "2026-09-28" / "content.json").exists()
    assert manifest.read_text(encoding="utf-8") == "{}\n"


def test_property_12_zero_dates_leave_data_untouched(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    marker = data / "manifest.json"
    marker.write_bytes(b"{}\n")
    before = marker.read_bytes()
    assert ingest_dates([], data) == []
    assert marker.read_bytes() == before


def test_property_13_ingest_idempotent(tmp_path):
    date_dir = tmp_path / "รอบวันที่_2026-09-28"
    law_folder(date_dir, "01_กฎหมายทดสอบ")
    out = tmp_path / "data"
    first = ingest_date(date_dir, out, generated_at="2026-09-28T00:00:00Z")
    second = ingest_date(date_dir, out, generated_at="2026-09-28T01:00:00Z")
    assert first.ids == second.ids
    document = json.loads((out / "2026-09-28" / "content.json").read_text(encoding="utf-8"))
    assert document["posts"][0]["title"] == "กฎหมายทดสอบ"
    assert document["generated_at"] == "2026-09-28T01:00:00Z"


def test_thai_gazette_date_and_slug():
    assert announcement_date_from_text("ราชกิจจานุเบกษา 8 กรกฎาคม 2569", "2026-09-28") == "2026-07-08"
    assert announcement_date_from_text("ลงวันที่ 2 กันยายน 2569", "2026-09-28") == "2026-09-02"
    assert ingestor.extract_source_url("อ่านประกาศ/แหล่งอ้างอิงฉบับเต็ม: thansettakij.com/general-news/663506") == "https://thansettakij.com/general-news/663506"
    assert derive_slug("พรบ.อำนวยความสะดวก_2569") == "พรบ.อำนวยความสะดวก-2569"
    assert derive_id("07_ระเบียบคณะกรรมการ_2569", "2026-09-28").startswith("07-")


def test_read_comments_missing():
    assert read_comments(None) == []


def test_update_manifest_keeps_file_when_content_missing(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"entries": []}\n', encoding="utf-8")
    before = manifest.read_bytes()
    outcome = update_manifest_mod.update_manifest(manifest, [tmp_path / "missing.json"])
    assert outcome.error
    assert manifest.read_bytes() == before


def test_corrupt_manifest_is_not_rewritten(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes("ไม่ใช่ json".encode("utf-8"))
    before = manifest.read_bytes()
    content = tmp_path / "data" / "2026-09-28" / "content.json"
    content.parent.mkdir(parents=True)
    content.write_text(
        json.dumps(
            {
                "date": "2026-09-28",
                "generated_at": "2026-09-28T00:00:00Z",
                "posts": [_valid_post()],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(update_manifest_mod.ManifestParseError):
        update_manifest_mod.load_manifest(manifest)
    outcome = update_manifest_mod.update_manifest(manifest, [content])
    assert outcome.changed is False
    assert manifest.read_bytes() == before
