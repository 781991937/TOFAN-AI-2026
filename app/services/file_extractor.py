from pathlib import Path
import re

from docx import Document
from pypdf import PdfReader


class FileExtractor:
    SUPPORTED = {".pdf", ".docx", ".txt"}

    def extract(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED:
            raise ValueError(f"Unsupported file type: {suffix}")
        if suffix == ".pdf":
            return self._pdf(path)
        if suffix == ".docx":
            return self._docx(path)
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _pdf(path: Path) -> str:
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _docx(path: Path) -> str:
        document = Document(str(path))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts)


def _fix_reversed_arabic_word(word: str) -> str:
    """Repair the common PDF extraction case where Arabic glyph order is reversed."""
    if re.fullmatch(r"[\u0600-\u06FF]+", word) and len(word) >= 2:
        return word[::-1]
    return word


def _repair_arabic_line(line: str) -> str:
    arabic = len(re.findall(r"[\u0600-\u06FF]", line))
    latin = len(re.findall(r"[A-Za-z]", line))
    if arabic < 4 or arabic < latin:
        return line

    # pypdf may return Arabic words character-reversed while keeping word order.
    # Reverse only Arabic words so English terms, numbers, URLs and punctuation stay intact.
    tokens = re.split(r"(\s+)", line)
    return "".join(_fix_reversed_arabic_word(t) for t in tokens)


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\ufeff", "")
    cleaned = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        line = _repair_arabic_line(line)
        # Remove repeated PDF page headers/footers that pollute summaries and quizzes.
        if re.fullmatch(r"(?:Page|صفحة)\s*\d+", line, flags=re.I):
            continue
        if re.fullmatch(r"[-_=·•\s]{3,}", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def chunk_text(text: str, max_chars: int = 10000) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
