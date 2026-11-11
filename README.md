# AeroScope — Aviation Maintenance Intelligence

A transparent research prototype for three aviation maintenance challenges: actuator failure prediction, maintenance delay prediction, and belt defect investigation.

## Data-free package

This version preserves the team's analysis, model-selection, dashboard, and test code, but omits the supplied hackathon workbook and all row-level records and generated result bundles. Notebook execution outputs and sample prediction inputs have also been cleared. `aviation-dashboard/AeroScope.html` and `aviation-dashboard/dist/index.html` are static notices; they do not load records or run the dashboard. The browser application source remains in `aviation-dashboard/dist/app.js`.

The summary metrics and limitations below are aggregate project findings retained from the original project README. They are not a new evaluation and do not contain individual records. No dataset or software license is added.

## Models and aggregate results

The existing work selected these final model forms:

| Task | Final model | Configuration |
|---|---|---|
| 1: 30-day actuator failure | CART decision tree | Depth 3; minimum leaf 2 |
| 2: Maintenance delay | CART decision tree | Depth 3; minimum leaf 2 |
| 2: Delay duration | Ridge regression | α = 0.1; negative estimates clipped to zero |
| 3: Belt defect | CART decision stump | Depth 1; minimum leaf 2 |

The following nested internal-validation summaries are retained from the original project documentation:

| Task | Aircraft accuracy | Aircraft F1 | Later-month accuracy | Later-month recall |
|---|---:|---:|---:|---:|
| Actuator failure | 97.2% | 92.3% | 84.6% | 33.3% |
| Maintenance delay | 83.3% | 78.3% | 77.3% | 63.6% |
| Belt defect | 100% | 100% | 100% | 100% |

Delay-duration mean absolute error was 17.8 minutes on aircraft-held-out folds and 16.7 minutes on later-month records. These are internal estimates from a small development dataset that had already been used during experimentation; there is no untouched external test set.

## Interpretation and limits

- The actuator model missed four of six failures in later-month testing. Its aircraft-held-out score alone does not establish reliable forecasting.
- Delay models exclude actual transport time from pre-job predictions. Shortage effects cannot be estimated from the supplied observations.
- Belt-defect scores are predictive associations, not causal evidence. Tool identity and calibration are confounded in the original analysis.
- Exact timestamps are unavailable, so the 30-day outcome-maturity gap cannot be verified. Independent future data is needed before any maintenance decision relies on these models.

## Files retained

- `AeroScope.ipynb`: analysis and validation code, with saved outputs and sample inputs removed. It requires authorized local data and generated results before it can run.
- `aviation-dashboard/analyze.py`, `benchmark.py`, and `optimize.py`: dependency-free analysis and model-selection source.
- `aviation-dashboard/dist/app.js`, `style.css`, `final-setup.js`, and `dashboard-template.html`: dashboard source; no record or result payloads are bundled.
- `aviation-dashboard/test_*.py`, `test_*.cjs`: tests. Python unit tests run without the source workbook; browser tests skip when local generated results are absent.
- `aviation-dashboard/AeroScope.html` and `aviation-dashboard/dist/index.html`: data-free notices, not the interactive dashboard.

## Reproduce locally

Only if you have permission to use the hackathon data, place an authorized `Cases Data.xlsx` copy in this project root. The workbook and generated row-level files are ignored by Git. From `aviation-dashboard`, run:

```sh
python3 analyze.py
python3 benchmark.py
python3 optimize.py
```

Then open the notebook to inspect the analysis. The standalone HTML builder embeds local records and result files, so it requires an explicit local opt-in and writes an ignored file:

```sh
AEROSCOPE_ALLOW_EMBEDDED_DATA=1 python3 package_artifact.py
```

This creates `AeroScope.local.html`. Do not commit or publish that file or the ignored data/results. The opt-in is not permission to redistribute them.

## Checks

From `aviation-dashboard`:

```sh
python3 -m unittest test_analysis.py
node test_interface.cjs
AEROSCOPE_FINAL=1 node test_navigation.cjs
```

The JavaScript suites report a skip when generated local result files are absent. No generated project results are included in this data-free package.

## Sharing note

The project bundle contained no `LICENSE` file or permission to redistribute the supplied dataset. This package excludes that dataset and row-level outputs; confirm the event and team terms before adding or sharing data. The static pages and ignored-file rules help avoid accidental inclusion, but do not replace a content review before publishing.
