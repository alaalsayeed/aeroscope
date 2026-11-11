# AeroScope dashboard source

This data-free package keeps the dashboard application source but does not include the case workbook, record-level data, or generated model/result payloads.

- `dist/app.js`, `dist/style.css`, and `dist/final-setup.js` are source assets.
- `AeroScope.html` and `dist/index.html` are static notices that no data is bundled; they do not run the interactive dashboard.
- The analysis and model-selection source files remain available. To run them, use an authorized local workbook and regenerate the ignored outputs as described in the [project README](../README.md).
- The browser test suites skip when their local generated results are absent.

Do not commit the workbook, generated result files, or a locally built data-embedded HTML page. No data-sharing permission or license is included here.
