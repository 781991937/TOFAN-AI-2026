"""Specialty-specific visual identity for the TOFAN academy UI.

The academic core stays shared; each specialty can provide its own theme and
experience configuration without creating a separate application.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.db.curriculum_models import Specialty

router = APIRouter(prefix="/specialties", tags=["specialty-experience"])

DEFAULT_THEME = {
    "mode": "dark",
    "surface": "#0B0D10",
    "surface_elevated": "#12161B",
    "text": "#F4F1EA",
    "muted_text": "#9CA3AF",
    "accent": "#C8A85B",
    "accent_soft": "#8E763E",
    "radius": "16px",
    "density": "academic",
    "rtl": True,
}

SPECIALTY_PRESETS = {
    "AI": {
        "icon": "🤖",
        "accent": "#C8A85B",
        "accent_soft": "#8E763E",
        "motif": "neural-network",
        "dashboard_modules": ["learning_path", "ai_teacher", "models", "projects", "weak_points"],
    },
    "CS": {
        "icon": "💻",
        "accent": "#7DD3FC",
        "accent_soft": "#2563EB",
        "motif": "code-grid",
        "dashboard_modules": ["learning_path", "algorithms", "code_lab", "projects", "weak_points"],
    },
    "CYBER": {
        "icon": "🛡️",
        "accent": "#A3E635",
        "accent_soft": "#4D7C0F",
        "motif": "security-grid",
        "dashboard_modules": ["learning_path", "security_lab", "threats", "projects", "weak_points"],
    },
    "SE": {
        "icon": "⚙️",
        "accent": "#C4B5FD",
        "accent_soft": "#6D28D9",
        "motif": "architecture",
        "dashboard_modules": ["learning_path", "architecture", "testing", "devops", "projects"],
    },
    "DS": {
        "icon": "📊",
        "accent": "#67E8F9",
        "accent_soft": "#0891B2",
        "motif": "data-network",
        "dashboard_modules": ["learning_path", "datasets", "analytics", "models", "projects"],
    },
}


def _theme_for(specialty: Specialty) -> dict:
    theme = dict(DEFAULT_THEME)
    preset = SPECIALTY_PRESETS.get(specialty.code.upper(), {})
    theme.update(preset)
    if specialty.icon:
        theme["icon"] = specialty.icon
    if specialty.theme_config_json:
        try:
            custom = json.loads(specialty.theme_config_json)
            if isinstance(custom, dict):
                theme.update(custom)
        except json.JSONDecodeError:
            pass
    return theme


@router.get("/{specialty_id}/experience")
def get_specialty_experience(specialty_id: str, lang: str = "ar", db: Session = Depends(get_db)):
    specialty = db.scalar(
        select(Specialty).where(
            Specialty.id == specialty_id,
            Specialty.is_active.is_(True),
        )
    )
    if specialty is None:
        raise HTTPException(status_code=404, detail="Specialty not found.")

    if lang not in {"ar", "en"}:
        raise HTTPException(status_code=400, detail="Unsupported language. Use ar or en.")

    name = (specialty.name_ar if lang == "ar" else specialty.name_en) or specialty.name
    description = (specialty.description_ar if lang == "ar" else specialty.description_en) or specialty.description

    return {
        "locale": lang,
        "direction": "rtl" if lang == "ar" else "ltr",
        "specialty": {
            "id": specialty.id,
            "code": specialty.code,
            "name": name,
            "name_ar": specialty.name_ar or specialty.name,
            "name_en": specialty.name_en or specialty.name,
            "description": description,
            "description_ar": specialty.description_ar or specialty.description,
            "description_en": specialty.description_en or specialty.description,
        },
        "theme": _theme_for(specialty),
        "principle": "Shared TOFAN Core + specialty-specific visual identity and learning modules.",
    }
