# Import the PinchProblem class from the OpenPinch library, which provides
# pinch analysis functionality for heat exchanger network (HEN) design.
from pathlib import Path
from OpenPinch import PinchProblem

# Root directory that groups all input and output files for this case study.
# All sub-paths below are resolved relative to this directory so that the
# script can be run from any working directory.
CASE_DIR = Path(__file__).parent / "kemp_example"

# Create a new, empty PinchProblem instance that will hold all stream data,
# options, and analysis results for this heat integration study.
problem = PinchProblem()

# Choose which input file format to use. Set USE_CSV = True to load stream data
# from a CSV file (columns: zone, name, t_supply, t_target, heat_flow, dt_cont),
# or False to load from a JSON file where the same fields are nested under a
# "streams" key. Both formats are supported natively by PinchProblem.load().
USE_CSV = False

if USE_CSV:
    # Load stream definitions from the kemp_example/csv/ directory.
    # OpenPinch expects a directory containing exactly two CSV files:
    #   streams.csv  – columns: zone, name, t_supply, t_target, heat_flow,
    #                            dt_cont, htc, loc, index
    #                  row 1 = column labels, row 2 = unit strings, row 3+ = data
    #   utilities.csv – columns: name, type, t_supply, t_target, dt_cont,
    #                             price, htc, heat_flow
    #                  same row layout; rows with an empty name are dropped.
    # Both files contain the same streams and (empty) utilities as the JSON file.
    problem.load(CASE_DIR / "csv")
else:
    # Load the problem definition (streams, temperatures, heat flows, and options)
    # from the JSON file. Each stream entry defines supply/target temperatures,
    # heat flow rate, minimum approach temperature contribution (dt_cont), and zone.
    problem.load(CASE_DIR / "json" / "kemp_example.json")

# Validate the loaded problem data to ensure all required fields are present,
# units are consistent, and the stream definitions are physically meaningful
# (e.g. hot streams cool down, cold streams heat up).
problem.validate()

# Run the pinch targeting calculation: determines the minimum hot and cold
# utility requirements, the pinch temperature(s), and the maximum heat recovery
# achievable for the given minimum approach temperature (ΔTmin).
result = problem.target()

# Build a pandas DataFrame summarising the targeting results for every state
# (e.g. Site/Direct Integration, Plant/Direct Integration), including pinch
# temperatures, hot utility target, cold utility target, and heat recovery.
summary = problem.summary_frame()

# Print the summary DataFrame to the console so the results can be inspected.
print(summary)

# Generate a Plotly figure of the Grand Composite Curve (GCC), which shows the
# net heat surplus/deficit at each temperature interval and highlights the pinch
# point and pocket regions available for process-to-process heat integration.
gcc = problem.plot.grand_composite_curve()

# Generate a Plotly figure of the Composite Curves (hot and cold), which
# visualise the aggregate heat availability and demand across all temperature
# intervals and illustrate the minimum utility targets graphically.
cc = problem.plot.composite_curve()

# Build a DataFrame cataloguing every plot that OpenPinch can produce for this
# problem, including the zone, target type, graph type, and graph name. This
# acts as an index of all available visualisations before exporting them.
catalog = problem.plot.catalog()

# Print the catalog so it is visible in the console output, giving a quick
# overview of which graphs will be written to the results folder.
print(catalog.to_string(index=False))

# Save the catalog as a CSV file in the results folder so it can be opened in
# a spreadsheet for reference alongside the exported plot files.
catalog.to_csv(CASE_DIR / "results" / "catalog.csv", index=False)

# Export the Grand Composite Curve figure as a static PNG image file inside
# the kemp_example/results/ folder, keeping all outputs in one place.
gcc.write_image(CASE_DIR / "results" / "grand_composite_curve.png")

# Export the Composite Curves figure as a static PNG image file inside
# the kemp_example/results/ folder.
cc.write_image(CASE_DIR / "results" / "composite_curve.png")

# Export every graph listed in the catalog as standalone HTML files to
# results/catalog/. export_gallery also writes an index.html with relative
# links, but those are replaced below with a single self-contained page.
import re as _re

