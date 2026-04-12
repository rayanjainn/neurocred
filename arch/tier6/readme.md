# Tier 6 Architecture - Predictive Simulation and Stress Engine

## Objective
Tier 6 projects near-term and medium-term financial stress trajectories using Monte Carlo simulation, regime dynamics, correlated shocks, cascade behavior, and recovery planning.

## Implementation Scope
- Simulation request modeling and adaptive horizon selection.
- Regime path and volatility generation.
- Correlated shock simulation with variance reduction.
- Tail-risk, EWS, fan-chart, temporal projection extraction.
- Output caching and twin projection updates.

## Core Modules
- `src/simulation/engine.py`
- `src/simulation/scenario_library.py`
- `src/simulation/garch.py`
- `src/simulation/correlation.py`
- `src/simulation/regime.py`
- `src/simulation/cascade.py`
- `src/simulation/tail_risk.py`
- `src/simulation/ews.py`
- `src/simulation/recovery.py`
- `src/simulation/counterfactual.py`
- `src/simulation/output_emitter.py`

## Data Inputs
- Twin snapshot fields (cash, income, expenses, burden, volatility, persona).
- Scenario and override parameters.
- Simulation path count and variance reduction toggles.

## Processing Layers
1. Scenario Resolution Layer
- Maps baseline/atomic/compound/cascading scenarios to day-level multipliers.

2. Stochastic Dynamics Layer
- Builds GARCH volatility matrix per path/day.
- Generates correlated shocks using Sobol and antithetic controls.
- Evolves cash state under regime transitions.

3. Cascading Stress Layer
- Tracks EMI stress cascade state across paths.
- Applies penalties and due-date effects.

4. Risk Extraction Layer
- Computes default probabilities, VaR/CVaR, fan chart quantiles, EWS, and crash stats.
- Produces temporal day-30/day-60/day-90 projections.

5. Intervention and Recovery Layer
- Finds recovery plan actions via search heuristic.
- Runs optional counterfactual analyses.

6. Emission Layer
- Caches full simulation output and compact derivatives.
- Updates twin projection fields and emits completion events.

## Contracts and Guarantees
- Simulation response includes IDs, tail risk, EWS, fan chart, temporal projections, and recovery outputs.
- Output keys are stable for frontend and Tier 10 report assembly.
- Default threshold logic is conservative and explicit.

## Redis and Storage Interfaces
- Full result cache: `sim:{user_id}:{sim_id}`
- EWS cache: `sim:ews:{user_id}`
- Fan cache: `sim:fan:{user_id}`
- Twin update writeback: `twin:{user_id}`
- Event publish: `simulation_completed`

## Failure and Recovery Behavior
- Missing optional counterfactual does not fail base simulation.
- Emitter writes are best effort for supplementary artifacts.
- API layer returns health and missing-data diagnostics.

## Outputs
- Quantitative forward risk trajectory artifacts.
- Early warning probabilities and severity labels.
- Inputs for intervention offers and Tier 10 what-if/reporting.

## Dependency Edges
- Upstream: Tier 4 twin state and optional Tier 3 feature-derived snapshot fields.
- Downstream: Tier 4 projected patching, Tier 8 proactive interventions, Tier 10 reporting.

## What Tier 6 Enables
- Evidence-based stress anticipation beyond static scores.
- Scenario and what-if analysis with reproducible seeds.
- Operational EWS signaling for proactive action.
