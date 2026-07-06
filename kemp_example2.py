# Import Path for building file paths relative to this script's location.
from pathlib import Path

# Import PinchProblem for targeting and HeatExchangerNetwork/HeatExchanger for
# manually constructing the heat exchanger network (HEN) design.
from OpenPinch import PinchProblem
from OpenPinch.classes.heat_exchanger_network import HeatExchangerNetwork
from OpenPinch.classes.heat_exchanger import (
    HeatExchanger,
    HeatExchangerKind,
    HeatExchangerStreamRole,
)

# ── Shorthand aliases for the enum values used throughout ────────────────────
# PROC: the stream is a process stream (participates in heat recovery).
# UTIL: the stream is a hot or cold utility.
# REC:  recovery exchanger — process-to-process heat transfer.
# HU:   hot utility exchanger — utility heats a process stream.
# CU:   cold utility exchanger — process stream rejects heat to cold utility.
PROC = HeatExchangerStreamRole.PROCESS
UTIL = HeatExchangerStreamRole.UTILITY
REC  = HeatExchangerKind.RECOVERY
HU   = HeatExchangerKind.HOT_UTILITY
CU   = HeatExchangerKind.COLD_UTILITY

# Root directory that groups all input and output files for this case study.
CASE_DIR = Path(__file__).parent / "kemp_example2"

# ── Problem loading ──────────────────────────────────────────────────────────
# Create a PinchProblem instance and load the same four-stream Kemp problem
# that is used in kemp_example. The stream data is identical; this script
# extends the analysis by adding a specific HEN design on top of the targets.
problem = PinchProblem()
problem.load(CASE_DIR / "json" / "kemp_example2.json")

# Validate that all stream fields are consistent and physically meaningful.
problem.validate()

# Run the pinch targeting calculation to determine minimum utilities and the
# pinch temperature before any HEN design is attempted.
problem.target()

# Print the targeting summary so the baseline targets are visible.
summary = problem.summary_frame()
print(summary)

# ── Stream data reference (for the reader) ──────────────────────────────────
# F1 (COLD): 20 → 135 °C, CP = 2.0 kW/°C, Q_total = 230 kW
# F2 (HOT):  170 → 60 °C, CP = 3.0 kW/°C, Q_total = 330 kW
# F3 (COLD): 80 → 140 °C, CP = 4.0 kW/°C, Q_total = 240 kW
# F4 (HOT):  150 → 30 °C, CP = 1.5 kW/°C, Q_total = 180 kW
#
# Pinch temperature: 90 °C (hot side) / 80 °C (cold side)  [shown as 85 °C]
# Minimum hot utility:  20 kW
# Minimum cold utility: 60 kW
# Maximum heat recovery: 450 kW

# ── HEN design: above-pinch section ─────────────────────────────────────────
# Above the pinch (hot streams ≥ 90 °C, cold streams ≥ 80 °C):
#
#   F2: 170 → 90 °C  available heat = 3.0 × (170 − 90) = 240 kW
#   F4: 150 → 90 °C  available heat = 1.5 × (150 − 90) =  90 kW
#   F1:  80 → 135 °C  heat demand   = 2.0 × (135 −  80) = 110 kW
#   F3:  80 → 140 °C  heat demand   = 4.0 × (140 −  80) = 240 kW
#
# Match 1 — F2 ↔ F3 (stage 1, above pinch):
#   CP_cold (4.0) ≥ CP_hot (3.0) → satisfies the above-pinch design rule.
#   Q = 240 kW; F2 is fully cooled to the pinch (90 °C); F3 is fully heated
#   from the cold-side pinch (80 °C) to its target (140 °C).
#   ΔT_hot_end = 170 − 140 = 30 °C ≥ ΔTmin (10 °C) ✓
#   ΔT_cold_end = 90 − 80 = 10 °C = ΔTmin ✓
#
# Match 2 — F4 ↔ F1 (stage 1, above pinch):
#   CP_cold (2.0) ≥ CP_hot (1.5) → satisfies the above-pinch design rule.
#   Q = 90 kW (limited by F4 reaching pinch); F1 is partially heated
#   from 80 °C to 125 °C; the remaining 20 kW comes from hot utility.
#   ΔT_hot_end = 150 − 125 = 25 °C ≥ ΔTmin ✓
#   ΔT_cold_end = 90 − 80 = 10 °C = ΔTmin ✓

