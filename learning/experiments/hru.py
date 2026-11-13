"""TN13 extension: greedy marginal benefit over an eight-node view lattice.

Row counts are measured from the local warehouse. Workload weights and storage
budget in group-rows are illustrative assumptions, not measured I/O or bytes.
"""

import itertools
import json

from coffee_dw.config import RESULTS_DIR
from coffee_dw.warehouse import read_detail


def select_views(costs: dict, workload: dict, budget_rows: int, base_rows: int) -> list[dict]:
    chosen, rounds = set(), []
    remaining = budget_rows

    def cost(query, extra=None):
        available = chosen | ({extra} if extra is not None else set())
        return min([base_rows] + [costs[v] for v in available if set(query).issubset(v)])

    while True:
        candidates = []
        for view, size in costs.items():
            if view in chosen or size > remaining:
                continue
            benefit = sum(weight * (cost(query) - cost(query, view)) for query, weight in workload.items())
            candidates.append((benefit / size, benefit, view))
        if not candidates:
            break
        _, benefit, view = max(candidates)
        if benefit <= 0:
            break
        chosen.add(view)
        remaining -= costs[view]
        rounds.append({"view": "".join(view) or "ALL", "group_rows": costs[view],
                       "marginal_benefit_weighted_rows": benefit, "remaining_rows": remaining})
    return rounds


def run() -> dict:
    data = read_detail()
    dimensions = {"M": "MonthStart", "R": "Market", "P": "ProductName"}
    nodes = [tuple(c) for n in range(4) for c in itertools.combinations(dimensions, n)]
    sizes = {node: int(data.groupby([dimensions[d] for d in node]).ngroups) if node else 1 for node in nodes}
    workload = {("M", "R"): 10, ("M", "P"): 4, ("R", "P"): 3, ("M",): 4, ("R",): 2, (): 1}
    return {"base_fact_rows": len(data), "storage_budget_group_rows": 300,
            "cost_model": "Minimum ancestor view row count; no physical bytes or timings estimated",
            "workload_assumed": {"".join(k) or "ALL": v for k, v in workload.items()},
            "view_group_rows": {"".join(k) or "ALL": v for k, v in sizes.items()},
            "rounds": select_views(sizes, workload, 300, len(data)),
            "next_step": "Create chosen indexed views and measure workload/maintenance on SQL Server"}


if __name__ == "__main__":
    result = run()
    path = RESULTS_DIR / "TN13" / "hru.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
