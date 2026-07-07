from pathlib import Path
from OpenPinch import PinchProblem

# ---------------------------------------------------------------------------
# Paths — update these two lines if you want to use a different case file or
# write outputs to a different folder.
# ---------------------------------------------------------------------------

# Path to the OpenPinch sample cases bundled with the installed package.
# Other available JSON files in this folder:
#   basic_pinch.json, chocolate_factory.json, crude_preheat_train.json,
#   crude_preheat_train_multistate.json, Four-stream-Yee-and-Grossmann-1990-1.json,
#   heat_pump_targeting.json, zonal_site.json, zonal_site_multistate.json
SAMPLE_CASES = Path("/home/johan/anaconda3/envs/ept_env/lib/python3.14/site-packages/OpenPinch/data/sample_cases")

# Root output folder for this case study. All results are written under here.
# Change "pulp_mill" to match your own case name if you swap the input file.
CASE_DIR = Path(__file__).parent / "pulp_mill"

# ---------------------------------------------------------------------------
# Load and validate
# ---------------------------------------------------------------------------

# Create a fresh PinchProblem instance and load the case from the JSON file.
# To use your own file instead, replace the path with e.g.:
#   problem.load(Path("my_case/my_streams.json"))
# OpenPinch also accepts a directory containing streams.csv + utilities.csv.
problem = PinchProblem()
problem.load(SAMPLE_CASES / "pulp_mill.json")

# Check that the loaded data is physically consistent (hot streams cool down,
# cold streams heat up, required fields present, units compatible, etc.).
problem.validate()

# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

# Compute minimum hot/cold utility targets, pinch temperatures, and maximum
# heat recovery for the specified ΔTmin values in the input file.
result = problem.target()

# Print a tabular summary of the targeting results to the console.
summary = problem.summary_frame()
print(summary)

# ---------------------------------------------------------------------------
# Generate plots (in memory — nothing written to disk yet)
# ---------------------------------------------------------------------------

# Grand Composite Curve: shows net heat surplus/deficit at each temperature
# interval and highlights the pinch point and any pocket regions.
gcc = problem.plot.grand_composite_curve()

# Composite Curves: overlays aggregate hot and cold stream profiles to
# illustrate the minimum utility targets graphically.
cc = problem.plot.composite_curve()

# Catalog: a DataFrame listing every plot OpenPinch can produce for this
# problem (zone, target type, graph type, graph name).
catalog = problem.plot.catalog()
print(catalog.to_string(index=False))

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

# Create the results directory (and any missing parents) if it doesn't exist.
results_dir = CASE_DIR / "results"
results_dir.mkdir(parents=True, exist_ok=True)

# Save the plot catalog as a CSV so it can be opened in a spreadsheet.
catalog.to_csv(results_dir / "catalog.csv", index=False)

# Save the Grand Composite Curve and Composite Curves as PNG images.
# Requires the 'kaleido' package (installed via pip install kaleido).
gcc.write_image(results_dir / "grand_composite_curve.png")
cc.write_image(results_dir / "composite_curve.png")

# ---------------------------------------------------------------------------
# Export full interactive HTML gallery
# ---------------------------------------------------------------------------

import re as _re

# Export every graph in the catalog as its own standalone HTML file.
# The gallery also writes a link-based index.html, which we replace below
# with a single self-contained file for easier viewing in VS Code.
catalog_dir = results_dir / "catalog"
problem.plot.export_gallery(catalog_dir)

# --- Build a single self-contained index.html ---
# Parse the generated index.html to get the correct title/zone order.
_index_src = (catalog_dir / "index.html").read_text(encoding="utf-8")
_ordered = _re.findall(
    r'<a href="([^"]+)">([^<]+)</a>\s*<span>([^<]+)</span>', _index_src
)  # list of (filename, plot_title, zone_name)

# Extract the PlotlyConfig block and Plotly.js bundle from the first plot
# file so we can include them once in the combined page's <head>.
_first_html = (catalog_dir / _ordered[0][0]).read_text(encoding="utf-8")
_spos = [m.start() for m in _re.finditer(r"<script", _first_html)]
_bundle_end = _first_html.find("</script>", _spos[1]) + len("</script>")
_plotly_preamble = _first_html[_spos[0] : _bundle_end]

# For each individual plot file: strip the duplicate PlotlyConfig and
# Plotly.js scripts, keeping only the sizing <div> and newPlot <script>.
_sections = ""
for _fname, _title, _zone in _ordered:
    _html = (catalog_dir / _fname).read_text(encoding="utf-8")
    _body = _html[_html.find("<body>") + len("<body>") : _html.rfind("</body>")].strip()
    # Remove first script block (PlotlyConfig)
    _s1s = _body.find("<script")
    _s1e = _body.find("</script>", _s1s) + len("</script>")
    _body = _body[:_s1s] + _body[_s1e:]
    # Remove second script block (Plotly.js bundle)
    _s2s = _body.find("<script")
    _s2e = _body.find("</script>", _s2s) + len("</script>")
    _body = _body[:_s2s] + _body[_s2e:]
    _sections += (
        f"\n<section>\n<h2>{_title}"
        f" <small>({_zone})</small></h2>\n{_body.strip()}\n</section>\n"
    )

# Write the combined page, replacing the link-based index.html.
# The page title and <h1> heading can be changed to match your case name.
(catalog_dir / "index.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenPinch \u2013 Pulp Mill Graph Catalog</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;line-height:1.5}}
h2{{margin-top:2.5rem;border-bottom:1px solid #ddd;padding-bottom:.25rem}}
small{{color:#888;font-weight:normal;font-size:.75em}}
section{{margin-bottom:1rem}}
</style>
{_plotly_preamble}
</head>
<body>
<h1>OpenPinch \u2013 Pulp Mill</h1>
{_sections}
</body>
</html>""",
    encoding="utf-8",
)

print(f"\nResults written to: {results_dir}")
