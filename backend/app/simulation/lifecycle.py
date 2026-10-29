"""Heartbeat freshness and stage gate.

Mock mode records a local acknowledgement on the same 15 second cadence.
Venue mode must be given the official payload template before a POST is sent.
"""

from __future__ import annotations


class LifecycleManager:
    def __init__(self, interval_sec: float = 15.0) -> None:
        self.interval_sec = interval_sec
        self.stage = "PREFLIGHT"
        self.last_ack = 0.0
        self.last_error = ""
        self.ack_count = 0
        self.heartbeat_status = "pending"

    def ack(self, now: float) -> None:
        self.last_ack = now
        self.ack_count += 1
        self.last_error = ""
        self.heartbeat_status = "ok"

    def fail(self, message: str) -> None:
        self.last_error = message
        self.heartbeat_status = "failing"

    def fresh(self, now: float) -> bool:
        if self.last_ack <= 0:
            return False
        return (now - self.last_ack) <= self.interval_sec + 0.25

    def allows_orders(self) -> bool:
        return self.stage == "TRADING"
