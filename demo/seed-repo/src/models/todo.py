"""Todo data model."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class Todo:
    id: int
    title: str
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
