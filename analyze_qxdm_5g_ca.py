from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib import font_manager


TIMESTAMP_PATTERN = re.compile(
    r"^(?P<stamp>\d{4} \w{3} \d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+\[[^\]]+\]\s+0x[0-9A-F]+\s+(?P<name>.+)$"
)
KEY_VALUE_PATTERN = re.compile(r"^(?P<key>[^=]+?)\s*=\s*(?P<value>.+?)\s*$")
HEX_PATTERN = re.compile(r"0x[0-9A-Fa-f]+")
INT_PATTERN = re.compile(r"^-?\d+$")
FLOAT_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")


_ACADEMIC_RC = {
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica", "Liberation Sans"],
    "font.weight": "bold",
    "font.size": 16,
    "axes.titlesize": 16,
    "axes.labelsize": 16,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 14,
    "axes.prop_cycle": cycler(
        "color",
        [
            "#A6CEE3",
            "#1F78B4",
            "#B2DF8A",
            "#33A02C",
            "#FB9A99",
            "#E31A1C",
            "#FDBF6F",
            "#FF7F00",
            "#CAB2D6",
            "#6A3D9A",
            "#FFFF99",
            "#B15928",
        ],
    ),
    "lines.linewidth": 1.0,
    "lines.markersize": 12,
    "axes.linewidth": 1.5,
    "axes.edgecolor": "black",
    "axes.axisbelow": True,
    "xtick.major.width": 1.5,
    "xtick.major.size": 3,
    "ytick.major.width": 1.5,
    "ytick.major.size": 3,
    "xtick.minor.width": 1.0,
    "xtick.minor.size": 2,
    "ytick.minor.width": 1.0,
    "ytick.minor.size": 2,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.linewidth": 1.0,
    "grid.alpha": 0.6,
    "axes.grid.axis": "y",
    "legend.frameon": False,
    "legend.handlelength": 1.5,
    "legend.handletextpad": 0.4,
    "legend.columnspacing": 1.0,
    "hatch.linewidth": 0.5,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
}
matplotlib.rcParams.update(_ACADEMIC_RC)

BLUE_LT = "#A6CEE3"
BLUE_DK = "#1F78B4"
GREEN_LT = "#B2DF8A"
GREEN_DK = "#33A02C"
RED_LT = "#FB9A99"
RED_DK = "#E31A1C"
ORANGE_LT = "#FDBF6F"
ORANGE_DK = "#FF7F00"
PURPLE_LT = "#CAB2D6"
PURPLE_DK = "#6A3D9A"
YELLOW_LT = "#FFFF99"
BROWN_DK = "#B15928"
PAIRED = [
    BLUE_LT,
    BLUE_DK,
    GREEN_LT,
    GREEN_DK,
    RED_LT,
    RED_DK,
    ORANGE_LT,
    ORANGE_DK,
    PURPLE_LT,
    PURPLE_DK,
    YELLOW_LT,
    BROWN_DK,
]
MARKERS = ["s", "D", "^", "d", "o", "v", "P", "X"]
LINESTYLES = ["-", "--", "-.", ":", "-", "--", "-.", ":"]

fp_path = font_manager.findfont(font_manager.FontProperties(family="Arial"))
fp = font_manager.FontProperties(fname=fp_path, weight="bold", size=16)
SCATTER_CMAP = matplotlib.colormaps["viridis"]


@dataclass
class PdschSnapshot:
    timestamp: datetime
    carrier_id: int
    elapsed_slots: int
    num_pdsch_decode: int
    num_crc_pass_tb: int
    num_crc_fail_tb: int
    num_retx: int
    ack_as_nack: int
    harq_failure: int
    crc_pass_tb_bytes: int
    crc_fail_tb_bytes: int
    tb_bytes: int
    padding_bytes: int
    retx_bytes: int
    bler: float | None


@dataclass
class UlSnapshot:
    timestamp: datetime
    tb_new_tx_bytes: int
    tb_retx_bytes: int
    num_mcs: int
    num_prb: int
    phr: int
    num_new_tx_tb: int
    num_retx_tb: int
    ri: int
    cqi: int
    num_phr: int
    tpc_accum: int
    num_ulsch_sched: int
    num_no_ulsch_sched: int


@dataclass
class WindowAccumulator:
    pdsch_intervals: int = 0
    active_intervals: int = 0
    pdsch_time_seconds: float = 0.0
    configured_ca_max: int = 0
    active_carriers_sum: int = 0
    pass_bytes: int = 0
    fail_bytes: int = 0
    tb_bytes: int = 0
    retx_bytes: int = 0
    padding_bytes: int = 0
    pass_tb: int = 0
    fail_tb: int = 0
    pdsch_decode: int = 0
    ack_as_nack: int = 0
    harq_failure: int = 0
    carrier_pass_bytes: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    carrier_tb_bytes: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    carrier_retx_bytes: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    symbol_slots: int = 0
    symbol_dl_total: int = 0
    symbol_eval_total: int = 0
    symbol_ul_available_total: int = 0
    symbol_ul_committed_total: int = 0
    symbol_guard_total: int = 0
    symbol_ssb_total: int = 0
    symbol_no_dl_slots: int = 0
    ul_intervals: int = 0
    ul_new_tx_bytes: int = 0
    ul_retx_bytes: int = 0
    ul_new_tx_tb: int = 0
    ul_retx_tb: int = 0
    ul_sched: int = 0
    ul_no_sched: int = 0
    ul_num_prb: int = 0
    ul_cqi: int = 0
    ul_ri: int = 0
    ul_phr: int = 0
    ul_num_phr: int = 0


def is_pdsch_placeholder(snapshot: PdschSnapshot) -> bool:
    return (
        snapshot.elapsed_slots == 0
        and snapshot.num_pdsch_decode == 0
        and snapshot.num_crc_pass_tb == 0
        and snapshot.num_crc_fail_tb == 0
        and snapshot.num_retx == 0
        and snapshot.ack_as_nack == 0
        and snapshot.harq_failure == 0
        and snapshot.crc_pass_tb_bytes == 0
        and snapshot.crc_fail_tb_bytes == 0
        and snapshot.tb_bytes == 0
        and snapshot.padding_bytes == 0
        and snapshot.retx_bytes == 0
        and snapshot.bler is None
    )


def has_unreasonable_elapsed_jump(
    previous: PdschSnapshot,
    snapshot: PdschSnapshot,
    interval_seconds: float | None,
) -> bool:
    elapsed_delta = snapshot.elapsed_slots - previous.elapsed_slots
    if elapsed_delta <= 0 or interval_seconds is None or interval_seconds <= 0:
        return False
    max_reasonable_slots = max(1000, int(math.ceil(interval_seconds * 20000)))
    return elapsed_delta > max_reasonable_slots


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream and analyze large QXDM NR5G CA logs.")
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
        help="Aggregation window size for CSV and plots.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("qxdm_analysis_output"),
        help="Directory for generated CSV, JSON, markdown, and plots.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also print the JSON report to stdout.",
    )
    return parser.parse_args()


def parse_timestamp(line: str) -> tuple[datetime | None, str | None]:
    match = TIMESTAMP_PATTERN.match(line.rstrip("\n"))
    if not match:
        return None, None
    stamp = datetime.strptime(match.group("stamp"), "%Y %b %d  %H:%M:%S.%f")
    return stamp, match.group("name").strip()


def parse_scalar(value: str) -> int | float | str | None:
    cleaned = value.strip()
    if not cleaned or cleaned == "NA":
        return None if cleaned != "NA" else "NA"
    compact = cleaned.replace(" ", "")
    if HEX_PATTERN.fullmatch(compact):
        return compact
    if INT_PATTERN.fullmatch(compact):
        return int(compact)
    if FLOAT_PATTERN.fullmatch(compact):
        return float(compact)
    return cleaned


def popcount_hex(value: str | None) -> int:
    if not value or value == "NA":
        return 0
    if isinstance(value, str) and HEX_PATTERN.fullmatch(value):
        return int(value, 16).bit_count()
    return 0


def to_number(value: int | float | str | None) -> float | int | None:
    if isinstance(value, (int, float)):
        return value
    return None


def safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    sum_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    sum_x2 = sum((x - mean_x) ** 2 for x in xs)
    sum_y2 = sum((y - mean_y) ** 2 for y in ys)
    denominator = math.sqrt(sum_x2 * sum_y2)
    if denominator == 0:
        return None
    return sum_xy / denominator


def format_ratio(value: float | None, multiplier: float = 100.0) -> str:
    if value is None:
        return "n/a"
    return f"{value * multiplier:.2f}%"


def format_number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    if math.isfinite(value):
        return f"{value:,.{digits}f}"
    return "n/a"


def format_bytes_gb(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) / (1024 ** 3):.3f} GiB"


def style_ax(ax, _fp=None, enforce: bool = False) -> None:
    _fp = _fp or fp
    rc = _ACADEMIC_RC

    ax.xaxis.label.set_fontproperties(_fp)
    ax.yaxis.label.set_fontproperties(_fp)
    ax.title.set_fontproperties(_fp)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(_fp)
    legend = ax.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontproperties(_fp)

    if not enforce:
        return

    for spine in ax.spines.values():
        spine.set_linewidth(rc["axes.linewidth"])
        spine.set_edgecolor(rc["axes.edgecolor"])

    ax.tick_params(
        axis="both",
        which="major",
        direction=rc["xtick.direction"],
        width=rc["xtick.major.width"],
        length=rc["xtick.major.size"],
        labelsize=rc["xtick.labelsize"],
    )
    ax.tick_params(
        axis="both",
        which="minor",
        direction=rc["xtick.direction"],
        width=rc["xtick.minor.width"],
        length=rc["xtick.minor.size"],
    )

    ax.set_axisbelow(rc["axes.axisbelow"])
    grid_axis = rc["axes.grid.axis"]
    grid_kw = {
        "linestyle": rc["grid.linestyle"],
        "linewidth": rc["grid.linewidth"],
        "alpha": rc["grid.alpha"],
    }
    if grid_axis in ("x", "both"):
        ax.xaxis.grid(True, **grid_kw)
    else:
        ax.xaxis.grid(False)
    if grid_axis in ("y", "both"):
        ax.yaxis.grid(True, **grid_kw)
    else:
        ax.yaxis.grid(False)

    for line in ax.get_lines():
        line.set_linewidth(rc["lines.linewidth"])
        line.set_markersize(rc["lines.markersize"])


def style_fig(
    fig,
    _fp=None,
    legend_ncol: int | None = None,
    legend_level: str = "fig",
    legend_loc: str = "top",
    enforce: bool = False,
    **legend_kw,
) -> None:
    _fp = _fp or fp
    if enforce:
        matplotlib.rcParams.update(_ACADEMIC_RC)
    for ax in fig.get_axes():
        style_ax(ax, _fp, enforce=enforce)

    if legend_ncol is None:
        for legend in fig.legends:
            for text in legend.get_texts():
                text.set_fontproperties(_fp)
        return

    if legend_level == "fig":
        seen: dict[str, object] = {}
        for ax in fig.get_axes():
            handles, labels = ax.get_legend_handles_labels()
            for handle, label in zip(handles, labels):
                if label and label not in seen:
                    seen[label] = handle
        for ax in fig.get_axes():
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
        if seen:
            if legend_loc == "top":
                kw = {
                    "ncol": legend_ncol,
                    "frameon": False,
                    "prop": _fp,
                    "loc": "upper center",
                    "bbox_to_anchor": (0.5, 0.955),
                }
            else:
                kw = {"ncol": legend_ncol, "frameon": False, "prop": _fp, "loc": legend_loc}
            kw.update(legend_kw)
            fig.legend(list(seen.values()), list(seen.keys()), **kw)
    elif legend_level == "ax":
        for ax in fig.get_axes():
            handles, labels = ax.get_legend_handles_labels()
            if not handles:
                continue
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
            if legend_loc == "top":
                kw = {
                    "ncol": legend_ncol,
                    "frameon": False,
                    "prop": _fp,
                    "loc": "lower center",
                    "bbox_to_anchor": (0.5, 1.0),
                }
            else:
                kw = {"ncol": legend_ncol, "frameon": False, "prop": _fp, "loc": legend_loc}
            kw.update(legend_kw)
            ax.legend(handles, labels, **kw)


def _finalize_plot(fig, axes, x_label: str, legend_columns: int | None = None) -> None:
    if hasattr(axes, "flat"):
        axes = list(axes.flat)
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]
    for axis in axes:
        style_ax(axis, enforce=True)
    if x_label and axes:
        axes[-1].set_xlabel(x_label, fontproperties=fp)
    style_fig(fig, legend_ncol=legend_columns, enforce=True)


def _safe_series_max(values: list[float]) -> float:
    maximum = max(values, default=0.0)
    return maximum if maximum > 0 else 1.0


