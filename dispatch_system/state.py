"""
state.py  –  PriorityOrderQueue + AgentRegistry
"""

import heapq
import logging
from datetime import datetime
from typing import Optional

from models import (
    Agent,
    Coord,
    Order,
    OrderStatus,
    SystemConfig
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Priority Order Queue
# ─────────────────────────────────────────────────────────────

class PriorityOrderQueue:

    """
    Heap ordering:

    (
        -priority_rank,
        timestamp,
        insertion_seq,
        order_id
    )

    Higher priority first,
    older orders first.
    """

    def __init__(self):

        self._heap = []

        self._orders: dict[str, Order] = {}

        self._by_status = {
            s: set()
            for s in OrderStatus
        }

        self._seq = 0

    # ─────────────────────────────────────────────────────────
    # Add order
    # ─────────────────────────────────────────────────────────

    def enqueue(
        self,
        order: Order
    ):

        if order.order_id in self._orders:
            return

        self._orders[order.order_id] = order

        self._by_status[
            order.status
        ].add(order.order_id)

        self._push(order)

    # ─────────────────────────────────────────────────────────
    # Push into heap
    # ─────────────────────────────────────────────────────────

    def _push(
        self,
        order: Order
    ):

        self._seq += 1

        heapq.heappush(
            self._heap,
            (
                -order.priority.rank(),
                order.timestamp,
                self._seq,
                order.order_id
            )
        )

    # ─────────────────────────────────────────────────────────
    # Pop next valid pending
    # ─────────────────────────────────────────────────────────

    def pop_next_pending(
        self
    ) -> Optional[Order]:

        while self._heap:

            _, _, _, oid = heapq.heappop(
                self._heap
            )

            order = self._orders.get(oid)

            if (
                order and
                order.status == OrderStatus.PENDING
            ):

                return order

        return None

    # ─────────────────────────────────────────────────────────
    # Peek next valid pending
    # ─────────────────────────────────────────────────────────

    def peek_next_pending(
        self
    ) -> Optional[Order]:

        while self._heap:

            _, _, _, oid = self._heap[0]

            order = self._orders.get(oid)

            if (
                order and
                order.status == OrderStatus.PENDING
            ):

                return order

            # Lazy cleanup
            heapq.heappop(self._heap)

        return None

    # ─────────────────────────────────────────────────────────
    # Return multiple pending orders
    # ─────────────────────────────────────────────────────────

    def pending_orders(
        self,
        limit: Optional[int] = None
    ) -> list[Order]:

        pending = sorted(
            self.by_status(
                OrderStatus.PENDING
            ),
            key=lambda o: (
                -o.priority.rank(),
                o.timestamp
            )
        )

        if limit:
            return pending[:limit]

        return pending

    # ─────────────────────────────────────────────────────────
    # Transition status
    # ─────────────────────────────────────────────────────────

    def transition(
        self,
        order_id: str,
        new_status: OrderStatus,
        ts: Optional[datetime] = None
    ) -> bool:

        valid = {

            OrderStatus.PENDING:
                OrderStatus.ASSIGNED,

            OrderStatus.ASSIGNED:
                OrderStatus.IN_TRANSIT,

            OrderStatus.IN_TRANSIT:
                OrderStatus.DELIVERED,
        }

        order = self._orders.get(order_id)

        if order is None:

            logger.error(
                f"Unknown order {order_id}"
            )

            return False

        expected = valid.get(order.status)

        if expected != new_status:

            logger.error(
                f"Bad transition "
                f"{order.order_id}: "
                f"{order.status.value} "
                f"→ {new_status.value}"
            )

            return False

        self._by_status[
            order.status
        ].discard(order_id)

        order.status = new_status

        self._by_status[
            new_status
        ].add(order_id)

        if (
            new_status ==
            OrderStatus.DELIVERED
            and ts
        ):

            order.delivered_at = ts

        return True

    # ─────────────────────────────────────────────────────────
    # Accessors
    # ─────────────────────────────────────────────────────────

    def get(
        self,
        order_id: str
    ) -> Optional[Order]:

        return self._orders.get(order_id)

    def by_status(
        self,
        status: OrderStatus
    ) -> list[Order]:

        return [
            self._orders[oid]
            for oid in self._by_status[status]
        ]

    def all_orders(
        self
    ) -> list[Order]:

        return list(
            self._orders.values()
        )


# ─────────────────────────────────────────────────────────────
# Agent Registry
# ─────────────────────────────────────────────────────────────

class AgentRegistry:

    def __init__(
        self,
        config: SystemConfig
    ):

        self.cfg = config

        self._agents: dict[
            str,
            Agent
        ] = {}

        self._available: set[str] = set()

    # ─────────────────────────────────────────────────────────
    # Register agents
    # ─────────────────────────────────────────────────────────

    def register_all(
        self,
        agents: list[Agent]
    ):

        for agent in agents:

            self._agents[
                agent.agent_id
            ] = agent

            self._refresh(agent)

    # ─────────────────────────────────────────────────────────
    # Available agents
    # ─────────────────────────────────────────────────────────

    def available_agents(
        self
    ) -> list[Agent]:

        return [
            self._agents[aid]
            for aid in self._available
        ]

    # ─────────────────────────────────────────────────────────
    # Accessors
    # ─────────────────────────────────────────────────────────

    def all_agents(
        self
    ) -> list[Agent]:

        return list(
            self._agents.values()
        )

    def get(
        self,
        agent_id: str
    ) -> Optional[Agent]:

        return self._agents.get(agent_id)

    # ─────────────────────────────────────────────────────────
    # Assign order
    # ─────────────────────────────────────────────────────────

    def assign(
        self,
        agent_id: str,
        order_id: str
    ) -> bool:

        agent = self._agents.get(
            agent_id
        )

        if agent is None:
            return False

        ok = agent.add_order(
            order_id,
            self.cfg.max_active_orders_per_agent
        )

        if ok:

            agent.cumulative_assignments += 1

            self._refresh(agent)

        return ok

    # ─────────────────────────────────────────────────────────
    # Complete order
    # ─────────────────────────────────────────────────────────

    def complete(
        self,
        agent_id: str,
        order_id: str,
        new_loc: Coord
    ):

        agent = self._agents.get(
            agent_id
        )

        if agent:

            agent.remove_order(
                order_id,
                new_loc
            )

            self._refresh(agent)

    # ─────────────────────────────────────────────────────────
    # Refresh availability
    # ─────────────────────────────────────────────────────────

    def _refresh(
        self,
        agent: Agent
    ):

        if agent.is_available(
            self.cfg.max_active_orders_per_agent
        ):

            self._available.add(
                agent.agent_id
            )

        else:

            self._available.discard(
                agent.agent_id
            )