# ── HEN design: below-pinch section ─────────────────────────────────────────
# Below the pinch (hot streams ≤ 90 °C, cold streams ≤ 80 °C):
#
#   F2:  90 → 60 °C  available heat = 3.0 × (90 − 60) = 90 kW
#   F4:  90 → 30 °C  available heat = 1.5 × (90 − 30) = 90 kW
#   F1:  20 → 80 °C  heat demand    = 2.0 × (80 − 20) = 120 kW
#   (F3 supply = 80 °C = cold-side pinch, so F3 has no load below pinch.)
#
# Match 3 — F2 ↔ F1 (stage 2, below pinch):
#   CP_hot (3.0) ≥ CP_cold (2.0) → satisfies the below-pinch design rule.
#   Q = 90 kW (limited by F2 reaching 60 °C); F1 is heated from 35 → 80 °C.
#   ΔT_hot_end = 90 − 80 = 10 °C = ΔTmin ✓
#   ΔT_cold_end = 60 − 35 = 25 °C ≥ ΔTmin ✓
#
# Match 4 — F4 ↔ F1 (stage 2, below pinch):
#   Remaining F1 duty: 2.0 × (35 − 20) = 30 kW; F4 cools from 90 → 70 °C.
#   ΔT_hot_end = 90 − 35 = 55 °C ≥ ΔTmin ✓
#   ΔT_cold_end = 70 − 20 = 50 °C ≥ ΔTmin ✓
#   Remaining F4: 70 → 30 °C, Q = 60 kW → cold utility.

