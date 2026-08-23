from pathlib import Path
import re

from docx import Document
from pypdf import PdfReader

PAGE_MARKER_RE = re.compile(r"^\[\[PAGE:(\d+)\]\]$")


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
        parts = []
        for number, page in enumerate(reader.pages, start=1):
            parts.append(f"[[PAGE:{number}]]")
            parts.append(page.extract_text() or "")
        return "\n\n".join(parts)

    @staticmethod
    def _docx(path: Path) -> str:
        document = Document(str(path))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts)


_REVERSED_HINTS = {
    "ىلإ", "نم", "يف", "نع", "ىلع", "اذه", "هذه", "وه", "يه", "فصن", "مرتلا",
    "رابتخا", "ىنعملا", "ةملكلا", "قطنلا", "يبرعلاب", "ةلماك", "تابيردتلا", "لاثملاب",
    "ةليللا", "مهفا", "ظفحلل", "ةدعاقلا", "تاملعم", "تاملك", "ثحب",
}


def _fix_reversed_arabic_word(word: str) -> str:
    if re.fullmatch(r"[\u0600-\u06FF]+", word) and len(word) >= 2:
        return word[::-1]
    return word


def _repair_arabic_line(line: str) -> str:
    arabic_words = re.findall(r"[\u0600-\u06FF]+", line)
    if len(arabic_words) < 2:
        return line
    hints = sum(1 for word in arabic_words if word in _REVERSED_HINTS)
    if hints == 0:
        return line
    tokens = re.split(r"(\s+)", line)
    return "".join(_fix_reversed_arabic_word(t) for t in tokens)


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\u00ad", "").replace("\ufeff", "")
    cleaned = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        if PAGE_MARKER_RE.fullmatch(line):
            cleaned.append(line)
            continue
        line = _repair_arabic_line(line)
        if re.fullmatch(r"(?:Page|صفحة)\s*\d+", line, flags=re.I):
            continue
        if re.fullmatch(r"[-_=·•\s]{3,}", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def page_parts(text: str) -> list[tuple[int, str]]:
    """Return real PDF pages when page markers exist; otherwise one logical page."""
    text = clean_text(text)
    matches = list(PAGE_MARKER_RE.finditer(text))
    if not matches:
        return [(1, text)] if text else []
    pages = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        number = int(match.group(1))
        if body:
            pages.append((number, body))
    return pages


def chunk_text(text: str, max_chars: int = 10000) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


_LESSON_HEADING = re.compile(
    r"^\s*(?:(?:الدرس|درس|المحاضرة|محاضرة|الوحدة|وحدة|الفصل|فصل)\s*(?:رقم\s*)?[0-9٠-٩]+\b|"
    r"(?:lesson|lecture|unit|chapter)\s*(?:number\s*)?[0-9]+\b)\s*[:：\-–—.]?\s*(.*)$",
    re.IGNORECASE,
)


def split_lessons(text: str) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _LESSON_HEADING.match(line)
        if match:
            title = match.group(1).strip() or line.strip()
            starts.append((index, title))
    if not starts:
        return [("الدرس الكامل", text)]
    lessons: list[tuple[str, str]] = []
    for pos, (start, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            lessons.append((title, body))
    if starts[0][0] > 0 and lessons:
        intro = "\n".join(lines[:starts[0][0]]).strip()
        if intro:
            lessons[0] = (lessons[0][0], intro + "\n" + lessons[0][1])
    return lessons
