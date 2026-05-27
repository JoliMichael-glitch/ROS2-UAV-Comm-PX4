#!/usr/bin/env python3
"""Batch process R2C latency CSVs and draw a publication-grade boxplot."""

import argparse
import glob
import os
import sys
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

DEFAULT_FOLDERS = [
    r"C:\Users\MC\Desktop\实验数据\test5(多节点；R2C）\1node",
    r"C:\Users\MC\Desktop\实验数据\test5(多节点；R2C）\5nodes",
    r"C:\Users\MC\Desktop\实验数据\test5(多节点；R2C）\10nodes",
    r"C:\Users\MC\Desktop\实验数据\test5(多节点；R2C）\15nodes",
    r"C:\Users\MC\Desktop\实验数据\test5(多节点；R2C）\20nodes",
]

DEFAULT_LABELS = ["1 node", "5 nodes", "10 nodes", "15 nodes", "20 nodes"]


def _normalize_col_name(name: str) -> str:
    return "".join(ch for ch in str(name).strip().lower() if ch.isalnum())


def _extract_node_numbers(labels: List[str]) -> List[str]:
    numbers = []
    for label in labels:
        digits = "".join(ch for ch in str(label) if ch.isdigit())
        numbers.append(digits if digits else str(label))
    return numbers


def _find_delay_columns(columns: List[str]) -> Tuple[Optional[str], Optional[str]]:
    normalized = {_normalize_col_name(column): column for column in columns}
    d_s_col = None
    d_ns_col = None

    for key, original in normalized.items():
        if d_s_col is None and (key == "ds" or key.startswith("ds") or "delayseconds" in key):
            d_s_col = original
        if d_ns_col is None and (key == "dns" or key.startswith("dns") or "delaynanoseconds" in key):
            d_ns_col = original

    return d_s_col, d_ns_col


def _collect_csv_files(folder: str) -> List[str]:
    pattern = os.path.join(folder, "*.csv")
    return sorted(glob.glob(pattern))


def _load_latency_from_folder(folder: str, latency_col: str) -> pd.Series:
    csv_files = _collect_csv_files(folder)
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {folder}")

    series_list = []
    for csv_path in csv_files:
        df = pd.read_csv(csv_path, sep=None, engine="python")
        if latency_col in df.columns:
            values = pd.to_numeric(df[latency_col], errors="coerce").dropna()
            series_list.append(values)
            continue

        d_s_col, d_ns_col = _find_delay_columns(list(df.columns))
        if d_s_col is None or d_ns_col is None:
            raise ValueError(
                f"Missing column '{latency_col}' and cannot find delay columns in {csv_path}. "
                f"Columns: {list(df.columns)}"
            )

        d_s = pd.to_numeric(df[d_s_col], errors="coerce")
        d_ns = pd.to_numeric(df[d_ns_col], errors="coerce")
        latency_ms = (d_s * 1000.0 + d_ns / 1_000_000.0).replace([np.inf, -np.inf], np.nan).dropna()
        series_list.append(latency_ms)

    combined = pd.concat(series_list, ignore_index=True)
    combined = combined.replace([np.inf, -np.inf], np.nan).dropna()
    if combined.empty:
        raise ValueError(f"No valid latency data in: {folder}")

    positive = combined[combined > 0]
    if positive.empty:
        raise ValueError(f"All latency values are non-positive in: {folder}")

    return positive.reset_index(drop=True)


def _remove_outliers_iqr(series: pd.Series) -> pd.Series:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return series[(series >= lower) & (series <= upper)].reset_index(drop=True)


def _setup_theme(font_size: int) -> None:
    sns.set_theme(style="white")
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": font_size,
            "axes.labelsize": font_size,
            "xtick.labelsize": font_size,
            "ytick.labelsize": font_size,
        }
    )


