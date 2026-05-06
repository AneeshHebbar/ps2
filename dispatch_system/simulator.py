"""
simulator.py  –  Smart event-driven dispatch simulator
"""

import heapq
import logging
from datetime import datetime, timedelta
from typing import List, Tuple

from assignment import AssignmentEngine
from metrics import MetricsCollector
from models import (
    Candidate,
    Order,
    OrderStatus,
    SystemConfig
)
from state import (
    AgentRegistry,
    PriorityOrderQueue
)

logger = logging.getLogger(__name__)


class Simulator:

    def __init__(
        self,
        engine: AssignmentEngine,
        registry: AgentRegistry,
        queue: PriorityOrderQueue,
        metrics: MetricsCollector,
        config: SystemConfig
    ):

        self.engine = engine
        self.registry = registry
        self.queue = queue
        self.metrics = metrics
        self.cfg = config

        self._orders_processed = 0

        # (
        #   delivery_time,
        #   order_id,
        #   order
        # )
        self.delivery_events: List[
            Tuple[datetime, str, Order]
        ] = []

    # ─────────────────────────────────────────────────────────
    # Apply assignment
    # ─────────────────────────────────────────────────────────

    def _apply(
        self,
        cand: Candidate,
        now: datetime
    ) -> bool:

        order = cand.order
        agent = cand.agent

        if order.status != OrderStatus.PENDING:
            return False

        if not self.registry.assign(
            agent.agent_id,
            order.order_id
        ):
            return False

        self.queue.transition(
            order.order_id,
            OrderStatus.ASSIGNED
        )

        order.assigned_agent_id = (
            agent.agent_id
        )

        order.assigned_at = now

        logger.info(
            f"  ASSIGN  {order.order_id} "
            f"[{order.priority.value:6s}] "
            f"→ {agent.agent_id}  "
            f"ETA {cand.estimated_total:.1f}min"
        )

        return True

    # ─────────────────────────────────────────────────────────
    # Schedule delivery
    # ─────────────────────────────────────────────────────────

    def _schedule_delivery(
        self,
        order: Order,
        delivery_time: datetime
    ):

        heapq.heappush(
            self.delivery_events,
            (
                delivery_time,
                order.order_id,
                order
            )
        )

    # ─────────────────────────────────────────────────────────
    # Complete delivery
    # ─────────────────────────────────────────────────────────

    def _deliver(
        self,
        order: Order,
        now: datetime
    ):

        aid = order.assigned_agent_id

        self.queue.transition(
            order.order_id,
            OrderStatus.IN_TRANSIT
        )

        self.queue.transition(
            order.order_id,
            OrderStatus.DELIVERED,
            now
        )

        self.registry.complete(
            aid,
            order.order_id,
            order.location
        )

        self.metrics.record(order)

        self._orders_processed += 1

        status = (
            "✓"
            if not order.sla_violated
            else "✗ SLA VIOLATED"
        )

        logger.info(
            f"  DELIVER {order.order_id} "
            f"at {now.strftime('%H:%M:%S')}  "
            f"{status}"
        )

    # ─────────────────────────────────────────────────────────
    # Attempt assignment
    # ─────────────────────────────────────────────────────────

    def _try_assign_order(
        self,
        order: Order,
        now: datetime
    ) -> bool:

        wait = (
            now - order.timestamp
        ).total_seconds() / 60

        # Log queue wait only once
        if (
            wait > 10 and
            not hasattr(order, "_queue_warned")
        ):

            logger.warning(
                f"  QUEUE  {order.order_id} "
                f"waiting {wait:.1f}min"
            )

            order._queue_warned = True

        cand = self.engine.decide(
            order,
            now
        )

        if not cand:
            return False

        # remove pending
        self.queue.pop_next_pending()

        if not self._apply(cand, now):
            return False

        delivery_time = (
            now +
            timedelta(
                minutes=cand.estimated_total
            )
        )

        self._schedule_delivery(
            order,
            delivery_time
        )

        return True

    # ─────────────────────────────────────────────────────────
    # Assign ALL eligible pending orders
    # ─────────────────────────────────────────────────────────

    def _assign_pending_orders(
        self,
        now: datetime
    ):

        pending = self.queue.pending_orders()

        if not pending:
            return

        for order in pending:

            # future order
            if order.timestamp > now:
                continue

            # already assigned
            if order.status != OrderStatus.PENDING:
                continue

            self._try_assign_order(
                order,
                now
            )

    # ─────────────────────────────────────────────────────────
    # Process delivery events
    # ─────────────────────────────────────────────────────────

    def _process_delivery_events(
        self,
        current_time: datetime
    ):

        while (

            self.delivery_events and

            self.delivery_events[0][0]
            <= current_time
        ):

            delivery_time, _, order = (
                heapq.heappop(
                    self.delivery_events
                )
            )

            self._deliver(
                order,
                delivery_time
            )

    # ─────────────────────────────────────────────────────────
    # Main simulation loop
    # ─────────────────────────────────────────────────────────

    def run(self):

        pending_orders = sorted(

            self.queue.by_status(
                OrderStatus.PENDING
            ),

            key=lambda o: o.timestamp
        )

        if not pending_orders:

            logger.warning(
                "No orders to process."
            )

            return

        logger.info(
            f"Starting simulation: "
            f"{len(pending_orders)} orders, "
            f"{len(self.registry.all_agents())} agents\n"
        )

        # chronological arrivals
        for order in pending_orders:

            now = order.timestamp

            # complete deliveries due
            self._process_delivery_events(
                now
            )

            # assign all possible
            self._assign_pending_orders(
                now
            )

        # process remaining deliveries
        while self.delivery_events:

            delivery_time, _, order = (
                heapq.heappop(
                    self.delivery_events
                )
            )

            self._deliver(
                order,
                delivery_time
            )

            # freed agents take more
            self._assign_pending_orders(
                delivery_time
            )

        remaining = len(

            self.queue.by_status(
                OrderStatus.PENDING
            )
        )

        if remaining > 0:

            logger.warning(
                f"{remaining} orders "
                f"remain unassigned."
            )

        logger.info(
            f"\nSimulation complete. "
            f"Processed "
            f"{self._orders_processed} orders."
        )