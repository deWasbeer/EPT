from pathlib import Path
from OpenPinch import PinchProblem

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SAMPLE_CASES = Path("/home/johan/anaconda3/envs/ept_env/lib/python3.14/site-packages/OpenPinch/data/sample_cases")
CASE_DIR = Path(__file__).parent / "pulp_mill"
RESULTS_DIR = CASE_DIR / "results2"
ZONE_NAME = "Bleaching"

# ---------------------------------------------------------------------------
# Load and validate
# ---------------------------------------------------------------------------

problem = PinchProblem()
problem.load(SAMPLE_CASES / "pulp_mill.json")
problem.validate()

# ---------------------------------------------------------------------------
# Target only the Bleaching zone
# ---------------------------------------------------------------------------

# Run direct heat integration only for the specified zone.
problem.target.direct_heat_integration(zone_name=ZONE_NAME)

summary = problem.summary_frame()
print(summary)

# ---------------------------------------------------------------------------
# Generate zone-filtered plots
# ---------------------------------------------------------------------------

gcc = problem.plot.grand_composite_curve(zone_name=ZONE_NAME)
cc = problem.plot.composite_curve(zone_name=ZONE_NAME)
catalog = problem.plot.catalog()

# Keep only the Bleaching rows so the output catalog reflects this run scope.
catalog = catalog[catalog["Zone"] == ZONE_NAME]
print(catalog.to_string(index=False))

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

catalog.to_csv(RESULTS_DIR / "catalog.csv", index=False)
gcc.write_image(RESULTS_DIR / "grand_composite_curve.png")
cc.write_image(RESULTS_DIR / "composite_curve.png")

# Export a zone-filtered interactive HTML gallery.
catalog_dir = RESULTS_DIR / "catalog"
problem.plot.export_gallery(catalog_dir, zone_name=ZONE_NAME)

print(f"\nResults written to: {RESULTS_DIR}")
