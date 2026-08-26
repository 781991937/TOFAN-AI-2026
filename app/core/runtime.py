"""Application composition root for the Python runtime.

This module owns construction of shared Python services.  Telegram routers
consume the services through the dispatcher; they do not construct or own
the engines themselves.
"""

from dataclasses import dataclass

from app.config_gemini import Settings
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator
from .ai_engine import AIEngine
from .automation_engine import AutomationEngine


@dataclass(slots=True)
class PythonRuntime:
    settings: Settings
    db: Database
    extractor: FileExtractor
    ai: AIEngine
    automation: AutomationEngine

    @classmethod
    def build(cls, settings: Settings) -> "PythonRuntime":
        db = Database(settings.database_url or str(settings.database_path))
        extractor = FileExtractor()
        ai_service = AIService(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.database_path,
        )
        quiz_generator = QuizGenerator(ai_service, settings.database_path)
        return cls(
            settings=settings,
            db=db,
            extractor=extractor,
            ai=AIEngine(ai_service, quiz_generator),
            automation=AutomationEngine(extractor),
        )
