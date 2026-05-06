"""
metrics.py  –  Online metrics: delivery time, SLA, fairness (Issues 12-15)
"""
import json
import logging
import math
from datetime import datetime
from typing import Optional

from models import Order, Priority

logger = logging.getLogger(__name__)


class Welford:
    """Online mean + variance (Welford's algorithm)."""
    def __init__(self):
        self.n = 0
        self._mean = 0.0
        self._M2   = 0.0

    def update(self, x: float):
        self.n += 1
        d = x - self._mean
        self._mean += d / self.n
        self._M2   += d * (x - self._mean)

    @property
    def mean(self): return self._mean if self.n else 0.0
    @property
    def variance(self): return self._M2 / self.n if self.n else 0.0
    @property
    def std(self): return math.sqrt(self.variance)

    def to_dict(self):
        return {"n": self.n, "mean": round(self.mean, 3), "std": round(self.std, 3)}


class Bucket:
    def __init__(self):
        self.delivery  = Welford()
        self.sla_margin = Welford()
        self.violations = 0

    def record(self, dur_min: float, margin_min: float):
        self.delivery.update(dur_min)
        self.sla_margin.update(margin_min)
        if margin_min < 0:
            self.violations += 1

    def to_dict(self):
        total = self.delivery.n
        rate  = self.violations / total if total else 0.0
        return {
            "completed":              total,
            "avg_delivery_time_min":  round(self.delivery.mean, 2),
            "sla_violations":         self.violations,
            "sla_violation_rate_pct": round(rate * 100, 2),
            "sla_compliance_pct":     round((1 - rate) * 100, 2),
            "avg_sla_margin_min":     round(self.sla_margin.mean, 2),
        }


class MetricsCollector:
    def __init__(self):
        self._overall = Bucket()
        self._by_prio: dict[Priority, Bucket] = {p: Bucket() for p in Priority}

    def record(self, order: Order):
        if order.delivered_at is None:
            return
        dur    = (order.delivered_at - order.timestamp).total_seconds() / 60
        margin = (order.sla_deadline - order.delivered_at).total_seconds() / 60
        if margin < 0:
            order.sla_violated = True
        self._overall.record(dur, margin)
        self._by_prio[order.priority].record(dur, margin)

    def fairness(self, assignments: list[int]) -> dict:
        if not assignments:
            return {}
        n    = len(assignments)
        mn, mx = min(assignments), max(assignments)
        mean   = sum(assignments) / n
        var    = sum((x - mean) ** 2 for x in assignments) / n
        return {
            "agents": n,
            "total_assignments": sum(assignments),
            "mean": round(mean, 2),
            "min": mn, "max": mx,
            "range": mx - mn,
            "variance": round(var, 3),
            "std_dev": round(math.sqrt(var), 3),
        }

    def export(self, assignments: list[int], dataset: str = "run") -> dict:
        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "dataset": dataset,
            },
            "overall": self._overall.to_dict(),
            "by_priority": {p.value: self._by_prio[p].to_dict() for p in Priority},
            "workload_fairness": self.fairness(assignments),
        }

    def print_summary(self, assignments: list[int], dataset: str = "run") -> dict:
        data = self.export(assignments, dataset)
        ov   = data["overall"]
        fw   = data["workload_fairness"]
        sep  = "=" * 62
        print(f"\n{sep}")
        print("  SMART DELIVERY DISPATCH  –  RESULTS")
        print(sep)
        print(f"  Orders completed   : {ov['completed']}")
        print(f"  Avg delivery time  : {ov['avg_delivery_time_min']} min")
        print(f"  SLA compliance     : {ov['sla_compliance_pct']}%")
        print(f"  SLA violations     : {ov['sla_violations']}")
        print()
        print("  By Priority:")
        for p in Priority:
            b = data["by_priority"][p.value]
            print(f"    [{p.value.upper():6s}] "
                  f"n={b['completed']:3d}  "
                  f"avg={b['avg_delivery_time_min']:5.1f}min  "
                  f"SLA✓={b['sla_compliance_pct']}%")
        if fw:
            print()
            print(f"  Workload Fairness  : "
                  f"mean={fw['mean']} std={fw['std_dev']} range={fw['range']}")
        print(sep + "\n")
        return data

    def to_json(self, assignments: list[int], dataset: str = "run") -> str:
        return json.dumps(self.export(assignments, dataset), indent=2)