def select_spike_index(
    x_values: list[float],
    aggregate_values: list[float],
    selection_mode: str = "max",
    min_x: float = 0.0,
    target_x: float | None = None,
    target_peak_fraction: float = 0.5,
) -> int:
    if not x_values or not aggregate_values:
        return 0

    candidate_indices = [
        index for index, x_value in enumerate(x_values) if x_value >= min_x and aggregate_values[index] > 0
    ]
    if not candidate_indices:
        candidate_indices = [index for index, value in enumerate(aggregate_values) if value > 0]
    if not candidate_indices:
        return 0

    if selection_mode == "max":
        return max(candidate_indices, key=lambda index: aggregate_values[index])

    peak_indices: list[int] = []
    for index in candidate_indices:
        left_value = aggregate_values[index - 1] if index > 0 else float("-inf")
        right_value = aggregate_values[index + 1] if index + 1 < len(aggregate_values) else float("-inf")
        current_value = aggregate_values[index]
        if current_value >= left_value and current_value >= right_value:
            peak_indices.append(index)

    if not peak_indices:
        peak_indices = candidate_indices

    if selection_mode == "target" and target_x is not None:
        peak_threshold = max(aggregate_values[index] for index in peak_indices) * target_peak_fraction
        strong_peaks = [index for index in peak_indices if aggregate_values[index] >= peak_threshold]
        if strong_peaks:
            peak_indices = strong_peaks
        return min(
            peak_indices,
            key=lambda index: (abs(x_values[index] - target_x), -aggregate_values[index]),
        )

    sorted_peaks = sorted((aggregate_values[index], index) for index in peak_indices)
    median_position = len(sorted_peaks) // 2
    return sorted_peaks[median_position][1]


def classify_window(row: dict[str, object]) -> str:
    throughput = float(row.get("throughput_mibps") or 0.0)
    bler = row.get("bler")
    active_only_ca = row.get("ca_utilization_ratio_active_only")
    dominant_share = row.get("dominant_carrier_share")

    if throughput < 0.5:
        return "idle_or_control"
    if bler is not None and float(bler) >= 0.30:
        return "rf_or_decode_failure"
    if active_only_ca is not None and dominant_share is not None:
        active_only_ca_value = float(active_only_ca)
        dominant_share_value = float(dominant_share)
        if active_only_ca_value >= 0.67 and dominant_share_value <= 0.60:
            return "balanced_ca"
        if active_only_ca_value < 0.50 and dominant_share_value >= 0.80:
            return "single_carrier_dominant"
        if active_only_ca_value >= 0.67 and dominant_share_value > 0.60:
            return "ca_active_but_skewed"
        if active_only_ca_value < 0.50:
            return "underutilized_ca"
    if throughput < 10.0:
        return "light_traffic"
    return "mixed_load"


def _parse_configured_carrier_slice(text_slice: str, role: str) -> dict[str, object] | None:
    ssb_match = re.search(r"absoluteFrequencySSB\s+(\d+)", text_slice)
    band_match = re.search(r"frequencyBandList\s*\{\s*(\d+)\s*\}", text_slice)
    scs_bw_match = re.search(
        r"scs-SpecificCarrierList\s*\{\s*\{\s*offsetToCarrier\s+\d+,\s*subcarrierSpacing\s+kHz(\d+),\s*carrierBandwidth\s+(\d+)",
        text_slice,
        re.DOTALL,
    )
    phys_cell_match = re.search(r"physCellId\s+(\d+)", text_slice)
    if not ssb_match or not band_match:
        return None
    scs_khz = int(scs_bw_match.group(1)) if scs_bw_match else None
    carrier_bandwidth = int(scs_bw_match.group(2)) if scs_bw_match else None
    return {
        "role": role,
        "cell_type": "PCell" if role == "PCell" else "SCell",
        "ssb_arfcn": int(ssb_match.group(1)),
        "band": int(band_match.group(1)),
        "scs_khz": scs_khz,
        "carrier_bandwidth_rbs": carrier_bandwidth,
        "physical_cell_id": int(phys_cell_match.group(1)) if phys_cell_match else None,
    }


def infer_carrier_topology(report: dict[str, object], focused_snippets: list[dict[str, object]]) -> dict[str, object]:
    configured_cells_by_arfcn: dict[int, dict[str, object]] = {}
    observed_earfcns: dict[int, Counter[int]] = defaultdict(Counter)

    for snippet in focused_snippets:
        for entry in snippet.get("entries", []):
            text = str(entry.get("text") or "")
            section_name = str(entry.get("section_name") or "")
            if not text:
                continue

            spcell_index = text.find("spCellConfig")
            if spcell_index != -1:
                parsed = _parse_configured_carrier_slice(text[spcell_index : spcell_index + 5000], "PCell")
                if parsed is not None:
                    configured_cells_by_arfcn.setdefault(int(parsed["ssb_arfcn"]), parsed)

            scell_start = 0
            while True:
                scell_index = text.find("sCellIndex", scell_start)
                if scell_index == -1:
                    break
                parsed = _parse_configured_carrier_slice(text[scell_index : scell_index + 5000], f"SCell {len([cell for cell in configured_cells_by_arfcn.values() if str(cell.get('cell_type')) == 'SCell']) + 1}")
                if parsed is not None:
                    configured_cells_by_arfcn.setdefault(int(parsed["ssb_arfcn"]), parsed)
                scell_start = scell_index + len("sCellIndex")

            if "NR5G MAC PDSCH Status" not in section_name and "NR5G MAC DL TB Report" not in section_name:
                continue
            for line in text.splitlines():
                if not line.lstrip().startswith("|"):
                    continue
                columns = [column.strip() for column in line.strip().split("|")[1:-1]]
                if len(columns) < 14 or columns[0] == "#":
                    continue
                if not columns[13].isdigit():
                    continue
                try:
                    carrier_id = int(columns[5])
                    earfcn = int(columns[13])
                except ValueError:
                    continue
                observed_earfcns[carrier_id][earfcn] += 1

    configured_cells = sorted(configured_cells_by_arfcn.values(), key=lambda cell: (0 if cell["cell_type"] == "PCell" else 1, int(cell["ssb_arfcn"])))
    mapped_cells: list[dict[str, object]] = []
    used_carrier_ids: set[int] = set()
    used_arfcns: set[int] = set()

    for carrier_id, counts in sorted(observed_earfcns.items()):
        ssb_arfcn, observation_count = counts.most_common(1)[0]
        configured_cell = configured_cells_by_arfcn.get(ssb_arfcn)
        if configured_cell is None:
            continue
        mapped_cells.append(
            {
                **configured_cell,
                "analyzer_carrier_id": carrier_id,
                "mapping_confidence": "direct_observed",
                "observation_count": observation_count,
            }
        )
        used_carrier_ids.add(carrier_id)
        used_arfcns.add(ssb_arfcn)

    carrier_ids = sorted(int(summary["carrier_id"]) for summary in report.get("pdsch", {}).get("carrier_summaries", []))
    remaining_carrier_ids = [carrier_id for carrier_id in carrier_ids if carrier_id not in used_carrier_ids]
    remaining_cells = [cell for cell in configured_cells if int(cell["ssb_arfcn"]) not in used_arfcns]
    if len(remaining_carrier_ids) == 1 and len(remaining_cells) == 1:
        mapped_cells.append(
            {
                **remaining_cells[0],
                "analyzer_carrier_id": remaining_carrier_ids[0],
                "mapping_confidence": "inferred_from_remaining_config",
                "observation_count": 0,
            }
        )
        used_carrier_ids.add(remaining_carrier_ids[0])
        used_arfcns.add(int(remaining_cells[0]["ssb_arfcn"]))

    mapped_cells.sort(key=lambda cell: int(cell.get("analyzer_carrier_id", 999)))
    unresolved_carrier_ids = [carrier_id for carrier_id in carrier_ids if carrier_id not in used_carrier_ids]
    unmapped_configured_cells = [cell for cell in configured_cells if int(cell["ssb_arfcn"]) not in used_arfcns]

    return {
        "configured_cells": configured_cells,
        "mapped_cells": mapped_cells,
        "unresolved_analyzer_carrier_ids": unresolved_carrier_ids,
        "unmapped_configured_cells": unmapped_configured_cells,
    }


def format_carrier_role(cell: dict[str, object]) -> str:
    role = str(cell.get("role") or cell.get("cell_type") or "Unknown")
    cell_type = str(cell.get("cell_type") or "")
    if not cell_type:
        return role
    if role.lower() == cell_type.lower() or role.lower().startswith(cell_type.lower()):
        return role
    return f"{cell_type} {role}"


