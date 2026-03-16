# QXDM 5G NR Carrier Aggregation (CA) Analyzer

This repo contains a small toolchain for analyzing large QXDM NR5G CA text logs and producing:
- Windowed metrics (`.csv`)
- A cached summary (`summary.json`)
- Plots (`.svg`)
- A research-style dashboard (`research_dashboard.html`) and summary markdown

## Requirements

- Python 3.10+ (recommended)
- Python packages:
  - `matplotlib`
  - `cycler`

Install dependencies:

```bash
python -m pip install matplotlib cycler
```

## Quickstart (all-in-one)

Run the full analysis + artifact generation in one step:

```bash
python analyze_qxdm_5g_ca.py PATH\\TO\\QXDM_LOG.txt --output-dir qxdm_analysis_output --window-seconds 1.0
```

Useful options:
- `--max-pdsch-blocks N` to stop early for a quick sample run
- `--json` to also print the JSON report to stdout

## Two-step workflow (cache then render)

1) Extract and cache analysis artifacts:

```bash
python extract_qxdm_5g_ca_data.py PATH\\TO\\QXDM_LOG.txt --output-dir qxdm_analysis_output --window-seconds 1.0
```

2) Render plots + dashboard from the cached `summary.json`:

```bash
python plot_qxdm_5g_ca.py --summary-json qxdm_analysis_output\\summary.json
```

(Optionally) choose where rendered artifacts go:

```bash
python plot_qxdm_5g_ca.py --summary-json qxdm_analysis_output\\summary.json --output-dir qxdm_analysis_output
```

## Output files

By default, outputs are written under `qxdm_analysis_output/`:
- `summary.json` (cached report)
- `window_metrics.csv`
- `carrier_window_metrics.csv`
- `research_summary.md`
- `research_dashboard.html`
- `focused_anomaly_report.md`
- `focused_anomaly_windows.json`
- Several `.svg` plots

## Slides PDF export (optional)

If you want to export the HTML slide deck to PDF, there is a small Node script:

```bash
node html_to_pdf.mjs [output.pdf]
```

Notes:
- The script uses `puppeteer-core` and launches Microsoft Edge via a hard-coded `executablePath`.
  If Edge is installed elsewhere (or you want Chrome), edit `html_to_pdf.mjs` accordingly.
- Install the dependency:

```bash
npm install puppeteer-core
```
