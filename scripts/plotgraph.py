#!/usr/bin/env python3
"""
读取 publisher.csv 并绘制环回时延箱线图。
Read publisher.csv and plot loopback latency boxplot.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def _find_delay_columns(columns):
    """根据列名自动定位 d_s / d_ns 列（兼容不同表头写法）。"""
    normalized = {c.strip().lower(): c for c in columns}

    d_s_candidates = [
        "d_s",
        "d_s(delay seconds)",
        "delay_s",
        "delay_seconds",
    ]
    d_ns_candidates = [
        "d_ns",
        "d_ns(delay nanoseconds)",
        "delay_ns",
        "delay_nanoseconds",
    ]

    d_s_col = None
    d_ns_col = None

    for key, original in normalized.items():
        if d_s_col is None and (key in d_s_candidates or key.startswith("d_s")):
            d_s_col = original
        if d_ns_col is None and (key in d_ns_candidates or key.startswith("d_ns")):
            d_ns_col = original

    return d_s_col, d_ns_col


def load_latency_ms(csv_path):
    """读取CSV并返回毫秒单位时延序列。"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File not found: {csv_path}")

    df = pd.read_csv(csv_path, sep=None, engine="python")
    if df.empty:
        raise ValueError("CSV is empty: no data rows found")

    d_s_col, d_ns_col = _find_delay_columns(df.columns)
    if d_s_col is None or d_ns_col is None:
        raise ValueError(
            "Cannot find delay columns. Expected columns like d_s and d_ns. "
            f"Detected columns: {list(df.columns)}"
        )

    d_s = pd.to_numeric(df[d_s_col], errors="coerce")
    d_ns = pd.to_numeric(df[d_ns_col], errors="coerce")

    latency_ms = d_s * 1000.0 + d_ns / 1_000_000.0
    latency_ms = latency_ms.dropna()

    if latency_ms.empty:
        raise ValueError("No valid latency values after numeric conversion")

    return latency_ms


def plot_latency_boxplot(latency_ms, output_path=None, show=False):
    """绘制箱线图并可选保存图片。"""
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(8, 5.5))

    sns.boxplot(
        y=latency_ms,
        ax=ax,
        color="#4C78A8",
        width=0.35,
        showfliers=True,
        whis=1.5,
    )

    ax.set_title("UAV Communication Loopback Latency Analysis", fontsize=13, pad=10)
    ax.set_ylabel("Latency (ms)")
    ax.set_xlabel("")
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)

    q1, median, q3 = np.percentile(latency_ms, [25, 50, 75])
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outlier_count = int(((latency_ms < lower_bound) | (latency_ms > upper_bound)).sum())

    stats_text = (
        f"Q1: {q1:.3f} ms\n"
        f"Median: {median:.3f} ms\n"
        f"Q3: {q3:.3f} ms\n"
        f"Outliers: {outlier_count}"
    )

    ax.text(
        0.98,
        0.98,
        stats_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150)

    if show:
        plt.show()
    else:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Read publisher CSV and plot latency boxplot (ms)."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input CSV/TSV file path, e.g. /home/ubuntu/uav_ws/publisher_log.csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="latency_boxplot.png",
        help="Output image path (default: latency_boxplot.png)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the plot window in addition to saving image",
    )

    args = parser.parse_args()

    try:
        latency_ms = load_latency_ms(args.input)
        plot_latency_boxplot(latency_ms, output_path=args.output, show=args.show)
        print(f"Done. Boxplot saved to: {args.output}")
    except FileNotFoundError as e:
        print(f"[File Error] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[Data Error] {e}")
        sys.exit(2)
    except Exception as e:
        print(f"[Unexpected Error] {e}")
        sys.exit(99)


if __name__ == "__main__":
    main()