def parse_focused_markdown_entries(markdown_text: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    lines = markdown_text.splitlines()
    line_count = len(lines)
    index = 0
    while index < line_count:
        line = lines[index]
        if not line.startswith("### "):
            index += 1
            continue
        header = line[4:].strip()
        index += 1
        while index < line_count and lines[index].strip() != "```text":
            index += 1
        if index >= line_count:
            break
        index += 1
        block_lines: list[str] = []
        while index < line_count and lines[index].strip() != "```":
            block_lines.append(lines[index])
            index += 1
        entries.append({"section_name": header, "text": "\n".join(block_lines)})
        index += 1
    return entries


def print_carrier_topology(report: dict[str, object]) -> None:
    topology = report.get("carrier_topology", {})
    mapped_cells = topology.get("mapped_cells", [])
    if not mapped_cells:
        return

    print()
    print("Carrier topology")
    for cell in mapped_cells:
        confidence = str(cell.get("mapping_confidence") or "")
        confidence_text = "direct" if confidence == "direct_observed" else "inferred"
        print(
            f"  Carrier {cell['analyzer_carrier_id']}: {format_carrier_role(cell)}, n{cell['band']}, SSB ARFCN {cell['ssb_arfcn']} ({confidence_text})"
        )


def iterate_log_entries(log_path: Path) -> Iterator[tuple[datetime, str, str]]:
    current_timestamp: datetime | None = None
    current_section: str | None = None
    current_lines: list[str] = []

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            timestamp, section_name = parse_timestamp(line)
            if timestamp is not None and section_name is not None:
                if current_timestamp is not None and current_section is not None:
                    yield current_timestamp, current_section, "".join(current_lines)
                current_timestamp = timestamp
                current_section = section_name
                current_lines = [line]
                continue
            if current_timestamp is not None:
                current_lines.append(line)

    if current_timestamp is not None and current_section is not None:
        yield current_timestamp, current_section, "".join(current_lines)


class Analyzer:
    def __init__(self, window_seconds: float, max_pdsch_blocks: int | None = None) -> None:
        self.window_seconds = window_seconds
        self.max_pdsch_blocks = max_pdsch_blocks
        self.base_timestamp: datetime | None = None
        self.first_timestamp: datetime | None = None
        self.last_timestamp: datetime | None = None
        self.last_pdsch_block_timestamp: datetime | None = None
        self.pdsch_blocks_seen = 0
        self.pdsch_prev: dict[int, PdschSnapshot] = {}
        self.pdsch_reset_count = 0
        self.pdsch_valid_intervals = 0
        self.pdsch_total_configured_ca = 0
        self.active_carrier_histogram: Counter[int] = Counter()
        self.carrier_totals: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.ul_prev: UlSnapshot | None = None
        self.ul_intervals = 0
        self.ul_reset_count = 0
        self.ul_totals: dict[str, float] = defaultdict(float)
        self.symbol_slots = 0
        self.symbol_dl_total = 0
        self.symbol_eval_total = 0
        self.symbol_ul_available_total = 0
        self.symbol_ul_committed_total = 0
        self.symbol_guard_total = 0
        self.symbol_ssb_total = 0
        self.symbol_no_dl_slots = 0
        self.windows: dict[int, WindowAccumulator] = defaultdict(WindowAccumulator)
        self.all_carrier_ids: set[int] = set()

    def analyze(self, log_path: Path) -> dict[str, object]:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            iterator = iter(handle)
            for line in iterator:
                timestamp, section_name = parse_timestamp(line)
                if timestamp is None or section_name is None:
                    continue
                if self.base_timestamp is None:
                    self.base_timestamp = timestamp
                if self.first_timestamp is None:
                    self.first_timestamp = timestamp
                self.last_timestamp = timestamp

                if section_name == "NR5G MAC PDSCH Stats":
                    self._parse_pdsch_block(iterator, timestamp)
                    if self.max_pdsch_blocks is not None and self.pdsch_blocks_seen >= self.max_pdsch_blocks:
                        break
                elif section_name == "NR5G MAC UL TB Stats":
                    self._parse_ul_tb_block(iterator, timestamp)
                elif section_name == "NR5G MAC Symbol Arbitration":
                    self._parse_symbol_block(iterator, timestamp)

        report = self._build_report(log_path)
        report["window_metrics"] = self._build_window_rows()
        report["carrier_window_metrics"] = self._build_carrier_window_rows()
        report["research"] = self._build_research_findings(report["window_metrics"])
        return report

    def _window_index(self, timestamp: datetime) -> int:
        if self.base_timestamp is None:
            self.base_timestamp = timestamp
        delta_seconds = (timestamp - self.base_timestamp).total_seconds()
        return int(delta_seconds // self.window_seconds)

    def _window_bounds(self, window_index: int) -> tuple[datetime, datetime]:
        assert self.base_timestamp is not None
        start = self.base_timestamp + timedelta(seconds=window_index * self.window_seconds)
        end = start + timedelta(seconds=self.window_seconds)
        return start, end

    def _parse_pdsch_block(self, iterator: Iterator[str], timestamp: datetime) -> None:
        header_values: dict[str, int | float | str | None] = {}
        rows: list[PdschSnapshot] = []

        for line in iterator:
            stripped = line.strip()
            if not stripped:
                if rows:
                    break
                continue

            key_value = KEY_VALUE_PATTERN.match(line)
            if key_value:
                key = key_value.group("key").strip()
                header_values[key] = parse_scalar(key_value.group("value"))
                continue

            if "Carrier ID" in line or line.startswith("---"):
                continue

            if not line.lstrip().startswith("|"):
                if rows:
                    break
                continue

            columns = [column.strip() for column in line.strip().split("|")[1:-1]]
            if len(columns) < 15 or columns[0] == "#":
                continue

            try:
                snapshot = PdschSnapshot(
                    timestamp=timestamp,
                    carrier_id=int(columns[1]),
                    elapsed_slots=int(columns[2]),
                    num_pdsch_decode=int(columns[3]),
                    num_crc_pass_tb=int(columns[4]),
                    num_crc_fail_tb=int(columns[5]),
                    num_retx=int(columns[6]),
                    ack_as_nack=int(columns[7]),
                    harq_failure=int(columns[8]),
                    crc_pass_tb_bytes=int(columns[9]),
                    crc_fail_tb_bytes=int(columns[10]),
                    tb_bytes=int(columns[11]),
                    padding_bytes=int(columns[12]),
                    retx_bytes=int(columns[13]),
                    bler=None if columns[14] == "NA" else float(columns[14]),
                )
            except ValueError:
                continue
            rows.append(snapshot)

        self.pdsch_blocks_seen += 1
        configured_ca = int(to_number(header_values.get("Num CA")) or 0)
        self.pdsch_total_configured_ca = max(self.pdsch_total_configured_ca, configured_ca)
        self._update_pdsch_totals(rows, configured_ca, timestamp)
        self.last_pdsch_block_timestamp = timestamp

    def _update_pdsch_totals(self, rows: Iterable[PdschSnapshot], configured_ca: int, timestamp: datetime) -> None:
        active_carriers = 0
        valid_delta_seen = False
        interval_seconds = None if self.last_pdsch_block_timestamp is None else (timestamp - self.last_pdsch_block_timestamp).total_seconds()
        interval_totals = defaultdict(int)
        carrier_interval_totals: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for snapshot in rows:
            self.all_carrier_ids.add(snapshot.carrier_id)
            if is_pdsch_placeholder(snapshot):
                continue
            previous = self.pdsch_prev.get(snapshot.carrier_id)
            self.pdsch_prev[snapshot.carrier_id] = snapshot
            if previous is None:
                continue

            numeric_pairs = {
                "elapsed_slots": snapshot.elapsed_slots - previous.elapsed_slots,
                "num_pdsch_decode": snapshot.num_pdsch_decode - previous.num_pdsch_decode,
                "num_crc_pass_tb": snapshot.num_crc_pass_tb - previous.num_crc_pass_tb,
                "num_crc_fail_tb": snapshot.num_crc_fail_tb - previous.num_crc_fail_tb,
                "num_retx": snapshot.num_retx - previous.num_retx,
                "ack_as_nack": snapshot.ack_as_nack - previous.ack_as_nack,
                "harq_failure": snapshot.harq_failure - previous.harq_failure,
                "crc_pass_tb_bytes": snapshot.crc_pass_tb_bytes - previous.crc_pass_tb_bytes,
                "crc_fail_tb_bytes": snapshot.crc_fail_tb_bytes - previous.crc_fail_tb_bytes,
                "tb_bytes": snapshot.tb_bytes - previous.tb_bytes,
                "padding_bytes": snapshot.padding_bytes - previous.padding_bytes,
                "retx_bytes": snapshot.retx_bytes - previous.retx_bytes,
            }

            if any(delta < 0 for delta in numeric_pairs.values()):
                self.pdsch_reset_count += 1
                continue

            if has_unreasonable_elapsed_jump(previous, snapshot, interval_seconds):
                self.pdsch_reset_count += 1
                continue

            valid_delta_seen = True
            if numeric_pairs["tb_bytes"] > 0 or numeric_pairs["num_pdsch_decode"] > 0:
                active_carriers += 1

            carrier_total = self.carrier_totals[snapshot.carrier_id]
            for key, delta in numeric_pairs.items():
                carrier_total[key] += delta
                interval_totals[key] += delta
                carrier_interval_totals[snapshot.carrier_id][key] += delta

        if not valid_delta_seen:
            return

        self.pdsch_valid_intervals += 1
        if configured_ca > 0:
            self.active_carrier_histogram[active_carriers] += 1

        window = self.windows[self._window_index(timestamp)]
        window.pdsch_intervals += 1
        if interval_seconds is not None and interval_seconds > 0:
            window.pdsch_time_seconds += interval_seconds
        window.configured_ca_max = max(window.configured_ca_max, configured_ca)
        window.active_carriers_sum += active_carriers
        if active_carriers > 0:
            window.active_intervals += 1
        window.pass_bytes += interval_totals["crc_pass_tb_bytes"]
        window.fail_bytes += interval_totals["crc_fail_tb_bytes"]
        window.tb_bytes += interval_totals["tb_bytes"]
        window.retx_bytes += interval_totals["retx_bytes"]
        window.padding_bytes += interval_totals["padding_bytes"]
        window.pass_tb += interval_totals["num_crc_pass_tb"]
        window.fail_tb += interval_totals["num_crc_fail_tb"]
        window.pdsch_decode += interval_totals["num_pdsch_decode"]
        window.ack_as_nack += interval_totals["ack_as_nack"]
        window.harq_failure += interval_totals["harq_failure"]

        for carrier_id, carrier_metrics in carrier_interval_totals.items():
            window.carrier_pass_bytes[carrier_id] += carrier_metrics["crc_pass_tb_bytes"]
            window.carrier_tb_bytes[carrier_id] += carrier_metrics["tb_bytes"]
            window.carrier_retx_bytes[carrier_id] += carrier_metrics["retx_bytes"]

    def _parse_ul_tb_block(self, iterator: Iterator[str], timestamp: datetime) -> None:
        values: dict[str, int | float | str | None] = {}

        for line in iterator:
            stripped = line.strip()
            if not stripped:
                if values:
                    break
                continue

            key_value = KEY_VALUE_PATTERN.match(line)
            if not key_value:
                if values:
                    break
                continue

            key = key_value.group("key").strip()
            values[key] = parse_scalar(key_value.group("value"))

        required_keys = [
            "TB New Tx Bytes",
            "TB ReTx Bytes",
            "Num MCS",
            "Num PRB",
            "PHR",
            "Num New TX TB",
            "Num ReTx TB",
            "RI",
            "CQI",
            "Num PHR",
            "TPC Accum",
            "Num ULSCH Sched",
            "Num No ULSCH Sched",
        ]
        if any(key not in values for key in required_keys):
            return

        snapshot = UlSnapshot(
            timestamp=timestamp,
            tb_new_tx_bytes=int(to_number(values["TB New Tx Bytes"]) or 0),
            tb_retx_bytes=int(to_number(values["TB ReTx Bytes"]) or 0),
            num_mcs=int(to_number(values["Num MCS"]) or 0),
            num_prb=int(to_number(values["Num PRB"]) or 0),
            phr=int(to_number(values["PHR"]) or 0),
            num_new_tx_tb=int(to_number(values["Num New TX TB"]) or 0),
            num_retx_tb=int(to_number(values["Num ReTx TB"]) or 0),
            ri=int(to_number(values["RI"]) or 0),
            cqi=int(to_number(values["CQI"]) or 0),
            num_phr=int(to_number(values["Num PHR"]) or 0),
            tpc_accum=int(to_number(values["TPC Accum"]) or 0),
            num_ulsch_sched=int(to_number(values["Num ULSCH Sched"]) or 0),
            num_no_ulsch_sched=int(to_number(values["Num No ULSCH Sched"]) or 0),
        )

        previous = self.ul_prev
        self.ul_prev = snapshot
        if previous is None:
            return

        deltas = {
            "tb_new_tx_bytes": snapshot.tb_new_tx_bytes - previous.tb_new_tx_bytes,
            "tb_retx_bytes": snapshot.tb_retx_bytes - previous.tb_retx_bytes,
            "num_mcs": snapshot.num_mcs - previous.num_mcs,
            "num_prb": snapshot.num_prb - previous.num_prb,
            "phr": snapshot.phr - previous.phr,
            "num_new_tx_tb": snapshot.num_new_tx_tb - previous.num_new_tx_tb,
            "num_retx_tb": snapshot.num_retx_tb - previous.num_retx_tb,
            "ri": snapshot.ri - previous.ri,
            "cqi": snapshot.cqi - previous.cqi,
            "num_phr": snapshot.num_phr - previous.num_phr,
            "tpc_accum": snapshot.tpc_accum - previous.tpc_accum,
            "num_ulsch_sched": snapshot.num_ulsch_sched - previous.num_ulsch_sched,
            "num_no_ulsch_sched": snapshot.num_no_ulsch_sched - previous.num_no_ulsch_sched,
        }

        if any(delta < 0 for delta in deltas.values()):
            self.ul_reset_count += 1
            return

        self.ul_intervals += 1
        for key, delta in deltas.items():
            self.ul_totals[key] += delta

        window = self.windows[self._window_index(timestamp)]
        window.ul_intervals += 1
        window.ul_new_tx_bytes += deltas["tb_new_tx_bytes"]
        window.ul_retx_bytes += deltas["tb_retx_bytes"]
        window.ul_new_tx_tb += deltas["num_new_tx_tb"]
        window.ul_retx_tb += deltas["num_retx_tb"]
        window.ul_sched += deltas["num_ulsch_sched"]
        window.ul_no_sched += deltas["num_no_ulsch_sched"]
        window.ul_num_prb += deltas["num_prb"]
        window.ul_cqi += deltas["cqi"]
        window.ul_ri += deltas["ri"]
        window.ul_phr += deltas["phr"]
        window.ul_num_phr += deltas["num_phr"]

    def _parse_symbol_block(self, iterator: Iterator[str], timestamp: datetime) -> None:
        groups: list[list[str]] = []
        current_group: list[str] = []
        in_records = False

        for line in iterator:
            stripped = line.strip()
            if not stripped:
                if current_group:
                    groups.append(current_group)
                break

            if stripped == "Records":
                in_records = True
                continue

            if not in_records or stripped.startswith("---") or "VSTMR (Ts)" in stripped:
                continue

            if not line.lstrip().startswith("|"):
                if current_group:
                    groups.append(current_group)
                break

            columns = [column.strip() for column in line.strip().split("|")[1:-1]]
            if len(columns) < 19 or columns[0] == "#":
                continue

            if columns[0]:
                if current_group:
                    groups.append(current_group)
                current_group = [line]
            elif current_group:
                current_group.append(line)

        window = self.windows[self._window_index(timestamp)]
        for group in groups:
            last_line = group[-1]
            columns = [column.strip() for column in last_line.strip().split("|")[1:-1]]
            if len(columns) < 19:
                continue
            num_symbol_eval = int(columns[8]) if columns[8].isdigit() else 0
            ul_available = popcount_hex(columns[9] or None)
            dl_aggregated = popcount_hex(columns[12] or None)
            guard = popcount_hex(columns[13] or None)
            ul_committed = popcount_hex(columns[14] or None)
            ssb_aggregated = popcount_hex(columns[18] or None)

            self.symbol_slots += 1
            self.symbol_eval_total += num_symbol_eval
            self.symbol_ul_available_total += ul_available
            self.symbol_dl_total += dl_aggregated
            self.symbol_guard_total += guard
            self.symbol_ul_committed_total += ul_committed
            self.symbol_ssb_total += ssb_aggregated
            if dl_aggregated == 0:
                self.symbol_no_dl_slots += 1

            window.symbol_slots += 1
            window.symbol_eval_total += num_symbol_eval
            window.symbol_ul_available_total += ul_available
            window.symbol_dl_total += dl_aggregated
            window.symbol_guard_total += guard
            window.symbol_ul_committed_total += ul_committed
            window.symbol_ssb_total += ssb_aggregated
            if dl_aggregated == 0:
                window.symbol_no_dl_slots += 1

    def _build_report(self, log_path: Path) -> dict[str, object]:
        total_pass_bytes = sum(total["crc_pass_tb_bytes"] for total in self.carrier_totals.values())
        total_fail_bytes = sum(total["crc_fail_tb_bytes"] for total in self.carrier_totals.values())
        total_tb_bytes = sum(total["tb_bytes"] for total in self.carrier_totals.values())
        total_retx_bytes = sum(total["retx_bytes"] for total in self.carrier_totals.values())
        total_padding_bytes = sum(total["padding_bytes"] for total in self.carrier_totals.values())
        total_pass_tb = sum(total["num_crc_pass_tb"] for total in self.carrier_totals.values())
        total_fail_tb = sum(total["num_crc_fail_tb"] for total in self.carrier_totals.values())
        total_decodes = sum(total["num_pdsch_decode"] for total in self.carrier_totals.values())
        total_active_carriers = sum(count * freq for count, freq in self.active_carrier_histogram.items())
        total_intervals = sum(self.active_carrier_histogram.values())
        active_only_intervals = sum(freq for count, freq in self.active_carrier_histogram.items() if count > 0)
        active_only_carriers = sum(count * freq for count, freq in self.active_carrier_histogram.items() if count > 0)

        carrier_summaries = []
        for carrier_id in sorted(self.carrier_totals):
            totals = self.carrier_totals[carrier_id]
            carrier_summaries.append(
                {
                    "carrier_id": carrier_id,
                    "pass_bytes": int(totals["crc_pass_tb_bytes"]),
                    "fail_bytes": int(totals["crc_fail_tb_bytes"]),
                    "tb_bytes": int(totals["tb_bytes"]),
                    "retx_bytes": int(totals["retx_bytes"]),
                    "padding_bytes": int(totals["padding_bytes"]),
                    "pass_tb": int(totals["num_crc_pass_tb"]),
                    "fail_tb": int(totals["num_crc_fail_tb"]),
                    "pdsch_decode": int(totals["num_pdsch_decode"]),
                    "goodput_share": safe_divide(totals["crc_pass_tb_bytes"], total_pass_bytes),
                    "tb_bler": safe_divide(totals["num_crc_fail_tb"], totals["num_crc_pass_tb"] + totals["num_crc_fail_tb"]),
                    "retx_overhead": safe_divide(totals["retx_bytes"], totals["tb_bytes"]),
                    "padding_overhead": safe_divide(totals["padding_bytes"], totals["tb_bytes"]),
                }
            )

        duration_seconds = None
        if self.first_timestamp and self.last_timestamp:
            duration_seconds = (self.last_timestamp - self.first_timestamp).total_seconds()

        return {
            "file": str(log_path),
            "time_span_seconds": duration_seconds,
            "window_seconds": self.window_seconds,
            "pdsch": {
                "blocks_seen": self.pdsch_blocks_seen,
                "valid_intervals": self.pdsch_valid_intervals,
                "reset_count": self.pdsch_reset_count,
                "configured_ca": self.pdsch_total_configured_ca,
                "active_carrier_histogram": dict(sorted(self.active_carrier_histogram.items())),
                "avg_active_carriers": safe_divide(total_active_carriers, total_intervals),
                "active_interval_ratio": safe_divide(active_only_intervals, total_intervals),
                "avg_active_carriers_active_only": safe_divide(active_only_carriers, active_only_intervals),
                "ca_utilization_ratio": safe_divide(total_active_carriers, total_intervals * self.pdsch_total_configured_ca) if self.pdsch_total_configured_ca else None,
                "ca_utilization_ratio_active_only": safe_divide(active_only_carriers, active_only_intervals * self.pdsch_total_configured_ca) if self.pdsch_total_configured_ca and active_only_intervals else None,
                "full_ca_ratio_all_intervals": safe_divide(self.active_carrier_histogram.get(self.pdsch_total_configured_ca, 0), total_intervals) if total_intervals else None,
                "full_ca_ratio_active_only": safe_divide(self.active_carrier_histogram.get(self.pdsch_total_configured_ca, 0), active_only_intervals) if active_only_intervals else None,
                "pass_bytes": int(total_pass_bytes),
                "fail_bytes": int(total_fail_bytes),
                "tb_bytes": int(total_tb_bytes),
                "retx_bytes": int(total_retx_bytes),
                "padding_bytes": int(total_padding_bytes),
                "pass_tb": int(total_pass_tb),
                "fail_tb": int(total_fail_tb),
                "pdsch_decode": int(total_decodes),
                "tb_bler": safe_divide(total_fail_tb, total_pass_tb + total_fail_tb),
                "goodput_efficiency": safe_divide(total_pass_bytes, total_tb_bytes),
                "retx_overhead": safe_divide(total_retx_bytes, total_tb_bytes),
                "padding_overhead": safe_divide(total_padding_bytes, total_tb_bytes),
                "carrier_summaries": carrier_summaries,
            },
            "ul_tb": {
                "intervals": self.ul_intervals,
                "reset_count": self.ul_reset_count,
                "new_tx_bytes": int(self.ul_totals["tb_new_tx_bytes"]),
                "retx_bytes": int(self.ul_totals["tb_retx_bytes"]),
                "new_tx_tb": int(self.ul_totals["num_new_tx_tb"]),
                "retx_tb": int(self.ul_totals["num_retx_tb"]),
                "ulsch_sched": int(self.ul_totals["num_ulsch_sched"]),
                "no_ulsch_sched": int(self.ul_totals["num_no_ulsch_sched"]),
                "retx_byte_ratio": safe_divide(self.ul_totals["tb_retx_bytes"], self.ul_totals["tb_new_tx_bytes"]),
                "retx_tb_ratio": safe_divide(self.ul_totals["num_retx_tb"], self.ul_totals["num_new_tx_tb"]),
                "avg_bytes_per_new_tb": safe_divide(self.ul_totals["tb_new_tx_bytes"], self.ul_totals["num_new_tx_tb"]),
                "avg_prb_per_sched": safe_divide(self.ul_totals["num_prb"], self.ul_totals["num_ulsch_sched"]),
                "avg_cqi": safe_divide(self.ul_totals["cqi"], self.ul_totals["num_ulsch_sched"]),
                "avg_ri": safe_divide(self.ul_totals["ri"], self.ul_totals["num_ulsch_sched"]),
                "avg_phr": safe_divide(self.ul_totals["phr"], self.ul_totals["num_phr"]),
            },
            "symbol_arbitration": {
                "slots": self.symbol_slots,
                "avg_dl_symbols": safe_divide(self.symbol_dl_total, self.symbol_slots),
                "avg_eval_symbols": safe_divide(self.symbol_eval_total, self.symbol_slots),
                "avg_ul_available_symbols": safe_divide(self.symbol_ul_available_total, self.symbol_slots),
                "avg_ul_committed_symbols": safe_divide(self.symbol_ul_committed_total, self.symbol_slots),
                "avg_guard_symbols": safe_divide(self.symbol_guard_total, self.symbol_slots),
                "avg_ssb_symbols": safe_divide(self.symbol_ssb_total, self.symbol_slots),
                "no_dl_slot_ratio": safe_divide(self.symbol_no_dl_slots, self.symbol_slots),
                "dl_symbol_fill_ratio": safe_divide(self.symbol_dl_total, self.symbol_eval_total),
            },
        }

    def _build_window_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for window_index in sorted(self.windows):
            window = self.windows[window_index]
            start, end = self._window_bounds(window_index)
            dominant_share = None
            if window.pass_bytes > 0 and window.carrier_pass_bytes:
                dominant_share = max(window.carrier_pass_bytes.values()) / window.pass_bytes
            rows.append(
                {
                    "window_index": window_index,
                    "window_start": start.isoformat(timespec="milliseconds"),
                    "window_end": end.isoformat(timespec="milliseconds"),
                    "seconds_from_start": window_index * self.window_seconds,
                    "pdsch_intervals": window.pdsch_intervals,
                    "active_intervals": window.active_intervals,
                    "pdsch_time_seconds": window.pdsch_time_seconds,
                    "configured_ca": window.configured_ca_max,
                    "avg_active_carriers": safe_divide(window.active_carriers_sum, window.pdsch_intervals),
                    "avg_active_carriers_active_only": safe_divide(window.active_carriers_sum, window.active_intervals),
                    "ca_utilization_ratio": safe_divide(window.active_carriers_sum, window.pdsch_intervals * window.configured_ca_max) if window.pdsch_intervals and window.configured_ca_max else None,
                    "ca_utilization_ratio_active_only": safe_divide(window.active_carriers_sum, window.active_intervals * window.configured_ca_max) if window.active_intervals and window.configured_ca_max else None,
                    "pass_bytes": window.pass_bytes,
                    "fail_bytes": window.fail_bytes,
                    "tb_bytes": window.tb_bytes,
                    "retx_bytes": window.retx_bytes,
                    "padding_bytes": window.padding_bytes,
                    "pass_tb": window.pass_tb,
                    "fail_tb": window.fail_tb,
                    "bucketed_pass_mib": window.pass_bytes / (1024 ** 2),
                    "throughput_mibps": safe_divide(window.pass_bytes / (1024 ** 2), window.pdsch_time_seconds),
                    "bler": safe_divide(window.fail_tb, window.pass_tb + window.fail_tb),
                    "goodput_efficiency": safe_divide(window.pass_bytes, window.tb_bytes),
                    "retx_ratio": safe_divide(window.retx_bytes, window.tb_bytes),
                    "padding_ratio": safe_divide(window.padding_bytes, window.tb_bytes),
                    "dominant_carrier_share": dominant_share,
                    "symbol_slots": window.symbol_slots,
                    "dl_symbol_fill_ratio": safe_divide(window.symbol_dl_total, window.symbol_eval_total),
                    "no_dl_slot_ratio": safe_divide(window.symbol_no_dl_slots, window.symbol_slots),
                    "avg_dl_symbols": safe_divide(window.symbol_dl_total, window.symbol_slots),
                    "avg_ul_available_symbols": safe_divide(window.symbol_ul_available_total, window.symbol_slots),
                    "avg_ul_committed_symbols": safe_divide(window.symbol_ul_committed_total, window.symbol_slots),
                    "ul_new_tx_mib": window.ul_new_tx_bytes / (1024 ** 2),
                    "ul_retx_ratio": safe_divide(window.ul_retx_bytes, window.ul_new_tx_bytes),
                    "ul_avg_prb_per_sched": safe_divide(window.ul_num_prb, window.ul_sched),
                    "ul_avg_cqi": safe_divide(window.ul_cqi, window.ul_sched),
                    "ul_avg_ri": safe_divide(window.ul_ri, window.ul_sched),
                    "ul_avg_phr": safe_divide(window.ul_phr, window.ul_num_phr),
                    "research_label": "",
                }
            )
            rows[-1]["research_label"] = classify_window(rows[-1])
        return rows

    def _build_carrier_window_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for window_index in sorted(self.windows):
            window = self.windows[window_index]
            for carrier_id in sorted(self.all_carrier_ids):
                pass_bytes = window.carrier_pass_bytes.get(carrier_id, 0)
                tb_bytes = window.carrier_tb_bytes.get(carrier_id, 0)
                retx_bytes = window.carrier_retx_bytes.get(carrier_id, 0)
                rows.append(
                    {
                        "window_index": window_index,
                        "seconds_from_start": window_index * self.window_seconds,
                        "carrier_id": carrier_id,
                        "pass_bytes": pass_bytes,
                        "pass_mib": pass_bytes / (1024 ** 2),
                        "share_of_window_pass": safe_divide(pass_bytes, window.pass_bytes),
                        "tb_bytes": tb_bytes,
                        "retx_ratio": safe_divide(retx_bytes, tb_bytes),
                    }
                )
        return rows

    def _build_research_findings(self, window_rows: list[dict[str, object]]) -> dict[str, object]:
        def collect_pairs(x_key: str, y_key: str, require_throughput: bool = False) -> tuple[list[float], list[float]]:
            xs: list[float] = []
            ys: list[float] = []
            for row in window_rows:
                x_value = row.get(x_key)
                y_value = row.get(y_key)
                if x_value is None or y_value is None:
                    continue
                if require_throughput and not row.get("throughput_mibps"):
                    continue
                xs.append(float(x_value))
                ys.append(float(y_value))
            return xs, ys

        active_windows = [row for row in window_rows if (row.get("throughput_mibps") or 0) > 0]
        low_ca_windows = [
            row for row in active_windows
            if row.get("ca_utilization_ratio_active_only") is not None and float(row["ca_utilization_ratio_active_only"]) < 0.50
        ]
        high_ca_windows = [
            row for row in active_windows
            if row.get("ca_utilization_ratio_active_only") is not None and float(row["ca_utilization_ratio_active_only"]) >= 0.67
        ]

        def summarize_windows(rows: list[dict[str, object]]) -> dict[str, object]:
            return {
                "count": len(rows),
                "avg_throughput_mibps": safe_divide(sum(float(row.get("throughput_mibps") or 0) for row in rows), len(rows)),
                "avg_bler": safe_divide(sum(float(row.get("bler") or 0) for row in rows), len(rows)),
                "avg_dl_symbol_fill_ratio": safe_divide(sum(float(row.get("dl_symbol_fill_ratio") or 0) for row in rows), len(rows)),
                "avg_no_dl_slot_ratio": safe_divide(sum(float(row.get("no_dl_slot_ratio") or 0) for row in rows), len(rows)),
                "avg_dominant_carrier_share": safe_divide(sum(float(row.get("dominant_carrier_share") or 0) for row in rows), len(rows)),
                "avg_active_only_ca": safe_divide(sum(float(row.get("ca_utilization_ratio_active_only") or 0) for row in rows), len(rows)),
            }

        label_counts = Counter(str(row.get("research_label") or "unknown") for row in window_rows)
        active_label_counts = Counter(str(row.get("research_label") or "unknown") for row in active_windows)

        xs, ys = collect_pairs("ca_utilization_ratio", "dl_symbol_fill_ratio")
        xs2, ys2 = collect_pairs("ca_utilization_ratio", "no_dl_slot_ratio")
        xs3, ys3 = collect_pairs("throughput_mibps", "dl_symbol_fill_ratio", require_throughput=True)
        xs4, ys4 = collect_pairs("bler", "retx_ratio")
        xs5, ys5 = collect_pairs("ca_utilization_ratio_active_only", "dl_symbol_fill_ratio", require_throughput=True)

        top_low_ca_with_load = sorted(
            [row for row in active_windows if (row.get("ca_utilization_ratio_active_only") or 1) < 0.50],
            key=lambda row: (float(row.get("throughput_mibps") or 0), -(float(row.get("ca_utilization_ratio_active_only") or 0))),
            reverse=True,
        )[:10]
        top_high_ca_with_load = sorted(
            [row for row in active_windows if (row.get("ca_utilization_ratio_active_only") or 0) >= 0.67],
            key=lambda row: (float(row.get("throughput_mibps") or 0), float(row.get("ca_utilization_ratio_active_only") or 0)),
            reverse=True,
        )[:10]
        top_bler_windows = sorted(
            [row for row in active_windows if row.get("bler") is not None],
            key=lambda row: float(row.get("bler") or 0),
            reverse=True,
        )[:10]
        top_single_carrier_windows = sorted(
            [row for row in active_windows if row.get("dominant_carrier_share") is not None],
            key=lambda row: (float(row.get("dominant_carrier_share") or 0), float(row.get("throughput_mibps") or 0)),
            reverse=True,
        )[:10]

        return {
            "correlations": {
                "ca_utilization_vs_dl_symbol_fill": pearson_correlation(xs, ys),
                "ca_utilization_vs_no_dl_slot_ratio": pearson_correlation(xs2, ys2),
                "throughput_vs_dl_symbol_fill": pearson_correlation(xs3, ys3),
                "bler_vs_retx_ratio": pearson_correlation(xs4, ys4),
                "active_only_ca_vs_dl_symbol_fill": pearson_correlation(xs5, ys5),
            },
            "label_counts": dict(sorted(label_counts.items())),
            "active_label_counts": dict(sorted(active_label_counts.items())),
            "window_groups": {
                "low_loaded_ca": summarize_windows(low_ca_windows),
                "high_loaded_ca": summarize_windows(high_ca_windows),
                "active_windows": summarize_windows(active_windows),
            },
            "top_low_ca_with_load": [
                {
                    "window_start": row["window_start"],
                    "throughput_mibps": row["throughput_mibps"],
                    "ca_utilization_ratio": row["ca_utilization_ratio"],
                    "ca_utilization_ratio_active_only": row["ca_utilization_ratio_active_only"],
                    "bler": row["bler"],
                    "dl_symbol_fill_ratio": row["dl_symbol_fill_ratio"],
                    "dominant_carrier_share": row["dominant_carrier_share"],
                    "research_label": row["research_label"],
                }
                for row in top_low_ca_with_load
            ],
            "top_high_ca_with_load": [
                {
                    "window_start": row["window_start"],
                    "throughput_mibps": row["throughput_mibps"],
                    "ca_utilization_ratio": row["ca_utilization_ratio"],
                    "ca_utilization_ratio_active_only": row["ca_utilization_ratio_active_only"],
                    "bler": row["bler"],
                    "dl_symbol_fill_ratio": row["dl_symbol_fill_ratio"],
                    "dominant_carrier_share": row["dominant_carrier_share"],
                    "research_label": row["research_label"],
                }
                for row in top_high_ca_with_load
            ],
            "top_bler_windows": [
                {
                    "window_start": row["window_start"],
                    "throughput_mibps": row["throughput_mibps"],
                    "bler": row["bler"],
                    "retx_ratio": row["retx_ratio"],
                    "ca_utilization_ratio": row["ca_utilization_ratio"],
                    "research_label": row["research_label"],
                }
                for row in top_bler_windows
            ],
            "top_single_carrier_windows": [
                {
                    "window_start": row["window_start"],
                    "throughput_mibps": row["throughput_mibps"],
                    "dominant_carrier_share": row["dominant_carrier_share"],
                    "ca_utilization_ratio_active_only": row["ca_utilization_ratio_active_only"],
                    "bler": row["bler"],
                    "research_label": row["research_label"],
                }
                for row in top_single_carrier_windows
            ],
            "investigation_ideas": [
                "Find windows with throughput but CA utilization below 33% to separate scheduler underuse from traffic idleness.",
                "Track whether DL symbol fill drops before BLER rises, which suggests scheduler or RF starvation instead of only HARQ instability.",
                "Measure carrier dominance over time; sustained dominance above 80% indicates poor CA balancing or SCell inactivity.",
                "Inspect reset-heavy regions in UL counters to determine whether modem logging resets align with throughput anomalies.",
                "Compare active-only CA utilization against overall utilization to distinguish idle time from CA inefficiency during actual data transfer.",
            ],
        }


def print_text_report(report: dict[str, object]) -> None:
    pdsch = report["pdsch"]
    ul_tb = report["ul_tb"]
    symbol = report["symbol_arbitration"]
    research = report["research"]

    print(f"File: {report['file']}")
    print(f"Time span: {format_number(report['time_span_seconds'])} s")
    print()
    print("DL CA efficiency")
    print(f"  PDSCH blocks seen: {pdsch['blocks_seen']}")
    print(f"  Valid delta intervals: {pdsch['valid_intervals']}")
    print(f"  Counter resets detected: {pdsch['reset_count']}")
    print(f"  Configured CA: {pdsch['configured_ca']}")
    print(f"  Average active carriers: {format_number(pdsch['avg_active_carriers'])}")
    print(f"  Average active carriers when active: {format_number(pdsch['avg_active_carriers_active_only'])}")
    print(f"  CA utilization ratio: {format_ratio(pdsch['ca_utilization_ratio'])}")
    print(f"  CA utilization ratio when active: {format_ratio(pdsch['ca_utilization_ratio_active_only'])}")
    print(f"  Active interval ratio: {format_ratio(pdsch['active_interval_ratio'])}")
    print(f"  Full CA ratio across all intervals: {format_ratio(pdsch['full_ca_ratio_all_intervals'])}")
    print(f"  Full CA ratio when active: {format_ratio(pdsch['full_ca_ratio_active_only'])}")
    print(f"  DL BLER: {format_ratio(pdsch['tb_bler'])}")
    print(f"  DL goodput efficiency: {format_ratio(pdsch['goodput_efficiency'])}")
    print(f"  DL retx overhead: {format_ratio(pdsch['retx_overhead'])}")
    print(f"  DL padding overhead: {format_ratio(pdsch['padding_overhead'])}")
    print(f"  CRC pass bytes: {format_bytes_gb(pdsch['pass_bytes'])}")
    print(f"  CRC fail bytes: {format_bytes_gb(pdsch['fail_bytes'])}")
    print(f"  Total TB bytes: {format_bytes_gb(pdsch['tb_bytes'])}")
    print(f"  Retx bytes: {format_bytes_gb(pdsch['retx_bytes'])}")
    print()
    print("UL efficiency")
    print(f"  Valid delta intervals: {ul_tb['intervals']}")
    print(f"  Counter resets detected: {ul_tb['reset_count']}")
    print(f"  New TX bytes: {format_bytes_gb(ul_tb['new_tx_bytes'])}")
    print(f"  ReTX bytes: {format_bytes_gb(ul_tb['retx_bytes'])}")
    print(f"  ReTX byte ratio: {format_ratio(ul_tb['retx_byte_ratio'])}")
    print(f"  ReTX TB ratio: {format_ratio(ul_tb['retx_tb_ratio'])}")
    print(f"  Average bytes per new TB: {format_number(ul_tb['avg_bytes_per_new_tb'])}")
    print(f"  Average PRB per schedule: {format_number(ul_tb['avg_prb_per_sched'])}")
    print(f"  Average CQI contribution per schedule: {format_number(ul_tb['avg_cqi'])}")
    print(f"  Average RI contribution per schedule: {format_number(ul_tb['avg_ri'])}")
    print(f"  Average PHR: {format_number(ul_tb['avg_phr'])}")
    print()
    print("Symbol arbitration")
    print(f"  Slots analyzed: {symbol['slots']}")
    print(f"  Average DL aggregated symbols: {format_number(symbol['avg_dl_symbols'])}")
    print(f"  Average evaluated symbols: {format_number(symbol['avg_eval_symbols'])}")
    print(f"  DL symbol fill ratio: {format_ratio(symbol['dl_symbol_fill_ratio'])}")
    print(f"  Average UL available symbols: {format_number(symbol['avg_ul_available_symbols'])}")
    print(f"  Average UL committed symbols: {format_number(symbol['avg_ul_committed_symbols'])}")
    print(f"  Average guard symbols: {format_number(symbol['avg_guard_symbols'])}")
    print(f"  Average SSB symbols: {format_number(symbol['avg_ssb_symbols'])}")
    print(f"  No-DL-slot ratio: {format_ratio(symbol['no_dl_slot_ratio'])}")
    print()
    print("Research correlations")
    correlations = research["correlations"]
    print(f"  CA utilization vs DL symbol fill: {format_number(correlations['ca_utilization_vs_dl_symbol_fill'], 3)}")
    print(f"  CA utilization vs no-DL-slot ratio: {format_number(correlations['ca_utilization_vs_no_dl_slot_ratio'], 3)}")
    print(f"  Active-only CA vs DL symbol fill: {format_number(correlations['active_only_ca_vs_dl_symbol_fill'], 3)}")
    print(f"  Throughput vs DL symbol fill: {format_number(correlations['throughput_vs_dl_symbol_fill'], 3)}")
    print(f"  BLER vs retx ratio: {format_number(correlations['bler_vs_retx_ratio'], 3)}")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_svg_line_panels(
    path: Path,
    title: str,
    x_values: list[float],
    panels: list[dict[str, object]],
    x_label: str,
) -> None:
    figure_height = max(4.2, 3.3 * len(panels))
    fig, axes = plt.subplots(len(panels), 1, figsize=(14, figure_height), sharex=True)
    if len(panels) == 1:
        axes = [axes]

    fig.suptitle(title, fontproperties=fp, y=0.992)
    for panel_index, (ax, panel) in enumerate(zip(axes, panels)):
        ax.set_title(str(panel["title"]), loc="left", pad=10, fontproperties=fp)
        ax.set_ylabel(str(panel["y_label"]), fontproperties=fp)
        panel_series = panel["series"]
        y_values_all: list[float] = []
        for series_index, series in enumerate(panel_series):
            values = [float(value) for value in series["values"]]
            if not values:
                continue
            y_values_all.extend(values)
            color = str(series.get("color") or PAIRED[series_index % len(PAIRED)])
            ax.plot(
                x_values,
                values,
                label=str(series["name"]),
                color=color,
                linestyle="-",
            )
        ax.set_xlim(min(x_values, default=0.0), max(x_values, default=1.0))
        y_max = _safe_series_max(y_values_all)
        ax.set_ylim(-0.04 * y_max, y_max * 1.08)
        if panel_index < len(panels) - 1:
            ax.tick_params(labelbottom=False)

    fig.subplots_adjust(top=0.84, bottom=0.12, hspace=0.34)
    _finalize_plot(fig, axes, x_label, legend_columns=max(1, min(4, max(len(panel["series"]) for panel in panels))))
    fig.savefig(path, format="svg")
    plt.close(fig)


def write_svg_scatter(
    path: Path,
    title: str,
    x_label: str,
    y_label: str,
    x_values: list[float],
    y_values: list[float],
    color_values: list[float],
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7.6))
    fig.suptitle(title, fontproperties=fp, y=0.988)
    if x_values and y_values:
        transformed_sizes = [math.log1p(max(value, 0.0)) for value in color_values]
        size_min = min(transformed_sizes, default=0.0)
        size_max = max(transformed_sizes, default=1.0)
        if size_max <= size_min:
            sizes = [42.0 for _ in transformed_sizes]
        else:
            sizes = [28.0 + 110.0 * ((value - size_min) / (size_max - size_min)) for value in transformed_sizes]
        scatter = ax.scatter(
            x_values,
            y_values,
            c=color_values,
            s=sizes,
            cmap=SCATTER_CMAP,
            alpha=0.72,
            edgecolors="none",
        )
        colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
        colorbar.set_label("Throughput (MiB/s)", fontproperties=fp)
        for label in colorbar.ax.get_yticklabels():
            label.set_fontproperties(fp)
    fig.subplots_adjust(top=0.90, bottom=0.12, right=0.88)
    ax.margins(x=0.02, y=0.02)
    ax.set_xlabel(x_label, fontproperties=fp)
    ax.set_ylabel(y_label, fontproperties=fp)
    _finalize_plot(fig, [ax], "", legend_columns=None)
    fig.savefig(path, format="svg")
    plt.close(fig)


def write_svg_pie(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    colors: list[str] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10.2, 7.8))
    fig.suptitle(title, fontproperties=fp, y=0.97)

    nonzero_pairs = [(label, value) for label, value in zip(labels, values) if value > 0]
    if nonzero_pairs:
        pie_labels = [label for label, _ in nonzero_pairs]
        pie_values = [value for _, value in nonzero_pairs]
        pie_colors = [
            (colors[index % len(colors)] if colors else PAIRED[index % len(PAIRED)])
            for index in range(len(nonzero_pairs))
        ]

        total_value = sum(pie_values)

        def autopct(pct: float) -> str:
            absolute = total_value * pct / 100.0
            return f"{pct:.1f}%\n{absolute:.1f} MiB"

        wedges, texts, autotexts = ax.pie(
            pie_values,
            labels=pie_labels,
            autopct=autopct,
            startangle=90,
            counterclock=False,
            colors=pie_colors,
            wedgeprops={"linewidth": 1.2, "edgecolor": "white"},
            textprops={"fontweight": "bold", "fontsize": 12},
            pctdistance=0.72,
            labeldistance=1.08,
        )
        for text in texts + autotexts:
            text.set_fontproperties(fp)
        ax.axis("equal")
    else:
        ax.text(0.5, 0.5, "No carrier pass data", ha="center", va="center", fontproperties=fp)
        ax.set_axis_off()

    fig.subplots_adjust(top=0.88, bottom=0.06)
    fig.savefig(path, format="svg")
    plt.close(fig)


