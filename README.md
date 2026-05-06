# Smart Delivery Dispatch System

## Team Information
- **Team Name**: ByteForge
- **Year**: 2nd Year
- **All-Female Team**: No

---

# Architecture Overview

The Smart Delivery Dispatch System is a modular backend platform designed for intelligent real time delivery assignment and optimization. The architecture follows an event driven workflow where orders, agents, and routing information are continuously processed to support efficient dispatch decisions. Orders are maintained in a priority queue and assigned through a weighted scoring algorithm based on travel distance, SLA urgency, workload balance, order priority, agent availability, and delivery ratings.

The platform uses Floyd Warshall shortest path computation to estimate travel times between locations efficiently. Pending orders remain queued until agents become available, ensuring continuous scheduling without blocking execution. State transitions are centrally managed to maintain consistency between order status and agent workload during assignment and delivery completion.

The architecture is divided into specialized modules for data loading, graph routing, assignment logic, state management, simulation handling, and performance analytics. The system supports SLA aware scheduling, workload fairness, batch delivery optimization, GPS aware tracking, and real time monitoring. Final operational metrics and delivery statistics are exported in structured JSON format for reporting, evaluation, and performance analysis purposes efficiently.

---

# Core Modules

| Module | Purpose |
|---|---|
| `loaders.py` | Load and validate CSV data |
| `graph.py` | Route and shortest-path calculations |
| `assignment.py` | Assignment scoring and dispatch |
| `state.py` | Manage order and agent states |
| `simulator.py` | Event-driven simulation engine |
| `metrics.py` | SLA and performance analytics |

---

# Technologies Used

- Python 3.10+
- Pandas
- Heapq
- JSON

---

# Key Features

- Real-time dispatching
- SLA-aware scheduling
- Workload balancing
- Priority-based assignment
- Route optimization
- Batch delivery support
- GPS-aware tracking
- JSON performance reports

---

# Output Metrics

The system tracks:
- SLA compliance rate
- Average delivery time
- Agent utilization
- Pending and failed orders
- Workload fairness statistics

Reports are exported in JSON format.
