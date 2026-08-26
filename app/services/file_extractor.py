from pathlib import Path
import json
import re

from docx import Document
from pypdf import PdfReader

try:
    import pdftotext
except ImportError:  # pragma: no cover - kept as a safety fallback for local environments
    pdftotext = None

PAGE_MARKER_RE = re.compile(r"^\s*\[\[PAGE:(\d+)\]\]\s*$")
PAGE_MARKER_ANY_RE = re.compile(r"\[\[PAGE:(\d+)\]\]")


class FileExtractor:
    """Extract common educational documents without involving the AI engine.

    PDF extraction uses the native ``pdftotext`` Python binding first.  This
    preserves Poppler's physical/layout-aware text extraction and page
    boundaries.  pypdf remains a defensive fallback for environments where
    the native binding is unavailable.
    """

    SUPPORTED = {
        ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".html", ".css",
        ".xml", ".yaml", ".yml", ".rst", ".tex", ".log", ".ini", ".cfg", ".rtf", ".xlsx", ".pptx"
    }

    def extract(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED:
            raise ValueError(f"Unsupported file type: {suffix}")
        if suffix == ".pdf":
            return self._pdf(path)
        if suffix == ".docx":
            return self._docx(path)
        if suffix == ".xlsx":
            return self._xlsx(path)
        if suffix == ".pptx":
            return self._pptx(path)
        if suffix == ".json":
            try:
                return json.dumps(
                    json.loads(path.read_text(encoding="utf-8", errors="replace")),
                    ensure_ascii=False,
                    indent=2,
                )
            except Exception:
                pass
        text = path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".rtf":
            text = re.sub(r"\\[a-z]+\d* ?|[{}]", "", text)
        return text

    @staticmethod
    def _pdf(path: Path) -> str:
        """Extract every PDF page with pdftotext/Poppler and retain page markers."""
        if pdftotext is not None:
            try:
                with path.open("rb") as handle:
                    pdf = pdftotext.PDF(handle)
                parts = []
                for number, page in enumerate(pdf, 1):
                    parts.extend([f"[[PAGE:{number}]]", page or ""])
                return "\n\n".join(parts)
            except Exception:
                # Fall through to pypdf instead of losing the uploaded lesson.
                pass

        reader = PdfReader(str(path))
        parts = []
        for number, page in enumerate(reader.pages, 1):
            parts.extend([f"[[PAGE:{number}]]", page.extract_text() or ""])
        return "\n\n".join(parts)

    @staticmethod
    def _docx(path: Path) -> str:
        document = Document(str(path))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts)

    @staticmethod
    def _xlsx(path: Path) -> str:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"[ورقة: {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                values = [str(v) for v in row if v is not None]
                if values:
                    parts.append(" | ".join(values))
        return "\n".join(parts)

    @staticmethod
    def _pptx(path: Path) -> str:
        from pptx import Presentation
        prs = Presentation(path)
        parts = []
        for i, slide in enumerate(prs.slides, 1):
            parts.append(f"[[PAGE:{i}]]")
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    parts.append(shape.text.strip())
        return "\n".join(parts)


def _repair_arabic_line(line: str) -> str:
    # Fix the common reversed-Arabic extraction artifact without touching normal text.
    hints = {"ىلإ", "نم", "يف", "نع", "ىلع", "اذه", "هذه", "وه", "يه", "رابتخا", "ىنعملا", "ةملكلا", "يبرعلاب", "لاثملاب"}
    words = re.findall(r"[\u0600-\u06FF]+", line)
    if len(words) < 2 or not any(w in hints for w in words):
        return line
    tokens = re.split(r"(\s+)", line)
    return "".join(
        t[::-1] if re.fullmatch(r"[\u0600-\u06FF]+", t or "") and len(t) >= 2 else t
        for t in tokens
    )


def clean_text(text: str) -> str:
    text = (text or "").replace("\x00", "").replace("\u00ad", "").replace("\ufeff", "")
    cleaned = []
    for raw in text.replace("\f", "\n").splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        marker = PAGE_MARKER_ANY_RE.fullmatch(line)
        if marker:
            cleaned.append(f"[[PAGE:{int(marker.group(1))}]]")
            continue
        if re.fullmatch(r"(?:Page|صفحة)\s*\d+", line, re.I):
            continue
        if re.fullmatch(r"[-_=·•\s]{3,}", line):
            continue
        cleaned.append(_repair_arabic_line(line))
    return "\n".join(cleaned).strip()


def page_parts(text: str, chars_per_page: int = 1800) -> list[tuple[int, str]]:
    """Return real PDF pages when markers exist; otherwise create stable virtual pages."""
    text = clean_text(text)
    if not text:
        return []
    matches = list(PAGE_MARKER_RE.finditer(text))
    if matches:
        pages = []
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[match.end():end].strip()
            if body:
                pages.append((int(match.group(1)), body))
        return pages
    chunks = []
    current = []
    size = 0
    page_no = 1
    for line in text.splitlines():
        if current and size + len(line) + 1 > chars_per_page:
            chunks.append((page_no, "\n".join(current).strip()))
            page_no += 1
            current = []
            size = 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append((page_no, "\n".join(current).strip()))
    return chunks


def split_lessons(text: str) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []
    lines = text.splitlines()
    heading = re.compile(
        r"^\s*(?:(?:الدرس|درس|المحاضرة|محاضرة|الوحدة|وحدة|الفصل|فصل)\s*(?:رقم\s*)?[0-9٠-٩]+\b|(?:lesson|lecture|unit|chapter)\s*(?:number\s*)?[0-9]+\b)\s*[:：\-–—.]?\s*(.*)$",
        re.I,
    )
    starts = []
    for i, line in enumerate(lines):
        m = heading.match(line)
        if m:
            starts.append((i, m.group(1).strip() or line.strip()))
    if not starts:
        return [("الدرس الكامل", text)]
    lessons = []
    for n, (start, title) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            lessons.append((title, body))
    if starts[0][0] > 0 and lessons:
        intro = "\n".join(lines[:starts[0][0]]).strip()
        if intro:
            lessons[0] = (lessons[0][0], intro + "\n" + lessons[0][1])
    return lessons


def chunk_text(text: str, max_chars: int = 10000) -> list[str]:
    text = clean_text(text)
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] if text else []
