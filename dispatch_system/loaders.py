"""
loaders.py  –  Load & validate all four CSV files
"""
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import Agent, Coord, Order, Priority, SystemConfig

logger = logging.getLogger(__name__)

_DT_FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _open_csv(path: str, required: set[str]) -> Optional[csv.DictReader]:
    p = Path(path)
    if not p.exists():
        logger.error(f"File not found: {path}")
        return None
    f = open(p, newline="", encoding="utf-8")
    reader = csv.DictReader(f)
    if reader.fieldnames is None:
        logger.error(f"Empty or header-less CSV: {path}")
        return None
    missing = required - set(reader.fieldnames)
    if missing:
        logger.error(f"{path}: missing columns {missing}")
        return None
    return reader


def _int(val: str, field: str, rid: str, row: int) -> Optional[int]:
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        logger.warning(f"Row {row} ({rid}): bad int for {field}='{val}', skipping")
        return None


def _float_nn(val: str, field: str, rid: str, row: int) -> Optional[float]:
    """Parse non-negative float."""
    try:
        v = float(val.strip())
        if v < 0:
            raise ValueError
        return v
    except (ValueError, AttributeError):
        logger.warning(f"Row {row} ({rid}): bad value for {field}='{val}', skipping")
        return None


def _dt(val: str, field: str, rid: str, row: int) -> Optional[datetime]:
    for fmt in _DT_FMTS:
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError:
            pass
    logger.warning(f"Row {row} ({rid}): cannot parse datetime {field}='{val}', skipping")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Agents  –  agent_id, current_x, current_y, rating
# ─────────────────────────────────────────────────────────────────────────────

def load_agents(path: str) -> list[Agent]:
    reader = _open_csv(path, {"agent_id", "current_x", "current_y", "rating"})
    if reader is None:
        return []
    agents: list[Agent] = []
    for rn, row in enumerate(reader, 2):
        aid = row.get("agent_id", "").strip()
        if not aid:
            logger.warning(f"Row {rn}: empty agent_id, skipping")
            continue
        x = _int(row.get("current_x", ""), "current_x", aid, rn)
        y = _int(row.get("current_y", ""), "current_y", aid, rn)
        r = _float_nn(row.get("rating", ""), "rating", aid, rn)
        if x is None or y is None or r is None:
            continue
        if not (0.0 <= r <= 5.0):
            logger.warning(f"Row {rn} ({aid}): rating {r} out of [0,5], skipping")
            continue
        agents.append(Agent(agent_id=aid, current_location=Coord(x, y), rating=r))
    logger.info(f"Loaded {len(agents)} agents from '{path}'")
    return agents


# ─────────────────────────────────────────────────────────────────────────────
# Orders  –  order_id, timestamp, location_x, location_y,
#             prep_time_minutes, priority, sla_minutes
# ─────────────────────────────────────────────────────────────────────────────

def load_orders(path: str) -> list[Order]:
    required = {"order_id", "timestamp", "location_x", "location_y",
                "prep_time_minutes", "priority", "sla_minutes"}
    reader = _open_csv(path, required)
    if reader is None:
        return []
    orders: list[Order] = []
    valid_prios = {p.value for p in Priority}
    for rn, row in enumerate(reader, 2):
        oid = row.get("order_id", "").strip()
        if not oid:
            logger.warning(f"Row {rn}: empty order_id, skipping")
            continue
        ts  = _dt(row.get("timestamp", ""), "timestamp", oid, rn)
        lx  = _int(row.get("location_x", ""), "location_x", oid, rn)
        ly  = _int(row.get("location_y", ""), "location_y", oid, rn)
        pt  = _float_nn(row.get("prep_time_minutes", ""), "prep_time_minutes", oid, rn)
        slm = _float_nn(row.get("sla_minutes", ""), "sla_minutes", oid, rn)
        prio_str = row.get("priority", "").strip().lower()
        if any(v is None for v in [ts, lx, ly, pt, slm]):
            continue
        if prio_str not in valid_prios:
            logger.warning(f"Row {rn} ({oid}): invalid priority '{prio_str}', skipping")
            continue
        orders.append(Order(
            order_id=oid, timestamp=ts,
            location=Coord(lx, ly),
            prep_time=pt, priority=Priority(prio_str),
            sla_minutes=slm,
        ))
    logger.info(f"Loaded {len(orders)} orders from '{path}'")
    return orders


# ─────────────────────────────────────────────────────────────────────────────
# Edges  –  from_x, from_y, to_x, to_y, distance_minutes, delay_multiplier
# ─────────────────────────────────────────────────────────────────────────────

def load_edges(path: str) -> list[tuple[Coord, Coord, float, float]]:
    """Returns list of (from_coord, to_coord, distance_minutes, delay_multiplier)."""
    required = {"from_x", "from_y", "to_x", "to_y", "distance_minutes", "delay_multiplier"}
    reader = _open_csv(path, required)
    if reader is None:
        return []
    edges = []
    for rn, row in enumerate(reader, 2):
        fx = _int(row.get("from_x", ""), "from_x", f"row{rn}", rn)
        fy = _int(row.get("from_y", ""), "from_y", f"row{rn}", rn)
        tx = _int(row.get("to_x", ""), "to_x", f"row{rn}", rn)
        ty = _int(row.get("to_y", ""), "to_y", f"row{rn}", rn)
        dm = _float_nn(row.get("distance_minutes", ""), "distance_minutes", f"row{rn}", rn)
        ml = _float_nn(row.get("delay_multiplier", ""), "delay_multiplier", f"row{rn}", rn)
        if any(v is None for v in [fx, fy, tx, ty, dm, ml]):
            continue
        edges.append((Coord(fx, fy), Coord(tx, ty), dm, ml))
    logger.info(f"Loaded {len(edges)} edges from '{path}'")
    return edges


# ─────────────────────────────────────────────────────────────────────────────
# Constraints  –  constraint, value
# ─────────────────────────────────────────────────────────────────────────────

def load_constraints(path: str) -> SystemConfig:
    cfg = SystemConfig()
    reader = _open_csv(path, {"constraint", "value"})
    if reader is None:
        logger.warning("Using default config.")
        return cfg
    type_map = {k: type(v) for k, v in cfg.__dict__.items()}
    for row in reader:
        key = row.get("constraint", "").strip()
        val = row.get("value", "").strip()
        if not key or not val:
            continue
        if hasattr(cfg, key):
            try:
                setattr(cfg, key, type_map[key](val))
            except (ValueError, TypeError) as e:
                logger.warning(f"Config '{key}': bad value '{val}': {e}")
        else:
            logger.debug(f"Unknown constraint key '{key}', ignored")
    logger.info("Config loaded.")
    return cfg
