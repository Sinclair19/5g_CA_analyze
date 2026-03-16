from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyze_qxdm_5g_ca import Analyzer, print_artifact_report, print_text_report, save_data_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse a QXDM NR5G CA log and cache analysis data artifacts.")
    parser.add_argument("log_path", type=Path, help="Path to the QXDM text log.")
    parser.add_argument(
        "--max-pdsch-blocks",
        type=int,
        default=None,
        help="Stop after this many PDSCH blocks. Useful for a quick sample run.",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=1.0,
        help="Aggregation window size for cached metrics.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("qxdm_analysis_output"),
        help="Directory for generated JSON, CSV, and focused anomaly artifacts.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also print the cached JSON report to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyzer = Analyzer(window_seconds=args.window_seconds, max_pdsch_blocks=args.max_pdsch_blocks)
    report = analyzer.analyze(args.log_path)
    report = save_data_artifacts(args.output_dir, report)
    print_text_report(report)
    print_artifact_report(report)
    if args.json:
        print()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()