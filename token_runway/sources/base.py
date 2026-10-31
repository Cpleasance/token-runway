"""Base provider abstractions and normalized data models for Token Runway."""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QuotaWindow:
    """Represents a single quota window (e.g., 5-hour, weekly, monthly)."""

    name: str
    used_pct: Optional[int] = None
    remaining_pct: Optional[float] = None
    remaining_count: Optional[float] = None
    total_entitlement: Optional[float] = None
    resets_at: Optional[str] = None
    resets_in_minutes: Optional[int] = None
    status: str = "ok"  # "ok", "warning", "exhausted", "not_on_plan", "unlimited", "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ProviderReading:
    """Normalized usage telemetry reading from one AI provider."""

    provider: str
    display_name: str
    available: bool = True
    error_message: Optional[str] = None
    plan: Optional[str] = None
    account: Optional[str] = None
    windows: List[QuotaWindow] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "available": self.available,
            "error_message": self.error_message,
            "plan": self.plan,
            "account": self.account,
            "windows": [w.to_dict() for w in self.windows],
            "timestamp": self.timestamp,
        }


def calculate_minutes_until(target_time_iso: Optional[str]) -> Optional[int]:
    """Calculate minutes remaining from now until target ISO timestamp."""
    if not target_time_iso:
        return None
    try:
        # Handle trailing Z or timezone offsets
        clean = target_time_iso.replace("Z", "+00:00")
        if "T" not in clean:
            # Date-only fallback ("2026-11-01") -> midnight UTC
            clean = f"{clean}T00:00:00+00:00"
        target = datetime.datetime.fromisoformat(clean)
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = (target - now).total_seconds()
        return max(0, int(round(diff / 60.0)))
    except Exception:
        return None