catalog_dir = CASE_DIR / "results" / "catalog"
problem.plot.export_gallery(catalog_dir)

# VS Code's built-in HTML preview blocks file:// link navigation, so the
# default link-based index.html does not work there. Replace it with a single
# self-contained page that embeds all 14 plots inline — Plotly.js is included
# once at the top, and each plot's sizing div + newPlot script follows in
# sequence. No inter-file navigation is required.

# Parse the generated index.html to get the correct title/zone order before
# we overwrite it.
_index_src = (catalog_dir / "index.html").read_text(encoding="utf-8")
_ordered = _re.findall(
    r'<a href="([^"]+)">([^<]+)</a>\s*<span>([^<]+)</span>', _index_src
)  # [(filename, title, zone), ...]

# Extract the PlotlyConfig script and Plotly.js bundle from the first plot
# file. These two script blocks are included once in the combined <head>;
# every subsequent newPlot call reuses the already-loaded Plotly object.
_first_html = (catalog_dir / _ordered[0][0]).read_text(encoding="utf-8")
_spos = [m.start() for m in _re.finditer(r"<script", _first_html)]
_bundle_end = _first_html.find("</script>", _spos[1]) + len("</script>")
_plotly_preamble = _first_html[_spos[0] : _bundle_end]

# For each plot file: strip the redundant PlotlyConfig and Plotly.js scripts,
# keeping only the sizing <div>, the empty plot <div>, and the newPlot <script>.
_sections = ""
for _fname, _title, _zone in _ordered:
    _html = (catalog_dir / _fname).read_text(encoding="utf-8")
    _body = _html[_html.find("<body>") + len("<body>") : _html.rfind("</body>")].strip()
    # Remove PlotlyConfig script (first script block)
    _s1s = _body.find("<script")
    _s1e = _body.find("</script>", _s1s) + len("</script>")
    _body = _body[:_s1s] + _body[_s1e:]
    # Remove Plotly.js bundle (now the first remaining script block)
    _s2s = _body.find("<script")
    _s2e = _body.find("</script>", _s2s) + len("</script>")
    _body = _body[:_s2s] + _body[_s2e:]
    _sections += (
        f"\n<section>\n<h2>{_title}"
        f" <small>({_zone})</small></h2>\n{_body.strip()}\n</section>\n"
    )

# Write the combined single-file index.html, replacing the link-based version.
(catalog_dir / "index.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenPinch \u2013 Graph Catalog</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;line-height:1.5}}
h2{{margin-top:2.5rem;border-bottom:1px solid #ddd;padding-bottom:.25rem}}
small{{color:#888;font-weight:normal;font-size:.75em}}
section{{margin-bottom:1rem}}
</style>
{_plotly_preamble}
</head>
<body>
<h1>OpenPinch \u2013 Graph Catalog</h1>
{_sections}
</body>
</html>""",
    encoding="utf-8",
)

# Print the list of state IDs defined for this problem. Each state represents
# a different integration scenario (e.g. plant-wide or site-level integration);
# the IDs are used to select a specific state for deeper analysis below.
print(problem.state_ids)

# Re-run targeting for state "0" using the direct heat integration method,
# which computes utility targets assuming streams within the same zone (plant)
# can exchange heat directly without site-level steam or hot-water circuits.
peak_target = problem.target.direct_heat_integration(state_id="0")

# Rebuild the summary DataFrame to reflect the results of the direct heat
# integration targeting that was just performed for state "0".
peak_summary = problem.summary_frame()

# Print only the Target scenario name, State ID, and Hot Utility Target columns
# from the updated summary so the effect of direct integration can be compared
# against the baseline targeting results.
print(peak_summary[["Target", "State ID", "Hot Utility Target"]])

# Run the targeting calculation across all defined states simultaneously using
# Python threads (parallel="thread"), which speeds up the analysis when many
# states or integration scenarios are present.
all_state_results = problem.target_all_states(parallel="thread")

# Print the dictionary keys of the results object to confirm which state IDs
# were successfully computed in the parallel targeting run.
print(all_state_results.keys())