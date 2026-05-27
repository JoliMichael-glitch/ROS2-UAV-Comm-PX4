#!/usr/bin/env python3

# 提醒：在 PowerShell/CMD 中运行示例：python scripts\cdf.py -i "C:\Users\MC\Desktop\实验数据\test3(单薄；1-1；J2R）\J2R-1node.csv"  -o latency_cdf.png


"""Plot end-to-end latency CDF curves from one or more CSV files."""

import argparse
import os
import sys
from glob import glob

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


LATENCY_COL_CANDIDATES = (
    "latency_ms",
    "latency (ms)",
    "latency",
    "e2e_latency_ms",
    "endtoendlatencyms",
    "endtoendlatency",
    "delay_ms",
    "delay (ms)",
)

COLOR_PALETTE = ["#004A99", "#B22222", "#006400", "#7A3E9D", "#D97706", "#0F766E"]
LINE_STYLES = ["-", "--", "-.", ":"]


def _normalize_col_name(name):
    return "".join(ch for ch in str(name).strip().lower() if ch.isalnum())


def _split_line_by_detected_delimiter(line):
    delimiter_candidates = ["\t", ",", ";", "|"]
    best_delimiter = None
    best_count = 1

    for delimiter in delimiter_candidates:
        count = len(line.split(delimiter))
        if count > best_count:
            best_count = count
            best_delimiter = delimiter

    if best_delimiter is not None and best_count > 1:
        return [part.strip() for part in line.split(best_delimiter)]

    return [part.strip() for part in line.strip().split()]


def _read_csv_robust(csv_path):
    df = pd.read_csv(csv_path, sep=None, engine="python")
    if len(df.columns) > 1:
        return df

    with open(csv_path, "r", encoding="utf-8", errors="replace") as file_handle:
        raw_text = file_handle.read()

    if "\\n" in raw_text and "\n" not in raw_text:
        raw_text = raw_text.replace("\\r\\n", "\n").replace("\\n", "\n")

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return df

    header_parts = _split_line_by_detected_delimiter(lines[0])
    if len(header_parts) <= 1:
        return df

    records = []
    for line in lines[1:]:
        parts = _split_line_by_detected_delimiter(line)
        if len(parts) == len(header_parts):
            records.append(parts)
        elif len(parts) > len(header_parts):
            records.append(parts[: len(header_parts)])
        else:
            records.append(parts + [""] * (len(header_parts) - len(parts)))

    if not records:
        return pd.DataFrame(columns=header_parts)

    return pd.DataFrame(records, columns=header_parts)


def _find_latency_column(columns):
    normalized = {_normalize_col_name(column): column for column in columns}
    candidate_keys = {_normalize_col_name(name) for name in LATENCY_COL_CANDIDATES}

    for key, original in normalized.items():
        if key in candidate_keys or "latency" in key or key.startswith("e2e") or key.startswith("delay"):
            return original
    return None


def _find_delay_columns(columns):
    normalized = {_normalize_col_name(column): column for column in columns}

    d_s_candidates = {
        _normalize_col_name(name)
        for name in (
            "d_s",
            "delay_s",
            "delay_seconds",
        )
    }
    d_ns_candidates = {
        _normalize_col_name(name)
        for name in (
            "d_ns",
            "delay_ns",
            "delay_nanoseconds",
        )
    }

    d_s_col = None
    d_ns_col = None
    for key, original in normalized.items():
        if d_s_col is None and (key in d_s_candidates or key.startswith("ds")):
            d_s_col = original
        if d_ns_col is None and (key in d_ns_candidates or key.startswith("dns")):
            d_ns_col = original

    return d_s_col, d_ns_col


def _list_csv_files_in_dir(dir_path):
    if not os.path.isdir(dir_path):
        return []

    csv_patterns = [os.path.join(dir_path, "*.csv"), os.path.join(dir_path, "*.CSV")]
    files = []
    for pattern in csv_patterns:
        files.extend(glob(pattern))
    return sorted(set(files))


def load_latency_data(input_path, drop_first_rows=0):
    if os.path.isfile(input_path):
        csv_paths = [input_path]
        dataset_name = os.path.splitext(os.path.basename(input_path))[0]
    elif os.path.isdir(input_path):
        csv_paths = _list_csv_files_in_dir(input_path)
        if not csv_paths:
            raise ValueError(f"No CSV files found in directory: {input_path}")
        dataset_name = os.path.basename(os.path.normpath(input_path))
    else:
        raise FileNotFoundError(f"Input path not found: {input_path}")

    latency_frames = []
    source_names = []

    for csv_path in csv_paths:
        df = _read_csv_robust(csv_path)
        if df.empty:
            continue

        if drop_first_rows > 0:
            df = df.iloc[drop_first_rows:].reset_index(drop=True)
            if df.empty:
                continue

        latency_col = _find_latency_column(df.columns)
        if latency_col is not None:
            latency_ms = pd.to_numeric(df[latency_col], errors="coerce").dropna()
        else:
            d_s_col, d_ns_col = _find_delay_columns(df.columns)
            if d_s_col is None or d_ns_col is None:
                raise ValueError(
                    "Cannot find latency column or delay columns. Expected a column such as latency_ms or delay_ms, "
                    f"or paired columns d_s / d_ns. File: {csv_path}, detected columns: {list(df.columns)}"
                )

            d_s = pd.to_numeric(df[d_s_col], errors="coerce")
            d_ns = pd.to_numeric(df[d_ns_col], errors="coerce")
            latency_ms = (d_s * 1000.0 + d_ns / 1_000_000.0).dropna()

        if latency_ms.empty:
            continue

        latency_frames.append(latency_ms)
        source_names.append(os.path.splitext(os.path.basename(csv_path))[0])

    if not latency_frames:
        raise ValueError(f"No valid latency values found in: {input_path}")

    merged_latency = pd.concat(latency_frames, ignore_index=True)
    return {
        "path": input_path,
        "name": dataset_name,
        "latency_ms": merged_latency,
        "samples": int(merged_latency.size),
        "sources": source_names,
    }


