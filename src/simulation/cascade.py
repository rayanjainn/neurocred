"""
Tier 6 — EMI Cascade & Contagion Model

Four-stage cascade triggered when cash < EMI_due on a due date:

  Stage 1 — Missed EMI: penalty interest applied, debit_failure++
  Stage 2 — Credit Limit Reduction (P = 0.55 × cascade_susceptibility)
  Stage 3 — Second EMI Miss (P = 0.40 × cascade_susceptibility if Stage 2 hit)
  Stage 4 — Lender Default Filing (P = 0.25 × cascade_susceptibility if Stage 3 hit)

Systemic stress flag: if >20% of paths reach Stage 2, all Stage 2 escalation
probabilities increase by +0.15.

cascade_susceptibility per persona:
  genuine_healthy:    0.10
  genuine_struggling: 0.72
  shell_circular:     0.91
  paper_trader:       0.68
  new_to_credit:      0.45
  unknown:            0.45
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field

PERSONA_CASCADE_SUSCEPTIBILITY: dict[str, float] = {
    "genuine_healthy":    0.10,
    "genuine_struggling": 0.72,
    "shell_circular":     0.91,
    "paper_trader":       0.68,
    "new_to_credit":      0.45,
    "unknown":            0.45,
}

BASE_RATE = 0.12          # 12% p.a.
PENALTY_RATE_STAGE1 = BASE_RATE + 0.02   # +2% p.a.
PENALTY_RATE_STAGE3 = BASE_RATE + 0.04   # +4% p.a.
OVERDRAFT_REDUCTION_STAGE2 = 0.30        # credit limit cut 30%
_SYSTEMIC_THRESHOLD = 0.20              # 20% paths in Stage 2 → systemic flag
_SYSTEMIC_BONUS = 0.15                  # additional escalation probability


@dataclass
class CascadeState:
    """Per-path mutable cascade state."""
    stage: int = 0                    # current cascade stage (0 = no cascade)
    days_in_cascade: int = 0          # days since first miss
    overdue_principal: float = 0.0    # principal in arrears
    penalty_rate: float = 0.0         # current effective penalty rate
    missed_emis: int = 0              # total missed EMIs on this path
    credit_limit_cut: bool = False    # Stage 2 triggered
    hard_default: bool = False        # Stage 4 triggered
    default_day: int = -1             # day of hard default (-1 if none)


def get_cascade_susceptibility(persona: str) -> float:
    return PERSONA_CASCADE_SUSCEPTIBILITY.get(persona, 0.45)


def daily_penalty_cashflow(state: CascadeState, emi_base: float) -> float:
    """
    Return daily penalty cash drain due to active cascade.
    Stage 1+: compound overdue interest accrues daily.
    """
    if state.stage == 0 or state.overdue_principal <= 0:
        return 0.0
    return state.overdue_principal * (state.penalty_rate / 365.0)


def try_escalate(
    state: CascadeState,
    cascade_susceptibility: float,
    rng: np.random.Generator,
    systemic_bonus: float = 0.0,
) -> None:
    """
    Attempt cascade escalation at the appropriate stage day thresholds.
    Modifies state in-place.
    """
    if state.stage == 1 and state.days_in_cascade >= 7:
        # Stage 2 attempt
        p2 = min(0.55 * cascade_susceptibility + systemic_bonus, 1.0)
        if rng.random() < p2:
            state.stage = 2
            state.credit_limit_cut = True
            state.penalty_rate = PENALTY_RATE_STAGE1

    if state.stage == 2 and state.days_in_cascade >= 30:
        # Stage 3 attempt
        p3 = min(0.40 * cascade_susceptibility + systemic_bonus, 1.0)
        if rng.random() < p3:
            state.stage = 3
            state.missed_emis += 1
            state.penalty_rate = PENALTY_RATE_STAGE3

    if state.stage == 3 and state.days_in_cascade >= 60:
        # Stage 4 attempt (hard default)
        p4 = min(0.25 * cascade_susceptibility, 1.0)
        if rng.random() < p4:
            state.stage = 4
            state.hard_default = True


def trigger_stage1(
    state: CascadeState,
    emi_base: float,
    n_remaining_emis: int,
) -> None:
    """
    Trigger Stage 1 cascade on missed EMI.
    Increases next EMI via: EMI_next = EMI_base × (1 + r_p/12) + overdue/N_remaining
    """
    state.stage = 1
    state.days_in_cascade = 0
    state.missed_emis += 1
    state.overdue_principal += emi_base
    state.penalty_rate = PENALTY_RATE_STAGE1


@dataclass
class CascadeTracker:
    """Tracks cascade state across all N paths for one simulation."""
    n_paths: int
    persona: str
    states: list[CascadeState] = field(default_factory=list)
    _susceptibility: float = 0.0

    def __post_init__(self) -> None:
        self.states = [CascadeState() for _ in range(self.n_paths)]
        self._susceptibility = get_cascade_susceptibility(self.persona)

    def check_systemic_flag(self) -> tuple[bool, float]:
        """Check if >20% of paths are in Stage 2+; return (flag, bonus)."""
        stage2_count = sum(1 for s in self.states if s.stage >= 2)
        frac = stage2_count / max(self.n_paths, 1)
        is_systemic = frac > _SYSTEMIC_THRESHOLD
        bonus = _SYSTEMIC_BONUS if is_systemic else 0.0
        return is_systemic, bonus

    def process_day(
        self,
        path_idx: int,
        cash: float,
        emi_base: float,
        emi_due_today: bool,
        n_remaining_emis: int,
        rng: np.random.Generator,
    ) -> float:
        """
        Process one simulation day for a path.
        Returns: extra penalty cash drain for this day.
        """
        state = self.states[path_idx]

        if state.hard_default:
            return 0.0

        # Advance cascade timer
        if state.stage > 0:
            state.days_in_cascade += 1

        # Check for EMI miss today
        if emi_due_today and cash < emi_base and state.stage == 0:
            trigger_stage1(state, emi_base, n_remaining_emis)

        # Try to escalate cascade
        if state.stage > 0 and state.stage < 4:
            _, systemic_bonus = self.check_systemic_flag()
            try_escalate(state, self._susceptibility, rng, systemic_bonus)

        # Compute daily penalty drain
        return daily_penalty_cashflow(state, emi_base)

    def cascade_analysis(self) -> dict:
        """Aggregate cascade analysis across all paths."""
        n = self.n_paths
        return {
            "paths_reaching_stage1": sum(1 for s in self.states if s.stage >= 1) / n,
            "paths_reaching_stage2": sum(1 for s in self.states if s.stage >= 2) / n,
            "paths_reaching_stage3": sum(1 for s in self.states if s.stage >= 3) / n,
            "paths_reaching_stage4": sum(1 for s in self.states if s.stage >= 4) / n,
            "systemic_stress_flag":  self.check_systemic_flag()[0],
        }

    def stage_matrix(self, horizon: int) -> np.ndarray:
        """
        Return int matrix of shape (n_paths,) with final cascade stage per path.
        Used for EMI stress score computation.
        """
        return np.array([s.stage for s in self.states], dtype=np.float32)
