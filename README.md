# Smart Delivery Dispatch System

## Team Information
- **Team Name**: ByteForge
- **Year**: 2nd year
- **All-Female Team**: No

## Architecture Overview

The Smart Delivery Dispatch System is a backend system that assigns delivery orders to agents in real time while managing priority, SLA deadlines, and agent workload.

### Dispatch Strategy

The system assigns orders using a scoring-based approach.

Each agent is scored based on:
- Distance to delivery location
- Remaining SLA time
- Order priority
- Current workload
- Agent availability

The agent with the best score gets assigned to the order.

To avoid long waiting times, older pending orders receive higher priority over time.

---

### SLA and Capacity Handling

- Every agent has a maximum delivery capacity.
- High-priority and near-deadline orders are processed first.
- Orders are managed using a priority queue for faster scheduling.

---

### System Flow

1. Load agents, orders, and road network data
2. Build graph for route calculation
3. Calculate shortest paths using Floyd-Warshall Algorithm
4. Start simulation
5. Score agents and assign deliveries
6. Track delivery performance and SLA status
7. Generate final report

---

### Core Modules

- `loaders.py` → Loads and validates data
- `graph.py` → Route and distance calculations
- `assignment.py` → Agent scoring and assignment
- `state.py` → Stores active system state
- `simulator.py` → Runs event-driven simulation
- `metrics.py` → Calculates performance metrics

---

### Technologies Used

- Python 3.10+
- Pandas
- Heapq
- JSON

---

### Key Features

- Real-time order assignment
- SLA-aware dispatching
- Workload balancing
- Priority-based scheduling
- Route optimization
- Event-driven simulation

---

### Output Metrics

The system tracks:
- SLA success rate
- Average delivery time
- Agent utilization
- Pending and failed orders

Reports are generated in JSON format for evaluation.
