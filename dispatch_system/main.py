"""
main.py  –  Smart Delivery Dispatch System
Usage:
    python main.py
    python main.py --agents data/agents.csv --orders data/orders.csv \
                   --edges data/environmental_edges.csv \
                   --constraints data/constraints.csv \
                   --output results.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from assignment import AssignmentEngine
from graph import Graph
from loaders import load_agents, load_constraints, load_edges, load_orders
from metrics import MetricsCollector
from models import OrderStatus
from simulator import Simulator
from state import AgentRegistry, PriorityOrderQueue

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def parse_args():
    p = argparse.ArgumentParser(description="Smart Delivery Dispatch System")
    p.add_argument("--agents",      default="data/agents.csv")
    p.add_argument("--orders",      default="data/orders.csv")
    p.add_argument("--edges",       default="data/environmental_edges.csv")
    p.add_argument("--constraints", default="data/constraints.csv")
    p.add_argument("--output",      default="results.json")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("\n" + "=" * 62)
    print("   SMART DELIVERY DISPATCH SYSTEM  –  starting")
    print("=" * 62 + "\n")

    # 1. Config
    config = load_constraints(args.constraints)
    logger.info(f"Config: max_active={config.max_active_orders_per_agent}  "
                f"latency_target={config.decision_latency_target_seconds}s  "
                f"default_sla={config.default_sla_minutes}min")

    # 2. Graph
    edges = load_edges(args.edges)
    if not edges:
        logger.error("No edges loaded – cannot compute travel times. Exiting.")
        sys.exit(1)
    graph = Graph()
    graph.build(edges)

    # 3. Agents
    agents = load_agents(args.agents)
    if not agents:
        logger.error("No agents loaded. Exiting.")
        sys.exit(1)
    registry = AgentRegistry(config)
    registry.register_all(agents)

    # 4. Orders
    orders = load_orders(args.orders)
    if not orders:
        logger.error("No orders loaded. Exiting.")
        sys.exit(1)
    queue = PriorityOrderQueue()
    for o in orders:
        queue.enqueue(o)

    # 5. Run
    metrics = MetricsCollector()
    engine  = AssignmentEngine(graph, registry, queue, config)
    sim     = Simulator(engine, registry, queue, metrics, config)
    sim.run()

    # 6. Results
    assignments = [a.cumulative_assignments for a in registry.all_agents()]
    report = metrics.print_summary(assignments, dataset=Path(args.orders).stem)

    # Unresolved orders
    still_pending    = [o.order_id for o in queue.by_status(OrderStatus.PENDING)]
    still_assigned   = [o.order_id for o in queue.by_status(OrderStatus.ASSIGNED)]
    still_in_transit = [o.order_id for o in queue.by_status(OrderStatus.IN_TRANSIT)]
    report["unresolved"] = {
        "pending":    still_pending,
        "assigned":   still_assigned,
        "in_transit": still_in_transit,
    }
    if still_pending:
        logger.warning(f"{len(still_pending)} orders still PENDING: {still_pending}")

    # Write JSON
    out = Path(args.output)
    out.write_text(json.dumps(report, indent=2))
    logger.info(f"Results written to {out}")
    print(f"Done. Open '{out}' for the full JSON report.\n")


if __name__ == "__main__":
    main()
