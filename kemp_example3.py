# Ensure the conda-env bin directory is on PATH so that ipopt (needed by the
# ESM stage) can be located by Pyomo's SolverFactory at runtime.
import os, sys
_ENV_BIN = os.path.join(sys.prefix, "bin")
if _ENV_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ENV_BIN + os.pathsep + os.environ.get("PATH", "")

# Suppress minor solver/GEKKO warnings that do not affect results.
import warnings
warnings.filterwarnings("ignore")

import logging
import matplotlib
matplotlib.use("Agg")   # non-interactive backend — no display needed
import matplotlib.pyplot as plt
from pathlib import Path

from openhens.classes.HEN_problem import HeatExchangerNetworkProblem
from openhens.utils.branching import run_parallel_solutions
# ── Directory layout ─────────────────────────────────────────────────────────
CASE_DIR = Path(__file__).parent / "kemp_example3"
CSV_FILE  = CASE_DIR / "csv" / "kemp_example3.csv"
RESULTS   = CASE_DIR / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# ── Problem description ───────────────────────────────────────────────────────
# This script applies OpenHENS to the same four-stream Kemp problem used in
# kemp_example and kemp_example2, but now lets the optimiser find the minimum-
# cost heat exchanger network (HEN) automatically.
#
# Stream data (same as kemp_example):
#   F2 (HOT):  170 → 60 °C  (443.15 → 333.15 K)  CP = 3.0 kW/K
#   F4 (HOT):  150 → 30 °C  (423.15 → 303.15 K)  CP = 1.5 kW/K
#   F1 (COLD):  20 → 135 °C (293.15 → 408.15 K)  CP = 2.0 kW/K
#   F3 (COLD):  80 → 140 °C (353.15 → 413.15 K)  CP = 4.0 kW/K
#
# Utilities:
#   Hot utility  – Steam at 200 °C (473.15 K), cost = 80 $/kW-y
#   Cold utility – Cooling water 20 → 30 °C, cost = 15 $/kW-y
#
# Cost model (Yee & Grossmann, 1990):
#   HX capital cost = 5 500 $/y fixed + 150 $/m²-y × area
#
# OpenHENS solves in three sequential stages:
#   1. PDM  – Pinch Decomposition Model (MINLP, APOPT solver)
#             Determines stream match topology above and below the pinch that
#             minimises hot utility consumption.
#   2. TDM  – Thermal Derivative Model (MINLP, APOPT solver)
#             Refines the topology by maximising dQ/dA (heat transferred per
#             unit area), trading off recovery against area cost.
#   3. ESM  – Evolutionary Synthesis Model (continuous NLP, IPOPT solver)
#             Relaxes the integer variables and minimises Total Annual Cost
#             (TAC = capital + operating) using the TDM topology as a warm start.

# ── Solver notes ─────────────────────────────────────────────────────────────
# OpenHENS normally uses Couenne (COIN-OR MINLP solver) for PDM and TDM.
# Couenne is not available in this environment, so APOPT (bundled with GEKKO)
# is used as a substitute for those two stages. APOPT handles mixed-integer
# problems and gives equivalent topology results for this problem size.
# The ESM stage uses IPOPT via Pyomo, which is already installed.

