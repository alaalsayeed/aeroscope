"""Create a local-only standalone dashboard after explicit data opt-in."""
import os
from pathlib import Path

root = Path(__file__).parent
d = root / "dist"
if os.environ.get("AEROSCOPE_ALLOW_EMBEDDED_DATA") != "1":
    raise SystemExit(
        "This builder embeds the local dataset and row-level results. "
        "Refusing by default; use only authorized local data and set "
        "AEROSCOPE_ALLOW_EMBEDDED_DATA=1 for a local-only build."
    )
required = ["data.js", "app.js", "final-data.js", "final-setup.js"]
missing = [name for name in required if not (d / name).is_file()]
if missing:
    raise SystemExit("Generate authorized local result files first: " + ", ".join(missing))

html = (d / "dashboard-template.html").read_text()
css = (d / "style.css").read_text()
css = "\n".join(line for line in css.splitlines() if not line.startswith("@import"))
html = html.replace('<link rel="stylesheet" href="style.css">', "<style>" + css + "</style>")
html = html.replace("SOURCE DATA OMITTED", "LOCAL WORKBOOK CONNECTED")
html = html.replace("Workbook and generated results are not bundled.", "Local authorized workbook and generated results loaded.")
for name in required:
    html = html.replace(
        f'<script src="{name}"></script>',
        "<script>" + (d / name).read_text().replace("</script", "<\\/script") + "</script>",
    )
out = root / "AeroScope.local.html"
out.write_text(html)
print("Created AeroScope.local.html. It embeds local records and results; keep it private and do not commit it.")
