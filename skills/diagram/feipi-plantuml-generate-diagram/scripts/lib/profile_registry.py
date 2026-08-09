#!/usr/bin/env python3
"""Profile 注册表：只把已经完整实现的图类型路由到 typed profile。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

LIB_DIR = Path(__file__).resolve().parent
SKILL_DIR = LIB_DIR.parent.parent

PROFILES: dict[str, dict[str, Any]] = {
    "fallback": {
        "profile": "fallback",
        "profile_version": "1.0",
        "brief_schema": None,
        "template": None,
        "coverage_mode": "basic",
        "layout_mode": "basic",
    },
    "architecture": {
        "profile": "architecture",
        "profile_version": "1.0",
        "brief_schema": str(SKILL_DIR / "assets" / "validation" / "types" / "architecture-brief.schema.json"),
        "template": str(SKILL_DIR / "assets" / "templates" / "types" / "architecture-brief.yaml"),
        "coverage_mode": "architecture",
        "layout_mode": "architecture",
    },
    "sequence": {
        "profile": "sequence",
        "profile_version": "1.1",
        "brief_schema": str(SKILL_DIR / "assets" / "validation" / "types" / "sequence-brief.schema.json"),
        "template": str(SKILL_DIR / "assets" / "templates" / "types" / "sequence-brief.yaml"),
        "coverage_mode": "sequence",
        "layout_mode": "sequence",
    },
    "component": {
        "profile": "component",
        "profile_version": "1.1",
        "brief_schema": str(SKILL_DIR / "assets" / "validation" / "types" / "component-brief.schema.json"),
        "template": str(SKILL_DIR / "assets" / "templates" / "types" / "component-brief.yaml"),
        "coverage_mode": "component",
        "layout_mode": "component",
    },
    "activity": {
        "profile": "activity",
        "profile_version": "1.1",
        "brief_schema": str(SKILL_DIR / "assets" / "validation" / "types" / "activity-brief.schema.json"),
        "template": str(SKILL_DIR / "assets" / "templates" / "types" / "activity-brief.yaml"),
        "coverage_mode": "activity",
        "layout_mode": "activity",
    },
    "deployment": {
        "profile": "deployment",
        "profile_version": "1.1",
        "brief_schema": str(SKILL_DIR / "assets" / "validation" / "types" / "deployment-brief.schema.json"),
        "template": str(SKILL_DIR / "assets" / "templates" / "types" / "deployment-brief.yaml"),
        "coverage_mode": "deployment",
        "layout_mode": "deployment",
    },
}


def get_profile(diagram_type: str) -> dict[str, Any] | None:
    return PROFILES.get(diagram_type)


def list_profiles() -> list[str]:
    return sorted(PROFILES.keys())


def is_typed_profile(diagram_type: str) -> bool:
    return diagram_type != "fallback" and diagram_type in PROFILES


def resolve_profile(diagram_type: str) -> dict[str, Any]:
    """未知图型明确降级到 fallback，不假装已具备 typed 校验。"""
    return PROFILES.get(diagram_type, PROFILES["fallback"])
