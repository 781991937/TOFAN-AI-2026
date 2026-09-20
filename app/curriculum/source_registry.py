"""Traceable global reference registry for TOFAN curriculum content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs" / "curricula" / "global_source_registry_v1.json"


def load_source_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def get_source(source_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in load_source_registry()["sources"] if item["id"] == source_id),
        None,
    )


def validate_source_ids(source_ids: list[str]) -> list[str]:
    known = {item["id"] for item in load_source_registry()["sources"]}
    return [source_id for source_id in source_ids if source_id not in known]
