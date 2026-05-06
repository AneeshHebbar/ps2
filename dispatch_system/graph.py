"""
graph.py  –  Coordinate-based graph with Floyd-Warshall shortest paths.
             Edge weight = distance_minutes * delay_multiplier.
"""
import heapq
import logging
import math
from typing import Optional

from models import Coord

logger = logging.getLogger(__name__)
INF = math.inf
FW_THRESHOLD = 300   # use Floyd-Warshall for graphs with ≤300 nodes


class Graph:
    def __init__(self):
        self._adj: dict[Coord, dict[Coord, float]] = {}
        self._dist: Optional[dict[Coord, dict[Coord, float]]] = None

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self, edges: list[tuple[Coord, Coord, float, float]]):
        """
        edges: (from_coord, to_coord, distance_minutes, delay_multiplier)
        Stored weight = distance * multiplier.
        Graph is directed; the CSV already provides both directions.
        We also add the reverse direction automatically to ensure
        full connectivity (cost = same effective weight).
        """
        self._adj.clear()
        self._dist = None

        for src, dst, dist, mult in edges:
            weight = dist * mult
            self._adj.setdefault(src, {})[dst] = weight
            # Ensure destination node exists
            self._adj.setdefault(dst, {})
            # Add reverse if not already present
            if src not in self._adj[dst]:
                self._adj[dst][src] = weight

        n = len(self._adj)
        if n == 0:
            logger.warning("Graph: no nodes loaded.")
            return

        if n <= FW_THRESHOLD:
            self._floyd_warshall()
            logger.info(f"Graph: {n} nodes, {len(edges)} edges – Floyd-Warshall precomputed.")
        else:
            logger.info(f"Graph: {n} nodes, {len(edges)} edges – Dijkstra on-demand.")

    def locations(self) -> set[Coord]:
        return set(self._adj.keys())

    # ── Query ──────────────────────────────────────────────────────────────────

    def travel_time(self, src: Coord, dst: Coord) -> Optional[float]:
        """Return shortest travel time (minutes) or None if unreachable."""
        if src == dst:
            return 0.0
        if self._dist is not None:
            d = self._dist.get(src, {}).get(dst, INF)
            return None if d >= INF else d
        return self._dijkstra(src, dst)

    # ── Floyd-Warshall ─────────────────────────────────────────────────────────

    def _floyd_warshall(self):
        nodes = list(self._adj.keys())
        idx = {n: i for i, n in enumerate(nodes)}
        sz = len(nodes)

        d = [[INF] * sz for _ in range(sz)]
        for i in range(sz):
            d[i][i] = 0.0
        for src, nbrs in self._adj.items():
            for dst, w in nbrs.items():
                d[idx[src]][idx[dst]] = w

        for k in range(sz):
            dk = d[k]
            for i in range(sz):
                if d[i][k] >= INF:
                    continue
                di = d[i]
                for j in range(sz):
                    nd = di[k] + dk[j]
                    if nd < di[j]:
                        di[j] = nd

        self._dist = {
            nodes[i]: {nodes[j]: d[i][j] for j in range(sz)}
            for i in range(sz)
        }

    # ── Dijkstra ───────────────────────────────────────────────────────────────

    def _dijkstra(self, src: Coord, target: Coord) -> Optional[float]:
        dist: dict[Coord, float] = {src: 0.0}
        heap = [(0.0, id(src), src)]
        while heap:
            d, _, u = heapq.heappop(heap)
            if u == target:
                return d
            if d > dist.get(u, INF):
                continue
            for v, w in self._adj.get(u, {}).items():
                nd = d + w
                if nd < dist.get(v, INF):
                    dist[v] = nd
                    heapq.heappush(heap, (nd, id(v), v))
        return None