# OpenHENS uses Python multiprocessing.  ALL executable code that triggers
# multiprocessing must live inside this guard to prevent child processes from
# re-running the script body when they import it.
if __name__ == "__main__":
    # ── Stage 1: Pinch Decomposition Method (PDM) ────────────────────────────
    # The PDM uses a stage-wise superstructure split at the pinch temperature.
    # It solves a MINLP to find the minimum hot utility for the given ΔTmin.
    # Binary variables encode which stream pairs are allowed to exchange heat in
    # each stage; APOPT resolves the integer assignments locally.
    print("Stage 1 / 3 – Pinch Decomposition Method (PDM) …")
    pdm_problem = HeatExchangerNetworkProblem(
        name="Kemp-PDM-dT10",
        framework="PDM",
        # APOPT is GEKKO's built-in MINLP solver; used here instead of Couenne.
        solver="apopt",
        # ΔTmin = 10 °C — the minimum approach temperature between any hot/cold pair.
        dTmin=10.0,
        import_file=str(CSV_FILE),
        min_dqda=0,
        z_restriction=[None, None, None],
        # Objective: minimise hot utility consumption.
        minimisation_goal="hot utility",
        non_isothermal_model=False,
        integers=True,
        parent=None,
        tol=1e-3,
        # "automated" lets OpenHENS determine the number of superstructure stages.
        stage_selection="automated",
    )
    pdm_solutions = run_parallel_solutions(
        [pdm_problem], max_parallel=1, print_output=False, evolution=False
    )

    if not pdm_solutions:
        print("PDM produced no solution — aborting.")
        sys.exit(1)

    pdm_best = pdm_solutions[0]
    print(f"  PDM complete: {pdm_best.case.stages} superstructure stage(s) found.")

    # ── Stage 2: Thermal Derivative Method (TDM) ─────────────────────────────
    # The TDM uses the PDM topology as a warm start and sweeps over a range of
    # dQ/dA (heat flux per unit area) thresholds. Low dQ/dA values allow small,
    # area-intensive exchangers; high values prune them. Here a single intermediate
    # value is used to keep runtime short.
    print("Stage 2 / 3 – Thermal Derivative Method (TDM) …")
    tdm_args = pdm_best.args.copy()
    tdm_args.update({
        "name": "Kemp-TDM-dQdA1.5",
        "framework": "TDM",
        # APOPT for the TDM MINLP as well.
        "solver": "apopt",
        # Near-zero ΔTmin allows the TDM to move heat freely across the pinch
        # once the topology is fixed by the PDM.
        "dTmin": 0.1,
        "non_isothermal_model": False,
        "integers": True,
        # dQ/dA threshold: exchangers below this value are penalised/removed.
        "min_dqda": 1.5,
        "minimisation_goal": "hot utility",
        # Restrict heat recovery to at least what the PDM found.
        "z_restriction": [pdm_best.case.Q_r, None, None],
    })
    tdm_problem = HeatExchangerNetworkProblem(**tdm_args, parent=pdm_best)
    tdm_solutions = run_parallel_solutions(
        [tdm_problem], max_parallel=1, print_output=False, evolution=False
    )

    if not tdm_solutions:
        print("TDM produced no solution — aborting.")
        sys.exit(1)

    tdm_best = tdm_solutions[0]
    print("  TDM complete.")

    # ── Stage 3: Evolutionary Synthesis Method (ESM) ─────────────────────────
    # The ESM relaxes all integer variables and solves a continuous NLP with IPOPT.
    # The objective switches to minimising Total Annual Cost (TAC), which balances
    # the cost of heat exchanger area against utility operating cost. The TDM
    # solution provides a good initial point for the NLP.
    print("Stage 3 / 3 – Evolutionary Synthesis Method (ESM, IPOPT) …")
    esm_args = tdm_best.args.copy()
    esm_args.update({
        "name": "Kemp-ESM",
        "framework": "ESM",
        # IPOPT (via Pyomo) solves the continuous NLP; no integer variables here.
        "solver": "ipopt-pyomo",
        # Non-isothermal model accounts for temperature variation along each HX.
        "non_isothermal_model": True,
        "integers": False,
        # Objective: minimise variable total cost (capital + utility operating).
        "minimisation_goal": "variable total cost",
        "z_restriction": [tdm_best.case.Q_r, None, None],
    })
    esm_problem = HeatExchangerNetworkProblem(**esm_args, parent=tdm_best)
    esm_solutions = run_parallel_solutions(
        [esm_problem], max_parallel=1, print_output=False, evolution=False
    )

    if not esm_solutions:
        print("ESM produced no solution — aborting.")
        sys.exit(1)

    esm_best = esm_solutions[0]

    # ── Results summary ───────────────────────────────────────────────────────
    # TAC = capital cost (area-based) + hot utility cost + cold utility cost.
    # Q_h and Q_c are the hot and cold utility duties in kW.
    # Q_r_total is the total process-to-process heat recovery in kW.
    def _v(x):
        """Return scalar float from a GEKKO variable, list, or plain float."""
        if hasattr(x, "value"):
            v = x.value
            return float(v[0]) if hasattr(v, "__iter__") else float(v)
        if hasattr(x, "__iter__"):
            return float(list(x)[0])
        return float(x)

    qhu = _v(esm_best.case.Q_hu_total)
    qcu = _v(esm_best.case.Q_cu_total)
    qr  = _v(esm_best.case.Q_r_total)
    hu_cost  = qhu * _v(esm_best.case.hu_cost)
    cu_cost  = qcu * _v(esm_best.case.cu_cost)
    cap_cost = esm_best.case.TAC - hu_cost - cu_cost
    print(f"\nOptimisation complete.")
    print(f"  Total Annual Cost (TAC)      : {esm_best.case.TAC:,.0f} $/y")
    print(f"  Capital cost (HX area)       : {cap_cost:,.0f} $/y")
    print(f"  Hot utility operating cost   : {hu_cost:,.0f} $/y")
    print(f"  Cold utility operating cost  : {cu_cost:,.0f} $/y")
    print(f"  Hot utility consumption      : {qhu:.1f} kW")
    print(f"  Cold utility consumption     : {qcu:.1f} kW")
    print(f"  Total heat recovery          : {qr:.1f} kW")

    # ── Save grid diagram ─────────────────────────────────────────────────────
    # The grid diagram shows each process stream as a horizontal line, with
    # vertical links representing heat exchangers. Utility connections appear at
    # the stream end-points. The diagram reflects the cost-optimal network found
    # by the ESM, which may differ from the manually designed network in
    # kemp_example2 if exchangers were removed or rerouted to reduce cost.
    # get_grid_diagram() returns a Grid_Diagram object with its own .save() method.
    grid = esm_best.get_grid_diagram(draw_stages=False)
    grid.fig.suptitle("Kemp Example – OpenHENS Optimal HEN (Grid Diagram)", y=0.98)
    grid.save(str(RESULTS / "grid_diagram.png"))
    plt.close("all")
    print(f"\nGrid diagram saved to results/")
