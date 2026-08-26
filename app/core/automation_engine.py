"""Pure Python automation engine.

No Telegram/aiogram imports live here.  This is the reusable engine for
extracting documents, splitting lessons/pages and preparing local analysis.
"""

import json
from dataclasses import dataclass
from typing import Any

from app.services.file_extractor import FileExtractor, clean_text, page_parts, split_lessons
from app.services.local_engine import local_analysis


@dataclass(slots=True)
class LessonPage:
    number: int
    text: str
    summary: str
    key_points: list[str]
    terms: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "page": self.number,
            "text": self.text,
            "summary": self.summary,
            "key_points": self.key_points,
            "terms": self.terms,
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
        pages: list[dict[str, Any]] = []
        for number, body in page_parts(clean_text(text)):
            analysis = local_analysis(body)
            pages.append(
                LessonPage(
                    number=int(number),
                    text=body,
                    summary=str(analysis.get("summary") or "")[:2200],
                    key_points=[str(x) for x in (analysis.get("key_points") or [])[:6]],
                    terms=[str(x) for x in (analysis.get("english_terms") or [])[:8]],
                ).as_dict()
            )
        return pages

    def serialize_pages(self, pages: list[dict[str, Any]]) -> str:
        return json.dumps(pages, ensure_ascii=False)

    def analyze(self, text: str) -> dict[str, Any]:
        return local_analysis(clean_text(text))
