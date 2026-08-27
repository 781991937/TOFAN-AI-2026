"""Pure Python automation engine.

This layer is deliberately independent from Telegram and from the AI engine.
It owns document extraction, lesson splitting and deterministic page building.
"""

import json
from dataclasses import dataclass
from typing import Any

from app.services.file_extractor import FileExtractor, clean_text, page_parts, split_lessons


@dataclass(slots=True)
class LessonPage:
    number: int
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "page": self.number,
            "text": self.text,
            "summary": "",
            "key_points": [],
            "terms": [],
        }


class AutomationEngine:
    """Framework-independent Python engine for the Bot/Automation domain."""

    def __init__(self, extractor: FileExtractor) -> None:
        self.extractor = extractor

    def extract(self, path) -> str:
        return clean_text(self.extractor.extract(path))

    def split_lessons(self, text: str) -> list[tuple[str, str]]:
        text = clean_text(text)
        return split_lessons(text) or [("الدرس الكامل", text)]

    def build_pages(self, text: str) -> list[dict[str, Any]]:
        """Build deterministic pages only; no AI/local analysis is performed."""
        return [LessonPage(number=int(number), text=body).as_dict() for number, body in page_parts(clean_text(text))]

    def serialize_pages(self, pages: list[dict[str, Any]]) -> str:
        return json.dumps(pages, ensure_ascii=False)

    def analyze(self, text: str) -> dict[str, Any]:
        """Compatibility method: deterministic metadata only, never AI."""
        clean = clean_text(text)
        return {"summary": "", "concepts": [], "key_points": [], "english_terms": [], "text_length": len(clean)}
