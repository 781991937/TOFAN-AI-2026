from pathlib import Path

from app.services.file_extractor import FileExtractor, chunk_text, clean_text


def test_clean_text():
    assert clean_text("  hello   world\n\n test ") == "hello world\ntest"


def test_chunk_text():
    chunks = chunk_text("abcdefghij", max_chars=3)
    assert chunks == ["abc", "def", "ghi", "j"]


def test_supported_extensions():
    assert {".pdf", ".docx", ".txt"} == FileExtractor.SUPPORTED


def test_txt_extraction(tmp_path: Path):
    path = tmp_path / "lesson.txt"
    path.write_text("درس تجريبي", encoding="utf-8")
    assert FileExtractor().extract(path) == "درس تجريبي"
