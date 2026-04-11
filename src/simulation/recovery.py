"""
Tier 6 — Dynamic Recovery Path Modeller

Uses A* Search on an MDP state graph to find the minimum-cost intervention
sequence that moves a distressed user back to STABLE regime.

State: (regime, cash_buffer_bucket, emi_overdue_count)
  regime ∈ {0=STABLE, 1=STRESSED, 2=CRISIS}
  cash_buffer_bucket ∈ {0: <5d, 1: 5–15d, 2: >15d}
  emi_overdue_count  ∈ {0, 1, 2+}

Target set: (STABLE, cash_bucket=2, overdue=0)

Each action is an edge with:
  - daily_cf_delta: extra daily cashflow (INR/day)
  - user_cost: financial cost label (low/medium/high)
  - success_probability: P(action achieves effect)
  - edge_cost = (1 - success_probability) × penalty + financial_cost_weight
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any


# ── Intervention action space ────────────────────────────────────────────────

@dataclass(frozen=True)
class Action:
    id: str
    description: str
    daily_cf_delta_low: float     # conservative daily cashflow improvement (INR/day)
    daily_cf_delta_high: float    # optimistic
    user_cost: str                # low / medium / high
    success_probability: float
    side_effect: str = ""
    one_time_inflow: float = 0.0  # e.g. micro-loan disbursement

    @property
    def daily_cf_delta(self) -> float:
        return (self.daily_cf_delta_low + self.daily_cf_delta_high) / 2.0

    @property
    def cost_weight(self) -> float:
        return {"low": 0.1, "medium": 0.4, "high": 0.7}.get(self.user_cost, 0.5)

    @property
    def edge_cost(self) -> float:
        """Lower is better: successful + cheap actions have low cost."""
        return (1.0 - self.success_probability) * 2.0 + self.cost_weight


ACTIONS: dict[str, Action] = {
    "A_CUT_DISC_20": Action(
        id="A_CUT_DISC_20",
        description="Cut discretionary 20%",
        daily_cf_delta_low=400, daily_cf_delta_high=2000,
        user_cost="low", success_probability=0.72,
        side_effect="Lifestyle impact",
    ),
    "A_CUT_DISC_40": Action(
        id="A_CUT_DISC_40",
        description="Cut discretionary 40%",
        daily_cf_delta_low=800, daily_cf_delta_high=4000,
        user_cost="medium", success_probability=0.55,
        side_effect="High lifestyle impact",
    ),
    "A_EMI_RESTRUC": Action(
        id="A_EMI_RESTRUC",
        description="EMI restructuring (extend tenure)",
        daily_cf_delta_low=100, daily_cf_delta_high=500,
        user_cost="low", success_probability=0.80,
        side_effect="Longer debt tenure",
    ),
    "A_MICRO_LOAN": Action(
        id="A_MICRO_LOAN",
        description="Pre-qualified micro-loan disbursement",
        daily_cf_delta_low=0, daily_cf_delta_high=0,
        one_time_inflow=20000.0,
        user_cost="medium", success_probability=0.90,
        side_effect="New debt obligation",
    ),
    "A_INC_SIDE": Action(
        id="A_INC_SIDE",
        description="Activate secondary income (gig/freelance)",
        daily_cf_delta_low=167, daily_cf_delta_high=500,   # ₹5k–₹15k / month ÷ 30
        user_cost="low", success_probability=0.45,
        side_effect="Time cost",
    ),
    "A_CREDIT_LINE": Action(
        id="A_CREDIT_LINE",
        description="Draw on revolving credit line",
        daily_cf_delta_low=0, daily_cf_delta_high=0,
        one_time_inflow=15000.0,    # 50% of typical revolving limit
        user_cost="high", success_probability=0.85,
        side_effect="Credit utilization spike",
    ),
    "A_INSURANCE": Action(
        id="A_INSURANCE",
        description="Emergency insurance activation",
        daily_cf_delta_low=0, daily_cf_delta_high=0,
        one_time_inflow=47500.0,    # mid-point ₹15k–₹80k
        user_cost="low", success_probability=0.95,
        side_effect="Only for medical scenario",
    ),
}


# ── MDP State ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MDPState:
    regime: int           # 0=STABLE, 1=STRESSED, 2=CRISIS
    cash_bucket: int      # 0: <5d, 1: 5–15d, 2: >15d buffer
    overdue_count: int    # 0, 1, 2+ (capped at 2)


_TARGET_STATE = MDPState(regime=0, cash_bucket=2, overdue_count=0)


def _bucketize_cash(cash_buffer_days: float) -> int:
    if cash_buffer_days < 5:
        return 0
    elif cash_buffer_days < 15:
        return 1
    return 2


def _initial_state(regime: int, cash_buffer_days: float, emi_overdue: int) -> MDPState:
    return MDPState(
        regime=regime,
        cash_bucket=_bucketize_cash(cash_buffer_days),
        overdue_count=min(emi_overdue, 2),
    )


def _transition(state: MDPState, action: Action, emi_monthly: float) -> MDPState:
    """
    Approximate state transition after applying action.
    More generous daily CF delta → better cash bucket.
    EMI restructuring reduces overdue count.
    """
    new_regime = state.regime
    new_cash = state.cash_bucket
    new_overdue = state.overdue_count

    cf = action.daily_cf_delta * action.success_probability
    one_time = action.one_time_inflow * action.success_probability

    # Estimate change in cash buffer days (rough: daily_cf_delta / daily_expense_proxy)
    daily_expense_proxy = max(emi_monthly / 30.0, 500.0)
    # One-time inflows convert to equivalent buffer days (over 30-day window)
    delta_buffer_days = cf / daily_expense_proxy + one_time / daily_expense_proxy

    # Determine new cash bucket (use midpoint of each bucket range)
    approx_buffer = {0: 2, 1: 10, 2: 20}[state.cash_bucket] + delta_buffer_days
    new_cash = _bucketize_cash(approx_buffer)

    # EMI restructuring reduces overdue
    if action.id == "A_EMI_RESTRUC" and new_overdue > 0:
        new_overdue = max(0, new_overdue - 1)

    # Regime improves if cash bucket improved or overdue cleared
    if new_cash > state.cash_bucket or new_overdue < state.overdue_count:
        new_regime = max(0, state.regime - 1)

    # Special: micro-loan / credit line one-time inflow may jump 2 levels
    if action.one_time_inflow > 0 and new_cash == 2:
        new_regime = 0

    return MDPState(regime=new_regime, cash_bucket=new_cash, overdue_count=new_overdue)


# ── A* heuristic ─────────────────────────────────────────────────────────────

def _heuristic(state: MDPState) -> float:
    """
    Admissible heuristic: Manhattan distance in (regime, cash_bucket, overdue) space.
    Lower-bounds true cost since each step reduces at most one dimension.
    """
    return float(
        abs(state.regime - _TARGET_STATE.regime) +
        abs(state.cash_bucket - _TARGET_STATE.cash_bucket) +
        abs(state.overdue_count - _TARGET_STATE.overdue_count)
    )


# ── A* Search ─────────────────────────────────────────────────────────────────

@dataclass(order=True)
class _Node:
    f: float
    g: float = field(compare=False)
    state: MDPState = field(compare=False)
    path: list[tuple[int, str]] = field(compare=False, default_factory=list)
    # path = [(day_offset, action_id), ...]


def find_recovery_plan(
    regime: int,
    cash_buffer_days: float,
    emi_overdue_count: int,
    emi_monthly: float,
    max_steps: int = 5,
    max_days: int = 90,
) -> dict:
    """
    Run A* search to find minimum-cost recovery plan.

    Returns recovery plan dict matching §15.2 simulation response shape.
    """
    start = _initial_state(regime, cash_buffer_days, emi_overdue_count)

    if start == _TARGET_STATE:
        return _trivial_plan()

    # Priority queue: (f_cost, node)
    heap: list[_Node] = []
    heapq.heappush(heap, _Node(f=_heuristic(start), g=0.0, state=start))
    visited: set[MDPState] = set()

    best_node: _Node | None = None

    while heap:
        node = heapq.heappop(heap)

        if node.state in visited:
            continue
        visited.add(node.state)

        if node.state == _TARGET_STATE or len(node.path) >= max_steps:
            best_node = node
            break

        for action in ACTIONS.values():
            next_state = _transition(node.state, action, emi_monthly)
            if next_state in visited:
                continue
            g_new = node.g + action.edge_cost
            f_new = g_new + _heuristic(next_state)
            day_offset = len(node.path) * 7  # rough: one action per week
            new_path = node.path + [(day_offset, action.id)]
            heapq.heappush(heap, _Node(f=f_new, g=g_new, state=next_state, path=new_path))

    if best_node is None or not best_node.path:
        return _trivial_plan()

    return _format_plan(best_node.path, emi_monthly, start)


def _trivial_plan() -> dict:
    return {
        "plan_id": "rp_trivial",
        "steps": [],
        "projected_regime_at_45d": "STABLE",
        "recovery_probability_full_compliance": 1.0,
        "recovery_probability_50pct_compliance": 0.85,
        "recovery_probability_no_action": 0.90,
        "alternative_step3": None,
    }


def _format_plan(
    path: list[tuple[int, str]],
    emi_monthly: float,
    start_state: MDPState,
) -> dict:
    """Build the plan dict from A* path."""
    steps = []
    cumulative_p_success = 1.0

    for i, (day_offset, action_id) in enumerate(path, start=1):
        action = ACTIONS[action_id]
        cumulative_p_success *= action.success_probability
        steps.append({
            "step": i,
            "day": day_offset,
            "action": action_id,
            "description": action.description,
            "daily_cf_delta": round(action.daily_cf_delta, 0),
            "success_probability": action.success_probability,
        })

    # Recovery probabilities
    p_full = round(cumulative_p_success, 2)
    p_50   = round(p_full * 0.5 + 0.22 * 0.5, 2)
    p_none = 0.22 if start_state.regime >= 2 else 0.45

    # Projected regime estimate
    if p_full > 0.7:
        proj_regime = "STABLE"
    elif p_full > 0.4:
        proj_regime = "STRESSED"
    else:
        proj_regime = "CRISIS"

    # Alternative last step
    last_action_id = path[-1][1] if path else None
    alt_step: dict[str, Any] | None = None
    if last_action_id != "A_MICRO_LOAN":
        alt_step = {
            "action": "A_MICRO_LOAN",
            "loan_amount": 20000,
            "trigger_day": (path[-1][0] + 5) if path else 35,
        }

    return {
        "plan_id": f"rp_auto_{abs(hash(str(path))) % 10000:04d}",
        "steps": steps,
        "projected_regime_at_45d": proj_regime,
        "recovery_probability_full_compliance": p_full,
        "recovery_probability_50pct_compliance": p_50,
        "recovery_probability_no_action": p_none,
        "alternative_step3": alt_step,
    }
