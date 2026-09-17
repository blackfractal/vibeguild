"""Bounded notification wait; never reads or acknowledges an inbox."""
from __future__ import annotations
import math
import time
import uuid

from .core import FileLock, Problem


def tripwire(request, endpoint, project, agent, session, credential, location, after, max_seconds=300):
    if after < 0 or not math.isfinite(max_seconds) or max_seconds <= 0:
        raise Problem("tripwire requires --after >= 0 and a finite --max-seconds > 0")
    # Canonical UUIDs also keep the local lock path independent of caller spelling.
    identity = "_".join(str(uuid.UUID(value)) for value in (project, agent, session))
    lock = FileLock(location / "tripwires" / (identity + ".lock"), "A tripwire already owns this session; collect or stop it before rearming")
    try:
        deadline = time.monotonic() + max_seconds
        first = True
        while True:
            remaining = deadline - time.monotonic()
            result = request(endpoint, "/api/watch", {"project": project, "after": after,
                             "timeout": 0 if first else min(30, max(0, remaining))}, credential)
            first = False
            control = result.get("control") if isinstance(result, dict) else None
            if (not isinstance(result, dict) or type(result.get("changed")) is not bool or
                    type(result.get("seq")) is not int or result["seq"] < after or
                    not isinstance(control, dict) or
                    any(type(control.get(key)) is not bool for key in ("paused", "agent_paused", "budget_paused")) or
                    "pending_batch" not in result or
                    result["pending_batch"] is not None and not isinstance(result["pending_batch"], str)):
                raise Problem("Malformed watch response (or coordinator needs updating); monitoring stopped")
            if result["pending_batch"] is not None:
                raise Problem(f"Unacknowledged batch {result['pending_batch']}; consume/recover it before rearming. Nothing was acknowledged.")
            if any(control[key] for key in ("paused", "agent_paused", "budget_paused")):
                return {**result, "reason": "paused"}
            if result["changed"]:
                return {**result, "reason": "changed"}
            if time.monotonic() >= deadline:
                return {**result, "reason": "timeout"}
            after = result["seq"]
    finally:
        lock.close()
