"""The one record every packcheck check reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Failure:
    workflow: str  # "<pack>/<workflow>", or "<pack>" for pack-level failures
    check: str  # "validate" | "fixture" | "no-fixture" | "tier-model" | "relative-fence" | "exec-code"
    message: str