# ── Build the HeatExchangerNetwork object ────────────────────────────────────
# Each HeatExchanger specifies:
#   kind              — RECOVERY, HOT_UTILITY, or COLD_UTILITY
#   stage             — 1 = above pinch, 2 = below pinch (required for RECOVERY)
#   source_stream     — name of the hot-side stream (or utility name)
#   sink_stream       — name of the cold-side stream (or utility name)
#   source/sink _stream_role — PROCESS or UTILITY
#   duty              — heat transferred [kW]
#   *_inlet/outlet_temperature — stream temperatures entering/leaving this HX [K]
#                                 (the grid diagram renderer subtracts 273.15
#                                  to display °C, so all values are in Kelvin)
network = HeatExchangerNetwork(
    exchangers=(

        # ── Above-pinch exchangers (stage 1) ────────────────────────────────

        # HX-1: F2 (hot) supplies 240 kW to F3 (cold) above the pinch.
        # F2 is cooled from its supply temperature (170 °C) to the hot-side
        # pinch temperature (90 °C). F3 is heated from the cold-side pinch
        # temperature (80 °C) to its target (140 °C).
        HeatExchanger(
            kind=REC, stage=1,
            source_stream="F2", source_stream_role=PROC,
            sink_stream="F3",   sink_stream_role=PROC,
            duty=240.0,
            source_inlet_temperature=443.15, source_outlet_temperature=363.15,
            sink_inlet_temperature=353.15,   sink_outlet_temperature=413.15,
        ),

        # HX-2: F4 (hot) supplies 90 kW to F1 (cold) above the pinch.
        # F4 is cooled from 150 °C to the hot-side pinch temperature (90 °C).
        # F1 is partially heated from 80 °C to 125 °C; it still needs 20 kW
        # of hot utility to reach its target of 135 °C.
        HeatExchanger(
            kind=REC, stage=1,
            source_stream="F4", source_stream_role=PROC,
            sink_stream="F1",   sink_stream_role=PROC,
            duty=90.0,
            source_inlet_temperature=423.15, source_outlet_temperature=363.15,
            sink_inlet_temperature=353.15,   sink_outlet_temperature=398.15,
        ),

        # HX-HU: Hot utility provides the remaining 20 kW to bring F1 from
        # 125 °C to its target (135 °C). This equals the minimum hot utility
        # target calculated during pinch targeting.
        HeatExchanger(
            kind=HU,
            source_stream="Default HU", source_stream_role=UTIL,
            sink_stream="F1",           sink_stream_role=PROC,
            duty=20.0,
            sink_inlet_temperature=398.15, sink_outlet_temperature=408.15,
        ),

        # ── Below-pinch exchangers (stage 2) ────────────────────────────────

        # HX-3: F2 (hot) supplies 90 kW to F1 (cold) below the pinch.
        # F2 is cooled from the hot-side pinch temperature (90 °C) to its
        # target (60 °C). F1 is heated from 35 °C to the cold-side pinch
        # temperature (80 °C).
        HeatExchanger(
            kind=REC, stage=2,
            source_stream="F2", source_stream_role=PROC,
            sink_stream="F1",   sink_stream_role=PROC,
            duty=90.0,
            source_inlet_temperature=363.15, source_outlet_temperature=333.15,
            sink_inlet_temperature=308.15,   sink_outlet_temperature=353.15,
        ),

        # HX-4: F4 (hot) supplies 30 kW to F1 (cold) below the pinch.
        # F4 cools from 90 °C to 70 °C, and F1 is heated from its supply
        # temperature (20 °C) to 35 °C. The remaining 60 kW in F4 is then
        # rejected to cold utility.
        HeatExchanger(
            kind=REC, stage=2,
            source_stream="F4", source_stream_role=PROC,
            sink_stream="F1",   sink_stream_role=PROC,
            duty=30.0,
            source_inlet_temperature=363.15, source_outlet_temperature=343.15,
            sink_inlet_temperature=293.15,   sink_outlet_temperature=308.15,
        ),

        # HX-CU: Cold utility removes the remaining 60 kW from F4 (70 → 30 °C).
        # This equals the minimum cold utility target from pinch targeting.
        HeatExchanger(
            kind=CU,
            source_stream="F4",         source_stream_role=PROC,
            sink_stream="Default CU",   sink_stream_role=UTIL,
            duty=60.0,
            source_inlet_temperature=343.15, source_outlet_temperature=303.15,
        ),
    )
)

# ── Print HEN energy summary ─────────────────────────────────────────────────
# Verify that the designed network achieves the targeting minima.
print(f"\nHEN energy summary:")
print(f"  Total heat recovery : {network.total_duty(kind=REC):.1f} kW  (target: 450.0 kW)")
print(f"  Total hot utility   : {network.total_duty(kind=HU):.1f} kW   (target:  20.0 kW)")
print(f"  Total cold utility  : {network.total_duty(kind=CU):.1f} kW   (target:  60.0 kW)")

# ── Build and save the grid diagram ─────────────────────────────────────────
# The grid diagram is the standard representation of a HEN: horizontal lines
# for each stream (hot left-to-right, cold right-to-left) with vertical links
# showing each heat exchanger. Utility exchangers appear at the stream ends.
grid = network.build_grid_diagram()

# Save the grid diagram as a PNG image to the results folder.
grid.save(CASE_DIR / "results" / "grid_diagram.png")

# Also save as an interactive HTML so temperatures and duties can be inspected
# by hovering over the exchangers in a browser.
grid.save(CASE_DIR / "results" / "grid_diagram.html")

print("Grid diagram saved to results/")

# ── Save composite curves and GCC for reference ──────────────────────────────
# These plots are the same as in kemp_example — they show the targeting
# context (pinch point, utility targets) against which the HEN above was
# designed.
gcc = problem.plot.grand_composite_curve()
cc  = problem.plot.composite_curve()

gcc.write_image(CASE_DIR / "results" / "grand_composite_curve.png")
cc.write_image(CASE_DIR  / "results" / "composite_curve.png")

print("Composite curves saved to results/")