def _apply_academic_style():
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.size": 18,
            "axes.titlesize": 18,
            "axes.labelsize": 18,
            "xtick.labelsize": 18,
            "ytick.labelsize": 18,
            "legend.fontsize": 16,
            "mathtext.fontset": "stix",
        }
    )
    sns.set_theme(style="whitegrid")


def _apply_clean_style():
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 14,
            "axes.titlesize": 16,
            "axes.labelsize": 14,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "legend.fontsize": 11,
            "axes.edgecolor": "#4a4a4a",
            "axes.labelcolor": "#2f2f2f",
            "xtick.color": "#2f2f2f",
            "ytick.color": "#2f2f2f",
        }
    )
    sns.set_theme(style="whitegrid")


def plot_cdf(results, output_base, show=False, title=None, style="academic"):
    if not results:
        raise ValueError("No data to plot")

    if style == "clean":
        _apply_clean_style()
    else:
        _apply_academic_style()

    fig, ax = plt.subplots(figsize=(10.5, 7.5))

    for index, item in enumerate(results):
        latency = np.asarray(item["latency_ms"], dtype=float)
        latency = latency[np.isfinite(latency)]
        if latency.size == 0:
            continue

        sorted_latency = np.sort(latency)
        cdf = np.arange(1, sorted_latency.size + 1) / sorted_latency.size

        color = COLOR_PALETTE[index % len(COLOR_PALETTE)]
        line_style = LINE_STYLES[index % len(LINE_STYLES)]
        ax.plot(
            sorted_latency,
            cdf,
            label=f"{item['name']} (n={item['samples']})",
            color=color,
            linestyle=line_style,
            linewidth=2.5,
        )

    ax.set_xlabel("End-to-End Latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_ylim(0.0, 1.0)
    ax.set_xlim(left=0.0)

    if title:
        ax.set_title(title)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)

    ax.tick_params(axis="both", direction="in", width=1.5, length=6)
    grid_color = "#e0e0e0" if style == "clean" else "#CCCCCC"
    grid_alpha = 0.6 if style == "clean" else 0.4
    ax.grid(True, which="major", color=grid_color, linestyle="--", alpha=grid_alpha)

    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()

    png_path = f"{output_base}.png"
    pdf_path = f"{output_base}.pdf"
    dpi_value = 300 if style == "clean" else 600
    transparent = False if style == "clean" else True
    fig.savefig(png_path, dpi=dpi_value, transparent=transparent, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=dpi_value, transparent=transparent, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return png_path, pdf_path


def main():
    parser = argparse.ArgumentParser(
        description="Read one or more CSV files and plot an end-to-end latency CDF figure."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        help="Input CSV files and/or directories containing CSV files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="cdf",
        help="Output file base name without extension (default: cdf).",
    )
    parser.add_argument(
        "--drop-first-rows",
        type=int,
        default=0,
        help="Drop the first N rows from each CSV before plotting (default: 0).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the figure in addition to saving files.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional plot title.",
    )
    parser.add_argument(
        "--style",
        choices=["academic", "clean"],
        default="academic",
        help="Plot style preset (default: academic).",
    )

    args = parser.parse_args()

    try:
        if args.drop_first_rows < 0:
            raise ValueError("--drop-first-rows must be a non-negative integer")

        results = []
        for input_path in args.input:
            results.append(load_latency_data(input_path, drop_first_rows=args.drop_first_rows))

        png_path, pdf_path = plot_cdf(
            results,
            args.output,
            show=args.show,
            title=args.title,
            style=args.style,
        )
        print(f"Done. PNG saved to: {png_path}")
        print(f"Done. PDF saved to: {pdf_path}")
    except FileNotFoundError as error:
        print(f"[File Error] {error}")
        sys.exit(1)
    except ValueError as error:
        print(f"[Data Error] {error}")
        sys.exit(2)
    except Exception as error:
        print(f"[Unexpected Error] {error}")
        sys.exit(99)


if __name__ == "__main__":
    main()