def build_plot_data(
    folders: List[str],
    labels: List[str],
    latency_col: str,
    clip_max_ms: float | None,
    remove_outliers: bool,
) -> pd.DataFrame:
    rows = []
    for folder, label in zip(folders, labels):
        raw = _load_latency_from_folder(folder, latency_col)
        cleaned = _remove_outliers_iqr(raw) if remove_outliers else raw
        if clip_max_ms is not None:
            cleaned = cleaned[cleaned <= clip_max_ms].reset_index(drop=True)
        for value in cleaned:
            rows.append({"Node Count": label, "Latency (ms)": float(value)})

        removed = len(raw) - len(cleaned) if remove_outliers else 0
        print(f"{label}: raw={len(raw)}, cleaned={len(cleaned)}, removed={removed}")

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        raise ValueError("No data available after cleaning.")

    return plot_df


def _build_symlog_ticks(y_max: float) -> List[float]:
    ticks = [0.0, 10.0, 20.0, 30.0, 40.0, 100.0, 200.0, 300.0, 500.0]
    if y_max <= ticks[-1]:
        return ticks

    extra = [1000.0, 2000.0, 3000.0, 5000.0, 10000.0]
    while y_max > extra[-1]:
        extra = [value * 10.0 for value in extra]
    ticks.extend(value for value in extra if value <= y_max)
    if ticks[-1] < y_max:
        ticks.append(extra[-1])

    return ticks


def draw_boxplot(plot_df: pd.DataFrame, labels: List[str], output_png: str, output_pdf: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    palette = sns.color_palette("Set2", n_colors=len(labels))

    sns.boxplot(
        data=plot_df,
        x="Node Count",
        y="Latency (ms)",
        order=labels,
        hue="Node Count",
        palette=palette,
        showfliers=True,
        whis=1.5,
        flierprops={
            "marker": "o",
            "markersize": 3.5,
            "markerfacecolor": "#7a7a7a",
            "markeredgecolor": "none",
            "alpha": 0.3,
        },
        legend=False,
        ax=ax,
    )

    means = plot_df.groupby("Node Count", sort=False)["Latency (ms)"].mean().reindex(labels)
    ax.scatter(
        range(len(labels)),
        means.values,
        marker="D",
        s=80,
        color="#C33C3C",
        zorder=3,
        label="Mean",
    )

    ax.set_xlabel("Nodes")
    ax.set_ylabel("Latency (ms)")
    ax.set_yscale("symlog", linthresh=40.0)

    y_max = float(plot_df["Latency (ms)"].max())
    y_max = max(100.0, y_max)
    ax.set_ylim(0.0, y_max * 1.05)

    yticks = _build_symlog_ticks(y_max)
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _: f"{value:g}"))

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(_extract_node_numbers(labels))

    ax.axhline(40.0, linestyle="--", color="#1a1a1a", alpha=0.5, linewidth=1.5, zorder=1)

    ax.grid(True, axis="y", linestyle="--", color="#cfcfcf", alpha=0.7, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=False)

    plt.tight_layout()
    fig.savefig(output_png, dpi=300)
    fig.savefig(output_pdf, dpi=300)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw R2C latency boxplot with IQR cleaning.")
    parser.add_argument("--folders", nargs=5, default=DEFAULT_FOLDERS, help="Five folders for 1/5/10/15/20 nodes.")
    parser.add_argument("--labels", nargs=5, default=DEFAULT_LABELS, help="Five x-axis labels.")
    parser.add_argument("--latency-col", default="latency", help="CSV column name for latency values.")
    parser.add_argument("--clip-max-ms", type=float, default=None, help="Clip values above this latency (ms).")
    parser.add_argument("--remove-outliers", action="store_true", help="Remove outliers using 1.5*IQR.")
    parser.add_argument("--font-size", type=int, default=18, help="Base font size.")
    parser.add_argument("--output-png", default="r2c_latency_boxplot.png", help="Output PNG path.")
    parser.add_argument("--output-pdf", default="r2c_latency_boxplot.pdf", help="Output PDF path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if len(args.folders) != 5 or len(args.labels) != 5:
        raise ValueError("Exactly five folders and five labels are required.")

    _setup_theme(args.font_size)
    plot_df = build_plot_data(args.folders, args.labels, args.latency_col, args.clip_max_ms, args.remove_outliers)
    draw_boxplot(plot_df, args.labels, args.output_png, args.output_pdf)

    print("Saved:")
    print(args.output_png)
    print(args.output_pdf)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[Error] {exc}")
        sys.exit(1)
