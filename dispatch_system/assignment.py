"""
assignment.py  –  Smart multi-objective dispatch engine
"""

import logging
import time
from datetime import datetime
from typing import Optional

from graph import Graph
from models import Candidate, Order, SystemConfig
from state import AgentRegistry, PriorityOrderQueue

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Normalization Helpers
# ─────────────────────────────────────────────────────────────

def _norm(v: float, lo: float, hi: float) -> float:
    return 1.0 if hi == lo else (v - lo) / (hi - lo)


def _norm_inv(v: float, lo: float, hi: float) -> float:
    return 1.0 - _norm(v, lo, hi)


# ─────────────────────────────────────────────────────────────
# Assignment Engine
# ─────────────────────────────────────────────────────────────

class AssignmentEngine:

    def __init__(
        self,
        graph: Graph,
        registry: AgentRegistry,
        queue: PriorityOrderQueue,
        config: SystemConfig
    ):
        self.graph = graph
        self.registry = registry
        self.queue = queue
        self.cfg = config

    # ─────────────────────────────────────────────────────────
    # Candidate Generation
    # ─────────────────────────────────────────────────────────

    def candidates(
        self,
        order: Order
    ) -> list[Candidate]:

        t0 = time.perf_counter()

        result: list[Candidate] = []

        available = self.registry.available_agents()

        for agent in available:

            travel_time = self.graph.travel_time(
                agent.current_location,
                order.location
            )

            if travel_time is None:
                continue

            # batching penalty
            active_penalty = (
                len(agent.active_orders) * 4
            )

            estimated_total = (
                travel_time +
                order.prep_time +
                active_penalty
            )

            result.append(
                Candidate(
                    agent=agent,
                    order=order,
                    travel_time=travel_time,
                    estimated_total=estimated_total,
                )
            )

        ms = (time.perf_counter() - t0) * 1000

        if ms > 100:
            logger.warning(
                f"Candidate generation took "
                f"{ms:.1f}ms"
            )

        return result

    # ─────────────────────────────────────────────────────────
    # Smart Multi-Objective Scoring
    # ─────────────────────────────────────────────────────────

    def score(
        self,
        cands: list[Candidate],
        now: datetime
    ) -> list[Candidate]:

        if not cands:
            return []

        times = [c.estimated_total for c in cands]
        assigns = [
            c.agent.cumulative_assignments
            for c in cands
        ]
        ratings = [c.agent.rating for c in cands]

        mn_t, mx_t = min(times), max(times)
        mn_a, mx_a = min(assigns), max(assigns)
        mn_r, mx_r = min(ratings), max(ratings)

        cfg = self.cfg

        for c in cands:

            # ─────────────────────────────────────
            # Queue aging
            # ─────────────────────────────────────

            queue_minutes = (
                now - c.order.timestamp
            ).total_seconds() / 60

            aging_bonus = min(
                1.5,
                queue_minutes * 0.015
            )

            # ─────────────────────────────────────
            # SLA urgency
            # ─────────────────────────────────────

            remaining_sla = (
                c.order.sla_deadline - now
            ).total_seconds() / 60

            if remaining_sla <= 0:

                # Log only once
                if not hasattr(
                    c.order,
                    "_sla_logged"
                ):

                    logger.warning(
                        f"Order {c.order.order_id} "
                        f"SLA already expired."
                    )

                    c.order._sla_logged = True

                sla_bonus = 2.0

            else:

                sla_bonus = max(
                    0.0,
                    1.0 - (
                        remaining_sla / 60
                    )
                )

            # ─────────────────────────────────────
            # Delivery speed
            # ─────────────────────────────────────

            s_time = _norm_inv(
                c.estimated_total,
                mn_t,
                mx_t
            )

            # ─────────────────────────────────────
            # Fairness
            # ─────────────────────────────────────

            s_fair = _norm_inv(
                c.agent.cumulative_assignments,
                mn_a,
                mx_a
            )

            # ─────────────────────────────────────
            # Priority
            # ─────────────────────────────────────

            max_pw = max(
                cfg.priority_weight_high,
                cfg.priority_weight_normal,
                cfg.priority_weight_low
            )

            s_prio = (
                c.order.priority.weight(cfg)
                / max_pw
            )

            # ─────────────────────────────────────
            # Agent rating
            # ─────────────────────────────────────

            s_rate = _norm(
                c.agent.rating,
                mn_r,
                mx_r
            )

            # ─────────────────────────────────────
            # Workload penalty
            # ─────────────────────────────────────

            workload_penalty = (
                len(c.agent.active_orders) * 0.15
            )

            # ─────────────────────────────────────
            # Final score
            # ─────────────────────────────────────

            c.score = (

                # Priority importance
                (s_prio * 2.5)

                # Faster deliveries
                + (s_time * 2.0)

                # SLA urgency
                + (sla_bonus * 2.2)

                # Queue aging
                + aging_bonus

                # Agent quality
                + (s_rate * 0.5)

                # Fairness
                + (s_fair * 0.8)

                # Penalize overloaded agents
                - workload_penalty
            )

        # Highest score wins
        cands.sort(
            key=lambda c: (
                -c.score,
                c.estimated_total,
                c.agent.agent_id
            )
        )

        return cands

    # ─────────────────────────────────────────────────────────
    # Decision
    # ─────────────────────────────────────────────────────────

    def decide(
        self,
        order: Order,
        now: datetime
    ) -> Optional[Candidate]:

        t0 = time.perf_counter()

        cands = self.candidates(order)

        if not cands:

            # Prevent repeated spam logging
            if not hasattr(order, "_queued_logged"):

                logger.info(
                    f"Order {order.order_id}: "
                    f"no available agents → queued."
                )

                order._queued_logged = True

            return None

        ranked = self.score(
            cands,
            now
        )

        best = ranked[0]

        ms = (
            time.perf_counter() - t0
        ) * 1000

        target_ms = (
            self.cfg
            .decision_latency_target_seconds
            * 1000
        )

        if ms > target_ms:

            logger.warning(
                f"Decision latency "
                f"{ms:.1f}ms > "
                f"target {target_ms:.0f}ms"
            )

        return best