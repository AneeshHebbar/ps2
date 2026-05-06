"""
models.py  –  Data models for Smart Delivery Dispatch System
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class Priority(Enum):
    HIGH   = "high"
    NORMAL = "normal"
    LOW    = "low"

    def rank(self) -> int:
        return {"high": 3, "normal": 2, "low": 1}[self.value]

    def weight(self, cfg: "SystemConfig") -> float:
        return {
            "high":   cfg.priority_weight_high,
            "normal": cfg.priority_weight_normal,
            "low":    cfg.priority_weight_low,
        }[self.value]


class OrderStatus(Enum):
    PENDING    = "PENDING"
    ASSIGNED   = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED  = "DELIVERED"


# ── Coordinate ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Coord:
    x: int
    y: int

    def __str__(self):
        return f"({self.x},{self.y})"


# ── Domain objects ────────────────────────────────────────────────────────────

@dataclass
class Order:
    order_id:    str
    timestamp:   datetime
    location:    Coord
    prep_time:   float          # minutes
    priority:    Priority
    sla_minutes: float          # deadline = timestamp + sla_minutes

    # mutable state
    status:             OrderStatus      = OrderStatus.PENDING
    assigned_agent_id:  Optional[str]    = None
    assigned_at:        Optional[datetime] = None
    delivered_at:       Optional[datetime] = None
    sla_violated:       bool             = False

    @property
    def sla_deadline(self) -> datetime:
        from datetime import timedelta
        return self.timestamp + timedelta(minutes=self.sla_minutes)

    def delivery_duration_minutes(self) -> Optional[float]:
        if self.delivered_at:
            return (self.delivered_at - self.timestamp).total_seconds() / 60
        return None

    def sla_margin_minutes(self) -> Optional[float]:
        if self.delivered_at:
            return (self.sla_deadline - self.delivered_at).total_seconds() / 60
        return None


@dataclass
class Agent:
    agent_id:         str
    current_location: Coord
    rating:           float
    active_orders:    list[str] = field(default_factory=list)
    cumulative_assignments: int = 0

    def is_available(self, max_active: int) -> bool:
        return len(self.active_orders) < max_active

    def add_order(self, order_id: str, max_active: int) -> bool:
        if len(self.active_orders) >= max_active:
            return False
        self.active_orders.append(order_id)
        self.cumulative_assignments += 1
        return True

    def remove_order(self, order_id: str, new_location: Coord):
        self.active_orders = [o for o in self.active_orders if o != order_id]
        self.current_location = new_location


@dataclass
class SystemConfig:
    max_active_orders_per_agent:    int   = 2
    decision_latency_target_seconds: float = 5.0
    default_sla_minutes:            float = 50.0
    priority_weight_high:           float = 1.5
    priority_weight_normal:         float = 1.0
    priority_weight_low:            float = 0.8
    # scoring weights (internal defaults, not in CSV)
    w_delivery_time:    float = 0.30
    w_sla_risk:         float = 0.30
    w_fairness:         float = 0.20
    w_priority:         float = 0.10
    w_rating:           float = 0.10


@dataclass
class Candidate:
    agent:               Agent
    order:               Order
    travel_time:         float   # minutes (with delay_multiplier applied)
    estimated_total:     float   # travel + prep
    score:               float = 0.0
