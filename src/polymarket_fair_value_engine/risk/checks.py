from __future__ import annotations

import os
from pathlib import Path


def guard_live_mode(live: bool, ack_live_risk: bool, live_enabled: bool) -> None:
    if not live:
        return
    if not ack_live_risk:
        raise RuntimeError("Live mode requires --ack-live-risk.")
    if not live_enabled:
        raise RuntimeError("Live mode is disabled in config. Set PMFE_LIVE_ENABLED=1 to proceed.")


def kill_switch_engaged() -> bool:
    path = os.getenv("PMFE_KILL_SWITCH_FILE", "").strip()
    return bool(path) and Path(path).exists()

