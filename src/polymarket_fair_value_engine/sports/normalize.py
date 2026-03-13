from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SportsEventMetadata:
    event_id: str
    league: str
    home_team: str
    away_team: str
    start_time: datetime

