from __future__ import annotations

import argparse
from pathlib import Path

from analyze_qxdm_5g_ca import load_cached_report, print_artifact_report, print_carrier_topology, render_cached_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render QXDM NR5G CA plots and dashboard from cached analysis data.")
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path("qxdm_analysis_output") / "summary.json",
        help="Path to a cached summary.json file produced by the data extraction step.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for rendered plots and dashboard. Defaults to the summary.json parent directory.",
    )
    parser.add_argument(
        "--spike-inset-anchor-x",
        type=float,
        default=800.0,
        help="Place the spike zoom inset above this x-axis location in seconds.",
    )
    parser.add_argument(
        "--spike-selection",
        choices=["max", "typical", "target"],
        default="target",
        help="Choose either the largest spike or a representative local spike for the zoom region.",
    )
    parser.add_argument(
        "--spike-min-x",
        type=float,
        default=0.0,
        help="Only consider spikes at or after this x-axis location in seconds.",
    )
    parser.add_argument(
        "--spike-target-x",
        type=float,
        default=430.0,
        help="Target x-axis location whose nearest strong local peak should be zoomed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_path = args.summary_json
    output_dir = args.output_dir or summary_path.parent
    report = load_cached_report(summary_path)
    report = render_cached_artifacts(
        output_dir,
        report,
        inset_anchor_x=args.spike_inset_anchor_x,
        spike_selection_mode=args.spike_selection,
        spike_min_x=args.spike_min_x,
        spike_target_x=args.spike_target_x,
    )
    print_carrier_topology(report)
    print_artifact_report(report)


if __name__ == "__main__":
    main()