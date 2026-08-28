from pathlib import Path
import json
import re

from docx import Document
from pypdf import PdfReader

try:
    import pdftotext
except ImportError:  # pragma: no cover - kept as a safety fallback for local environments
    pdftotext = None

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

PAGE_MARKER_RE = re.compile(r"^\s*\[\[PAGE:(\d+)\]\]\s*$")
PAGE_MARKER_ANY_RE = re.compile(r"\[\[PAGE:(\d+)\]\]")
LESSON_MARKER_RE = re.compile(r"^\s*\[\[LESSON:(.*?)\]\]\s*$", re.I)

_ARABIC_ORDINALS = {
    "الأول": 1, "الاول": 1, "أول": 1, "اول": 1,
    "الثاني": 2, "الثانى": 2, "ثاني": 2, "ثانى": 2,
    "الثالث": 3, "ثالث": 3,
    "الرابع": 4, "رابع": 4,
    "الخامس": 5, "خامس": 5,
    "السادس": 6, "سادس": 6,
    "السابع": 7, "سابع": 7,
    "الثامن": 8, "ثامن": 8,
    "التاسع": 9, "تاسع": 9,
    "العاشر": 10, "عاشر": 10,
}
_ENGLISH_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


class FileExtractor:
    """Extract common educational documents without involving the AI engine.

    PDF extraction uses Poppler first and keeps real page boundaries. When a
    PDF contains bookmarks/outline entries, the level-1 outline is also used
    as a reliable lesson-boundary signal.
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
        """Extract every PDF page and inject outline-based lesson markers."""
        toc_by_page: dict[int, list[str]] = {}
        if pymupdf is not None:
            try:
                doc = pymupdf.open(str(path))
                toc = doc.get_toc()
                for item in toc:
                    if len(item) >= 3 and int(item[0]) == 1 and int(item[2]) >= 1:
                        title = str(item[1] or "").strip()
                        if title:
                            toc_by_page.setdefault(int(item[2]), []).append(title)
                doc.close()
            except Exception:
                toc_by_page = {}

        if pdftotext is not None:
            try:
                with path.open("rb") as handle:
                    pdf = pdftotext.PDF(handle)
                parts = []
                for number, page in enumerate(pdf, 1):
                    for title in toc_by_page.get(number, []):
                        parts.append(f"[[LESSON:{title}]]")
                    parts.extend([f"[[PAGE:{number}]]", page or ""])
                return "\n\n".join(parts)
            except Exception:
                pass

        reader = PdfReader(str(path))
        parts = []
        for number, page in enumerate(reader.pages, 1):
            for title in toc_by_page.get(number, []):
                parts.append(f"[[LESSON:{title}]]")
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
    hints = {
        "ىلإ", "نم", "يف", "نع", "ىلع", "اذه", "هذه", "وه", "يه", "رابتخا",
        "ىنعملا", "ةملكلا", "يبرعلاب", "لاثملاب", "سردلا", "ةرضاحملا", "ةدحولا", "لصفلا",
    }
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
        page = PAGE_MARKER_ANY_RE.fullmatch(line)
        if page:
            cleaned.append(f"[[PAGE:{int(page.group(1))}]]")
            continue
        lesson = LESSON_MARKER_RE.fullmatch(line)
        if lesson:
            title = lesson.group(1).strip()
            if title:
                cleaned.append(f"[[LESSON:{title}]]")
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
            body = re.sub(r"\[\[LESSON:.*?\]\]\s*", "", body, flags=re.I)
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


def _lesson_heading(line: str):
    """Return a lesson title when a line is clearly a lesson/chapter heading."""
    value = line.strip()
    if not value or len(value) > 180:
        return None

    number = r"(?:[0-9٠-٩]+|" + "|".join(map(re.escape, _ARABIC_ORDINALS)) + r")"
    arabic = re.match(
        rf"^\s*(?:الدرس|درس|المحاضرة|محاضرة|الوحدة|وحدة|الفصل|فصل)\s*(?:رقم\s*)?({number})\b\s*[:：\-–—.]?\s*(.*)$",
        value,
        re.I,
    )
    if arabic:
        title = arabic.group(2).strip() or value
        return title

    english_number = r"(?:[0-9]+|" + "|".join(_ENGLISH_ORDINALS) + r")"
    english = re.match(
        rf"^\s*(?:lesson|lecture|unit|chapter)\s*(?:number\s*)?({english_number})\b\s*[:：\-–—.]?\s*(.*)$",
        value,
        re.I,
    )
    if english:
        title = english.group(2).strip() or value
        return title

    return None


def split_lessons(text: str) -> list[tuple[str, str]]:
    """Split a document into real lessons using explicit headings or PDF outlines."""
    text = clean_text(text)
    if not text:
        return []

    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    pending_outline_title: str | None = None

    for i, line in enumerate(lines):
        marker = LESSON_MARKER_RE.fullmatch(line.strip())
        if marker:
            pending_outline_title = marker.group(1).strip()
            starts.append((i, pending_outline_title or f"الدرس {len(starts) + 1}"))
            continue

        title = _lesson_heading(line)
        if title:
            starts.append((i, title))

    # De-duplicate a marker followed immediately by the same textual heading.
    deduped: list[tuple[int, str]] = []
    for start in starts:
        if deduped and start[0] <= deduped[-1][0] + 1:
            if len(start[1]) > len(deduped[-1][1]):
                deduped[-1] = start
        else:
            deduped.append(start)
    starts = deduped

    if not starts:
        return [("الدرس الكامل", text)]

    lessons: list[tuple[str, str]] = []
    for n, (start, title) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        body_lines = lines[start:end]
        body = "\n".join(
            line for line in body_lines
            if not LESSON_MARKER_RE.fullmatch(line.strip())
        ).strip()
        if body:
            lessons.append((title or f"الدرس {n + 1}", body))

    if starts[0][0] > 0 and lessons:
        intro = "\n".join(lines[:starts[0][0]]).strip()
        if intro and len(intro) < 3000:
            lessons[0] = (lessons[0][0], intro + "\n" + lessons[0][1])

    return lessons or [("الدرس الكامل", text)]


def chunk_text(text: str, max_chars: int = 10000) -> list[str]:
    text = clean_text(text)
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] if text else []