def write_svg_carrier_goodput_with_zoom(
    path: Path,
    title: str,
    x_values: list[float],
    carrier_series: list[dict[str, object]],
    x_label: str,
    inset_anchor_x: float = 300.0,
    spike_selection_mode: str = "max",
    spike_min_x: float = 0.0,
    spike_target_x: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 7.4))
    fig.suptitle(title, fontproperties=fp, y=0.988)

    all_values: list[float] = []
    aggregate_values = [0.0 for _ in x_values]
    for series_index, series in enumerate(carrier_series):
        values = [float(value) for value in series["values"]]
        if not values:
            continue
        all_values.extend(values)
        aggregate_values = [current + value for current, value in zip(aggregate_values, values)]
        ax.plot(
            x_values,
            values,
            label=str(series["name"]),
            color=str(series.get("color") or PAIRED[series_index % len(PAIRED)]),
            linestyle="-",
        )

    ax.set_ylabel("MiB", fontproperties=fp)
    ax.set_xlim(min(x_values, default=0.0), max(x_values, default=1.0))
    y_max = _safe_series_max(all_values)
    ax.set_ylim(-0.04 * y_max, y_max * 1.08)

    if x_values and aggregate_values:
        spike_index = select_spike_index(
            x_values,
            aggregate_values,
            selection_mode=spike_selection_mode,
            min_x=spike_min_x,
            target_x=spike_target_x,
        )
        zoom_radius = min(4, max(1, len(x_values) // 20))
        left_index = max(0, spike_index - zoom_radius)
        right_index = min(len(x_values) - 1, spike_index + zoom_radius)
        x_pad = max(0.25, (x_values[right_index] - x_values[left_index]) * 0.06)
        x_min = x_values[left_index] - x_pad
        x_max = x_values[right_index] + x_pad

        zoom_values: list[float] = []
        for series in carrier_series:
            zoom_values.extend(float(value) for value in series["values"][left_index : right_index + 1])

        inset_width = 0.17
        inset_height = 0.18
        inset_y = 0.64
        x_min_full = min(x_values, default=0.0)
        x_max_full = max(x_values, default=1.0)
        x_span_full = max(x_max_full - x_min_full, 1.0)
        target_center_fraction = (inset_anchor_x - x_min_full) / x_span_full
        inset_x = max(0.02, min(0.98 - inset_width, target_center_fraction - (inset_width / 2)))

        inset_ax = ax.inset_axes([inset_x, inset_y, inset_width, inset_height])
        for series_index, series in enumerate(carrier_series):
            inset_ax.plot(
                x_values,
                [float(value) for value in series["values"]],
                color=str(series.get("color") or PAIRED[series_index % len(PAIRED)]),
                linestyle="-",
            )

        inset_ax.set_xlim(x_min, x_max)
        zoom_y_max = _safe_series_max(zoom_values)
        inset_ax.set_ylim(-0.03 * zoom_y_max, zoom_y_max * 1.12)
        inset_ax.set_title("Spike", fontproperties=font_manager.FontProperties(fname=fp_path, weight="bold", size=10), pad=3)
        inset_ax.tick_params(axis="both", which="major", labelsize=7)
        style_ax(inset_ax, enforce=True)
        ax.indicate_inset_zoom(inset_ax, edgecolor="#374151", alpha=0.9)

    fig.subplots_adjust(top=0.88, bottom=0.12)
    _finalize_plot(fig, [ax], x_label, legend_columns=max(1, min(4, len(carrier_series))))
    fig.savefig(path, format="svg")
    plt.close(fig)


def save_plots(output_dir: Path, window_rows: list[dict[str, object]], carrier_rows: list[dict[str, object]], window_seconds: float) -> list[str]:
    return save_plots_with_options(output_dir, window_rows, carrier_rows, window_seconds)


def save_plots_with_options(
    output_dir: Path,
    window_rows: list[dict[str, object]],
    carrier_rows: list[dict[str, object]],
    window_seconds: float,
    inset_anchor_x: float = 300.0,
    spike_selection_mode: str = "max",
    spike_min_x: float = 0.0,
    spike_target_x: float | None = None,
) -> list[str]:
    saved_paths: list[str] = []
    if not window_rows:
        return saved_paths

    x = [float(row["seconds_from_start"]) for row in window_rows]
    ca_all = [float(row["ca_utilization_ratio"] or 0) * 100 for row in window_rows]
    ca_active = [float(row["ca_utilization_ratio_active_only"] or 0) * 100 for row in window_rows]
    throughput = [float(row["throughput_mibps"] or 0) for row in window_rows]
    bler = [float(row["bler"] or 0) * 100 for row in window_rows]
    retx = [float(row["retx_ratio"] or 0) * 100 for row in window_rows]
    symbol_fill = [float(row["dl_symbol_fill_ratio"] or 0) * 100 for row in window_rows]
    no_dl = [float(row["no_dl_slot_ratio"] or 0) * 100 for row in window_rows]

    path = output_dir / "ca_utilization_and_throughput.svg"
    write_svg_line_panels(
        path,
        "CA utilization and DL throughput over time",
        x,
        [
            {
                "title": "CA utilization",
                "y_label": "Percent",
                "series": [
                    {"name": "CA utilization", "values": ca_all, "color": "#0f766e"},
                    {"name": "CA utilization when active", "values": ca_active, "color": "#f59e0b"},
                ],
            },
            {
                "title": "DL goodput",
                "y_label": "MiB/s",
                "series": [{"name": "DL goodput", "values": throughput, "color": "#1d4ed8"}],
            },
        ],
        "Seconds from start",
    )
    saved_paths.append(str(path))

    path = output_dir / "dl_quality_and_symbol_fill.svg"
    write_svg_line_panels(
        path,
        "DL quality and symbol arbitration over time",
        x,
        [
            {
                "title": "BLER and retransmission",
                "y_label": "Percent",
                "series": [
                    {"name": "DL BLER", "values": bler, "color": "#b91c1c"},
                    {"name": "ReTX ratio", "values": retx, "color": "#7c3aed"},
                ],
            },
            {
                "title": "Symbol arbitration",
                "y_label": "Percent",
                "series": [
                    {"name": "DL symbol fill", "values": symbol_fill, "color": "#15803d"},
                    {"name": "No-DL slot ratio", "values": no_dl, "color": "#6b7280"},
                ],
            },
        ],
        "Seconds from start",
    )
    saved_paths.append(str(path))

    filtered = [row for row in window_rows if row.get("ca_utilization_ratio") is not None and row.get("dl_symbol_fill_ratio") is not None and row.get("throughput_mibps") is not None]
    path = output_dir / "symbol_fill_vs_ca_utilization.svg"
    write_svg_scatter(
        path,
        "Symbol fill versus CA utilization",
        "DL symbol fill (%)",
        "CA utilization (%)",
        [float(row["dl_symbol_fill_ratio"]) * 100 for row in filtered],
        [float(row["ca_utilization_ratio"]) * 100 for row in filtered],
        [float(row["throughput_mibps"]) for row in filtered],
    )
    saved_paths.append(str(path))

    if carrier_rows:
        carrier_ids = sorted({int(row["carrier_id"]) for row in carrier_rows})
        grouped: dict[int, list[float]] = {carrier_id: [] for carrier_id in carrier_ids}
        window_indices = sorted({int(row["window_index"]) for row in carrier_rows})
        x_carrier = [window_index * window_seconds for window_index in window_indices]
        for window_index in window_indices:
            window_subset = [row for row in carrier_rows if int(row["window_index"]) == window_index]
            for carrier_id in carrier_ids:
                match = next((row for row in window_subset if int(row["carrier_id"]) == carrier_id), None)
                grouped[carrier_id].append(float(match["pass_mib"]) if match else 0.0)

        path = output_dir / "carrier_goodput_by_window.svg"
        series = []
        colors = ["#0f766e", "#1d4ed8", "#f59e0b", "#b91c1c", "#7c3aed"]
        for idx, carrier_id in enumerate(carrier_ids):
            series.append({"name": f"Carrier {carrier_id}", "values": grouped[carrier_id], "color": colors[idx % len(colors)]})
        write_svg_carrier_goodput_with_zoom(
            path,
            "Per-carrier DL goodput by window with spike zoom",
            x_carrier,
            series,
            "Seconds from start",
            inset_anchor_x=inset_anchor_x,
            spike_selection_mode=spike_selection_mode,
            spike_min_x=spike_min_x,
            spike_target_x=spike_target_x,
        )
        saved_paths.append(str(path))

        carrier_totals = [sum(grouped[carrier_id]) for carrier_id in carrier_ids]
        path = output_dir / "carrier_share_pie.svg"
        write_svg_pie(
            path,
            "Carrier contribution to total DL goodput",
            [f"Carrier {carrier_id}" for carrier_id in carrier_ids],
            carrier_totals,
            colors=colors,
        )
        saved_paths.append(str(path))

    return saved_paths


def write_summary_json(path: Path, report: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)


def load_cached_report(summary_path: Path) -> dict[str, object]:
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def update_artifact_paths(
    report: dict[str, object],
    output_dir: Path,
    plot_paths: list[str] | None = None,
    include_rendered: bool = False,
) -> dict[str, object]:
    artifacts = dict(report.get("artifacts", {}))
    artifacts.update(
        {
            "summary_json": str(output_dir / "summary.json"),
            "window_metrics_csv": str(output_dir / "window_metrics.csv"),
            "carrier_window_metrics_csv": str(output_dir / "carrier_window_metrics.csv"),
            "focused_anomaly_markdown": str(output_dir / "focused_anomaly_report.md"),
            "focused_anomaly_json": str(output_dir / "focused_anomaly_windows.json"),
        }
    )
    if include_rendered:
        artifacts.update(
            {
                "research_summary_markdown": str(output_dir / "research_summary.md"),
                "html_dashboard": str(output_dir / "research_dashboard.html"),
            }
        )
    if include_rendered and plot_paths is not None:
        artifacts["plots"] = plot_paths
    report["artifacts"] = artifacts
    return report


def print_artifact_report(report: dict[str, object]) -> None:
    artifacts = report.get("artifacts", {})
    print()
    print("Artifacts")
    if artifacts.get("summary_json"):
        print(f"  Summary JSON: {artifacts.get('summary_json')}")
    if artifacts.get("window_metrics_csv"):
        print(f"  Window metrics CSV: {artifacts.get('window_metrics_csv')}")
    if artifacts.get("carrier_window_metrics_csv"):
        print(f"  Carrier window CSV: {artifacts.get('carrier_window_metrics_csv')}")
    if artifacts.get("research_summary_markdown"):
        print(f"  Research summary: {artifacts.get('research_summary_markdown')}")
    if artifacts.get("focused_anomaly_markdown"):
        print(f"  Focused anomaly report: {artifacts.get('focused_anomaly_markdown')}")
    if artifacts.get("focused_anomaly_json"):
        print(f"  Focused anomaly JSON: {artifacts.get('focused_anomaly_json')}")
    if artifacts.get("html_dashboard"):
        print(f"  HTML dashboard: {artifacts.get('html_dashboard')}")
    for plot_path in artifacts.get("plots", []):
        print(f"  Plot: {plot_path}")


def build_focus_targets(report: dict[str, object]) -> list[dict[str, object]]:
    research = report["research"]
    target_groups = [
        ("low_loaded_ca", research.get("top_low_ca_with_load", [])[:5]),
        ("high_loaded_ca", research.get("top_high_ca_with_load", [])[:5]),
        ("high_bler", research.get("top_bler_windows", [])[:5]),
        ("single_carrier", research.get("top_single_carrier_windows", [])[:5]),
    ]
    targets: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()
    window_seconds = float(report["window_seconds"])
    for category, items in target_groups:
        for index, item in enumerate(items, start=1):
            window_start = datetime.fromisoformat(str(item["window_start"]))
            key = (category, str(item["window_start"]))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            targets.append(
                {
                    "target_id": f"{category}_{index}",
                    "category": category,
                    "window_start": window_start,
                    "window_end": window_start + timedelta(seconds=window_seconds),
                    "metrics": item,
                }
            )
    for index, cluster in enumerate(research.get("single_carrier_clusters", [])[:3], start=1):
        targets.append(
            {
                "target_id": f"single_carrier_cluster_{index}",
                "category": "single_carrier_cluster",
                "window_start": datetime.fromisoformat(str(cluster["start_window"])),
                "window_end": datetime.fromisoformat(str(cluster["end_window"])),
                "metrics": cluster,
            }
        )
    return targets


def extract_log_snippets(
    log_path: Path,
    targets: list[dict[str, object]],
    pre_seconds: float = 0.4,
    post_seconds: float = 1.2,
    max_entries_per_target: int = 20,
) -> list[dict[str, object]]:
    prepared_targets = []
    for target in targets:
        prepared_targets.append(
            {
                **target,
                "capture_start": target["window_start"] - timedelta(seconds=pre_seconds),
                "capture_end": target["window_end"] + timedelta(seconds=post_seconds),
                "entries": [],
            }
        )

    for timestamp, section_name, text in iterate_log_entries(log_path):
        for target in prepared_targets:
            if len(target["entries"]) >= max_entries_per_target:
                continue
            if target["capture_start"] <= timestamp <= target["capture_end"]:
                target["entries"].append(
                    {
                        "timestamp": timestamp.isoformat(timespec="milliseconds"),
                        "section_name": section_name,
                        "text": text,
                    }
                )

    return prepared_targets


def build_focused_markdown(snippets: list[dict[str, object]]) -> str:
    lines = [
        "# Focused Anomaly Report",
        "",
        "This report extracts raw QXDM blocks around the most interesting windows identified by the analyzer.",
        "",
    ]
    for snippet in snippets:
        metrics = snippet["metrics"]
        lines.extend(
            [
                f"## {snippet['target_id']}",
                "",
                f"- Category: {snippet['category']}",
                f"- Window start: {snippet['window_start'].isoformat(timespec='milliseconds')}",
                f"- Window end: {snippet['window_end'].isoformat(timespec='milliseconds')}",
                f"- Throughput: {format_number(metrics.get('throughput_mibps'))} MiB/s",
                f"- Active-only CA: {format_ratio(metrics.get('ca_utilization_ratio_active_only'))}",
                f"- Overall CA: {format_ratio(metrics.get('ca_utilization_ratio'))}",
                f"- BLER: {format_ratio(metrics.get('bler'))}",
                f"- DL symbol fill: {format_ratio(metrics.get('dl_symbol_fill_ratio'))}",
                f"- Dominant carrier share: {format_ratio(metrics.get('dominant_carrier_share'))}",
                f"- Label: {metrics.get('research_label', 'n/a')}",
                "",
            ]
        )
        if not snippet["entries"]:
            lines.extend(["No matching log entries were captured for this window.", ""])
            continue
        for entry in snippet["entries"]:
            lines.extend(
                [
                    f"### {entry['timestamp']} {entry['section_name']}",
                    "",
                    "```text",
                    entry["text"].rstrip(),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines) + "\n"


def detect_entry_events(section_name: str, text: str) -> set[str]:
    events: set[str] = set()
    if section_name == "NR5G MAC RACH Trigger":
        events.add("rach_trigger")
        events.add("access_or_setup")
    if section_name == "NR5G RRC OTA Packet":
        events.add("rrc_ota")
        lowered = text.lower()
        if "rrcsetuprequest" in lowered or "rrc setup req" in lowered:
            events.add("rrc_setup_request")
            events.add("access_or_setup")
        if "rrcsetupcomplete" in lowered:
            events.add("rrc_setup_complete")
            events.add("access_or_setup")
        if "rrcreconfiguration" in lowered:
            events.add("rrc_reconfiguration")
            events.add("reconfiguration")
        if "securitymodecommand" in lowered or "securitymodecomplete" in lowered:
            events.add("security_procedure")
            events.add("access_or_setup")
    if section_name == "NR5G MAC UL TB Stats":
        if "Num ReTx TB" in text:
            events.add("ul_stats")
    if section_name == "NR5G MAC PDSCH Stats":
        events.add("pdsch_stats")
    if section_name == "NR5G MAC Symbol Arbitration":
        events.add("symbol_arbitration")
    return events


def summarize_window_state(event_names: set[str], throughput_mibps: float) -> str:
    if "access_or_setup" in event_names:
        return "access_or_setup"
    if "reconfiguration" in event_names:
        return "reconfiguration"
    if throughput_mibps < 0.5:
        return "idle_or_control"
    return "steady_state"


def annotate_windows_with_events(log_path: Path, window_rows: list[dict[str, object]]) -> dict[str, object]:
    if not window_rows:
        return {"state_counts": {}, "active_state_counts": {}, "event_counts": {}}

    windows_by_index = {int(row["window_index"]): row for row in window_rows}
    base_start = datetime.fromisoformat(str(window_rows[0]["window_start"]))
    window_seconds = float(window_rows[0]["window_end"] != window_rows[0]["window_start"] and (datetime.fromisoformat(str(window_rows[0]["window_end"])) - base_start).total_seconds() or 1.0)

    for row in window_rows:
        row["event_names"] = []
        row["event_count"] = 0
        row["state_context"] = "steady_state"

    event_counts: Counter[str] = Counter()
    for timestamp, section_name, text in iterate_log_entries(log_path):
        window_index = int((timestamp - base_start).total_seconds() // window_seconds)
        row = windows_by_index.get(window_index)
        if row is None:
            continue
        events = detect_entry_events(section_name, text)
        if not events:
            continue
        event_counts.update(events)
        existing = set(row["event_names"])
        existing.update(events)
        row["event_names"] = sorted(existing)

    state_counts: Counter[str] = Counter()
    active_state_counts: Counter[str] = Counter()
    for row in window_rows:
        throughput = float(row.get("throughput_mibps") or 0.0)
        state_context = summarize_window_state(set(row["event_names"]), throughput)
        row["state_context"] = state_context
        row["event_count"] = len(row["event_names"])
        state_counts[state_context] += 1
        if throughput > 0:
            active_state_counts[state_context] += 1

    return {
        "state_counts": dict(sorted(state_counts.items())),
        "active_state_counts": dict(sorted(active_state_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
    }


def build_single_carrier_clusters(window_rows: list[dict[str, object]], min_windows: int = 2) -> list[dict[str, object]]:
    clusters: list[dict[str, object]] = []
    current: list[dict[str, object]] = []

    def flush_cluster() -> None:
        if len(current) < min_windows:
            current.clear()
            return
        start_row = current[0]
        end_row = current[-1]
        clusters.append(
            {
                "cluster_id": f"single_carrier_cluster_{len(clusters) + 1}",
                "window_count": len(current),
                "start_window": start_row["window_start"],
                "end_window": end_row["window_end"],
                "avg_throughput_mibps": safe_divide(sum(float(row.get("throughput_mibps") or 0) for row in current), len(current)),
                "peak_throughput_mibps": max(float(row.get("throughput_mibps") or 0) for row in current),
                "avg_dominant_carrier_share": safe_divide(sum(float(row.get("dominant_carrier_share") or 0) for row in current), len(current)),
                "avg_active_only_ca": safe_divide(sum(float(row.get("ca_utilization_ratio_active_only") or 0) for row in current), len(current)),
                "state_contexts": sorted({str(row.get("state_context") or "steady_state") for row in current}),
            }
        )
        current.clear()

    for row in window_rows:
        is_single_carrier = str(row.get("research_label")) == "single_carrier_dominant"
        if not is_single_carrier:
            flush_cluster()
            continue
        if current:
            previous_index = int(current[-1]["window_index"])
            this_index = int(row["window_index"])
            if this_index != previous_index + 1:
                flush_cluster()
        current.append(row)
    flush_cluster()
    clusters.sort(key=lambda item: (int(item["window_count"]), float(item["peak_throughput_mibps"] or 0)), reverse=True)
    return clusters


def build_markdown_summary(report: dict[str, object], plot_paths: list[str], output_dir: Path) -> str:
    pdsch = report["pdsch"]
    ul_tb = report["ul_tb"]
    symbol = report["symbol_arbitration"]
    research = report["research"]
    carrier_topology = report.get("carrier_topology", {})
    low_ca = research["window_groups"]["low_loaded_ca"]
    high_ca = research["window_groups"]["high_loaded_ca"]
    active_labels = research["active_label_counts"]
    state_awareness = research.get("state_awareness", {})
    single_carrier_clusters = research.get("single_carrier_clusters", [])

    lines = [
        "# QXDM NR5G CA Research Summary",
        "",
        f"- File: {report['file']}",
        f"- Time span: {format_number(report['time_span_seconds'])} s",
        f"- Window size: {format_number(report['window_seconds'])} s",
        "",
        "## Headline findings",
        "",
        f"- Overall CA utilization is {format_ratio(pdsch['ca_utilization_ratio'])}, but active-only CA utilization rises to {format_ratio(pdsch['ca_utilization_ratio_active_only'])}.",
        f"- The modem is active in {format_ratio(pdsch['active_interval_ratio'])} of valid PDSCH intervals.",
        f"- Full 3CC appears in {format_ratio(pdsch['full_ca_ratio_all_intervals'])} of all intervals and {format_ratio(pdsch['full_ca_ratio_active_only'])} of active intervals.",
        f"- DL BLER is {format_ratio(pdsch['tb_bler'])} with retransmission overhead {format_ratio(pdsch['retx_overhead'])}.",
        f"- DL symbol fill is {format_ratio(symbol['dl_symbol_fill_ratio'])} and no-DL-slot ratio is {format_ratio(symbol['no_dl_slot_ratio'])}.",
        f"- UL retransmission byte ratio is {format_ratio(ul_tb['retx_byte_ratio'])}.",
        "",
        "## Carrier Topology",
        "",
    ]
    mapped_cells = carrier_topology.get("mapped_cells", [])
    if mapped_cells:
        for cell in mapped_cells:
            confidence = "direct" if cell.get("mapping_confidence") == "direct_observed" else "inferred"
            scs_value = cell.get("scs_khz")
            scs_text = f", SCS {format_number(scs_value, 0)} kHz" if scs_value is not None else ""
            lines.append(
                f"- Carrier {cell['analyzer_carrier_id']}: {format_carrier_role(cell)}, n{cell['band']}, SSB ARFCN {cell['ssb_arfcn']}{scs_text} ({confidence})."
            )
    else:
        lines.append("- Carrier topology could not be inferred from the captured snippets.")

    lines.extend([
        "",
        "## Correlation signals",
        "",
        f"- CA utilization vs DL symbol fill: {format_number(research['correlations']['ca_utilization_vs_dl_symbol_fill'], 3)}",
        f"- CA utilization vs no-DL-slot ratio: {format_number(research['correlations']['ca_utilization_vs_no_dl_slot_ratio'], 3)}",
        f"- Active-only CA vs DL symbol fill: {format_number(research['correlations']['active_only_ca_vs_dl_symbol_fill'], 3)}",
        f"- Throughput vs DL symbol fill: {format_number(research['correlations']['throughput_vs_dl_symbol_fill'], 3)}",
        f"- BLER vs retransmission ratio: {format_number(research['correlations']['bler_vs_retx_ratio'], 3)}",
        "",
        "## Low-CA versus high-CA windows",
        "",
        f"- Low loaded-CA windows: {low_ca['count']} windows, average throughput {format_number(low_ca['avg_throughput_mibps'])} MiB/s, symbol fill {format_ratio(low_ca['avg_dl_symbol_fill_ratio'])}, dominant-carrier share {format_ratio(low_ca['avg_dominant_carrier_share'])}.",
        f"- High loaded-CA windows: {high_ca['count']} windows, average throughput {format_number(high_ca['avg_throughput_mibps'])} MiB/s, symbol fill {format_ratio(high_ca['avg_dl_symbol_fill_ratio'])}, dominant-carrier share {format_ratio(high_ca['avg_dominant_carrier_share'])}.",
        "",
        "## Active Window Labels",
        "",
    ])
    for label, count in active_labels.items():
        lines.append(f"- {label}: {count}")
    lines.extend(["", "## State Awareness", ""])
    for state_name, count in state_awareness.get("active_state_counts", {}).items():
        lines.append(f"- {state_name}: {count}")
    lines.extend(["", "## Single-Carrier Clusters", ""])
    if single_carrier_clusters:
        for cluster in single_carrier_clusters[:5]:
            lines.append(
                f"- {cluster['cluster_id']}: {cluster['start_window']} to {cluster['end_window']}, windows={cluster['window_count']}, peak throughput {format_number(cluster['peak_throughput_mibps'])} MiB/s, dominant share {format_ratio(cluster['avg_dominant_carrier_share'])}, active-only CA {format_ratio(cluster['avg_active_only_ca'])}."
            )
    else:
        lines.append("- No multi-window single-carrier clusters detected.")
    lines.extend(["", "## What to investigate next", ""])
    for idea in research["investigation_ideas"]:
        lines.append(f"- {idea}")
    lines.extend(["", "## Generated artifacts", ""])
    lines.extend([
        f"- JSON report: {(output_dir / 'summary.json').name}",
        f"- Window metrics CSV: {(output_dir / 'window_metrics.csv').name}",
        f"- Carrier window CSV: {(output_dir / 'carrier_window_metrics.csv').name}",
        f"- Focused anomaly report: {(output_dir / 'focused_anomaly_report.md').name}",
        f"- Focused anomaly JSON: {(output_dir / 'focused_anomaly_windows.json').name}",
        f"- HTML dashboard: {(output_dir / 'research_dashboard.html').name}",
    ])
    for plot_path in plot_paths:
        lines.append(f"- Plot: {Path(plot_path).name}")
    return "\n".join(lines) + "\n"


def build_html_report(report: dict[str, object], output_dir: Path) -> str:
    pdsch = report["pdsch"]
    research = report["research"]
    carrier_topology = report.get("carrier_topology", {})
    state_awareness = research.get("state_awareness", {})
    plots = report.get("artifacts", {}).get("plots", [])
    low_loaded = research["top_low_ca_with_load"][:5]
    high_loaded = research["top_high_ca_with_load"][:5]
    top_single = research.get("top_single_carrier_windows", [])[:5]
    top_bler = research["top_bler_windows"][:5]

    def metric_card(title: str, value: str, subtitle: str) -> str:
        return (
            '<div class="card metric">'
            f'<div class="metric-title">{html.escape(title)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div>'
            f'<div class="metric-sub">{html.escape(subtitle)}</div>'
            '</div>'
        )

    def render_table(title: str, rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> str:
        header = ''.join(f'<th>{html.escape(label)}</th>' for _, label in columns)
        body_rows = []
        for row in rows:
            cells = []
            for key, _ in columns:
                value = row.get(key)
                if isinstance(value, float):
                    if "ratio" in key or key in {"bler", "dominant_carrier_share", "dl_symbol_fill_ratio"}:
                        rendered = format_ratio(value)
                    else:
                        rendered = format_number(value)
                else:
                    rendered = str(value)
                cells.append(f'<td>{html.escape(rendered)}</td>')
            body_rows.append('<tr>' + ''.join(cells) + '</tr>')
        return (
            '<section class="card table-card">'
            f'<h2>{html.escape(title)}</h2>'
            '<table><thead><tr>' + header + '</tr></thead><tbody>' + ''.join(body_rows) + '</tbody></table>'
            '</section>'
        )

    plot_sections = ''.join(
        f'<section class="card plot-card"><h2>{html.escape(Path(plot_path).name)}</h2><img src="{html.escape(Path(plot_path).name)}" alt="{html.escape(Path(plot_path).name)}"></section>'
        for plot_path in plots
    )

    state_items = ''.join(
        f'<li><strong>{html.escape(state_name)}</strong>: {count}</li>'
        for state_name, count in state_awareness.get("active_state_counts", {}).items()
    )
    topology_items = ''.join(
        f'<li><strong>Carrier {cell["analyzer_carrier_id"]}</strong>: {html.escape(format_carrier_role(cell))}, n{cell["band"]}, SSB ARFCN {cell["ssb_arfcn"]} ({"direct" if cell.get("mapping_confidence") == "direct_observed" else "inferred"})</li>'
        for cell in carrier_topology.get("mapped_cells", [])
    ) or '<li>Carrier topology could not be inferred from the cached snippets.</li>'
    configured_items = ''.join(
        f'<li>{html.escape(format_carrier_role(cell))}: n{cell["band"]}, SSB ARFCN {cell["ssb_arfcn"]}</li>'
        for cell in carrier_topology.get("configured_cells", [])
    ) or '<li>No configured cell information was recovered.</li>'

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>QXDM Research Dashboard</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 0; background: #f3f4f6; color: #111827; }}
    .wrap {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .hero {{ background: linear-gradient(135deg, #0f766e, #1d4ed8); color: white; padding: 24px; border-radius: 18px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px; }}
    .card {{ background: white; border-radius: 16px; padding: 18px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); }}
    .metric-title {{ font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }}
    .metric-value {{ font-size: 28px; font-weight: 700; margin: 6px 0; }}
    .metric-sub {{ font-size: 13px; color: #4b5563; }}
    .plot-card img {{ width: 100%; height: auto; border: 1px solid #e5e7eb; border-radius: 10px; background: white; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #e5e7eb; }}
    th {{ color: #6b7280; font-size: 12px; text-transform: uppercase; }}
    ul {{ margin: 0; padding-left: 20px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
    @media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <h1>QXDM NR5G CA Research Dashboard</h1>
      <p>State-aware CA efficiency analysis for {html.escape(str(report['file']))}</p>
    </section>
    <section class=\"grid\">
      {metric_card('Overall CA Utilization', format_ratio(pdsch['ca_utilization_ratio']), 'Across all intervals')}
      {metric_card('Active-Only CA', format_ratio(pdsch['ca_utilization_ratio_active_only']), 'When DL is active')}
      {metric_card('DL BLER', format_ratio(pdsch['tb_bler']), 'Transport block failure rate')}
      {metric_card('ReTX Overhead', format_ratio(pdsch['retx_overhead']), 'Retransmission byte share')}
      {metric_card('Active Interval Ratio', format_ratio(pdsch['active_interval_ratio']), 'Fraction of valid DL intervals with traffic')}
      {metric_card('Single-Carrier Windows', str(research['active_label_counts'].get('single_carrier_dominant', 0)), 'Active windows dominated by one carrier')}
    </section>
    <section class=\"two-col\">
      <section class=\"card\">
                <h2>Carrier Topology</h2>
                <ul>{topology_items}</ul>
            </section>
            <section class=\"card\">
        <h2>Active State Context</h2>
        <ul>{state_items}</ul>
      </section>
        </section>
        <section class=\"two-col\">
      <section class=\"card\">
        <h2>Key Correlations</h2>
        <ul>
          <li>BLER vs ReTX: {html.escape(format_number(research['correlations']['bler_vs_retx_ratio'], 3))}</li>
          <li>Throughput vs Symbol Fill: {html.escape(format_number(research['correlations']['throughput_vs_dl_symbol_fill'], 3))}</li>
          <li>Active-only CA vs Symbol Fill: {html.escape(format_number(research['correlations']['active_only_ca_vs_dl_symbol_fill'], 3))}</li>
        </ul>
      </section>
            <section class=\"card\">
                <h2>Configured CA</h2>
                <ul>{configured_items}</ul>
            </section>
    </section>
    {render_table('Top Low Loaded-CA Windows', low_loaded, [('window_start', 'Window Start'), ('throughput_mibps', 'Throughput MiB/s'), ('ca_utilization_ratio_active_only', 'Active CA'), ('dominant_carrier_share', 'Dominant Share'), ('research_label', 'Label')])}
    {render_table('Top High Loaded-CA Windows', high_loaded, [('window_start', 'Window Start'), ('throughput_mibps', 'Throughput MiB/s'), ('ca_utilization_ratio_active_only', 'Active CA'), ('dominant_carrier_share', 'Dominant Share'), ('research_label', 'Label')])}
    {render_table('Top Single-Carrier Windows', top_single, [('window_start', 'Window Start'), ('throughput_mibps', 'Throughput MiB/s'), ('dominant_carrier_share', 'Dominant Share'), ('ca_utilization_ratio_active_only', 'Active CA'), ('research_label', 'Label')])}
    {render_table('Top BLER Windows', top_bler, [('window_start', 'Window Start'), ('throughput_mibps', 'Throughput MiB/s'), ('bler', 'BLER'), ('retx_ratio', 'ReTX Ratio'), ('research_label', 'Label')])}
    {plot_sections}
  </div>
</body>
</html>
"""


def save_data_artifacts(output_dir: Path, report: dict[str, object]) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    window_rows = report.pop("window_metrics")
    carrier_rows = report.pop("carrier_window_metrics")
    state_awareness = annotate_windows_with_events(Path(report["file"]), window_rows)
    single_carrier_clusters = build_single_carrier_clusters(window_rows)
    report["research"]["state_awareness"] = state_awareness
    report["research"]["single_carrier_clusters"] = single_carrier_clusters
    summary_path = output_dir / "summary.json"
    window_csv_path = output_dir / "window_metrics.csv"
    carrier_csv_path = output_dir / "carrier_window_metrics.csv"
    focused_markdown_path = output_dir / "focused_anomaly_report.md"
    focused_json_path = output_dir / "focused_anomaly_windows.json"
    html_dashboard_path = output_dir / "research_dashboard.html"

    write_csv(window_csv_path, window_rows)
    write_csv(carrier_csv_path, carrier_rows)
    focus_targets = build_focus_targets(report)
    focused_snippets = extract_log_snippets(Path(report["file"]), focus_targets)
    focused_markdown_path.write_text(build_focused_markdown(focused_snippets), encoding="utf-8")
    with focused_json_path.open("w", encoding="utf-8") as handle:
        json.dump(focused_snippets, handle, indent=2, default=str)

    report["carrier_topology"] = infer_carrier_topology(report, focused_snippets)
    report["focused_anomalies"] = focused_snippets
    report["window_metrics"] = window_rows
    report["carrier_window_metrics"] = carrier_rows
    update_artifact_paths(report, output_dir)
    write_summary_json(summary_path, report)
    return report


def render_cached_artifacts(
    output_dir: Path,
    report: dict[str, object],
    inset_anchor_x: float = 300.0,
    spike_selection_mode: str = "max",
    spike_min_x: float = 0.0,
    spike_target_x: float | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    window_rows = list(report.get("window_metrics", []))
    carrier_rows = list(report.get("carrier_window_metrics", []))
    expected_carrier_count = len(report.get("pdsch", {}).get("carrier_summaries", []))
    focused_sources = list(report.get("focused_anomalies", []))
    topology = report.get("carrier_topology") or {}
    if len(topology.get("mapped_cells", [])) < expected_carrier_count:
        focused_markdown_path = Path(
            str(report.get("artifacts", {}).get("focused_anomaly_markdown") or (output_dir / "focused_anomaly_report.md"))
        )
        if focused_markdown_path.exists():
            focused_sources.append({"entries": parse_focused_markdown_entries(focused_markdown_path.read_text(encoding="utf-8"))})
        report["carrier_topology"] = infer_carrier_topology(report, focused_sources)
    plot_paths = save_plots_with_options(
        output_dir,
        window_rows,
        carrier_rows,
        float(report["window_seconds"]),
        inset_anchor_x=inset_anchor_x,
        spike_selection_mode=spike_selection_mode,
        spike_min_x=spike_min_x,
        spike_target_x=spike_target_x,
    )
    markdown_path = output_dir / "research_summary.md"
    html_dashboard_path = output_dir / "research_dashboard.html"
    markdown_path.write_text(build_markdown_summary(report, plot_paths, output_dir), encoding="utf-8")
    update_artifact_paths(report, output_dir, plot_paths=plot_paths, include_rendered=True)
    html_dashboard_path.write_text(build_html_report(report, output_dir), encoding="utf-8")
    write_summary_json(output_dir / "summary.json", report)
    return report


def save_artifacts(output_dir: Path, report: dict[str, object]) -> dict[str, object]:
    report = save_data_artifacts(output_dir, report)
    return render_cached_artifacts(output_dir, report)


def main() -> None:
    args = parse_args()
    analyzer = Analyzer(window_seconds=args.window_seconds, max_pdsch_blocks=args.max_pdsch_blocks)
    report = analyzer.analyze(args.log_path)
    report = save_artifacts(args.output_dir, report)
    print_text_report(report)
    print_carrier_topology(report)
    print_artifact_report(report)
    if args.json:
        print()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()