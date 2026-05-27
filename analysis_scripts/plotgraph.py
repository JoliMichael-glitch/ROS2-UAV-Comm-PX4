#!/usr/bin/env python3
"""Plot latency boxplot and histogram figures with shared y-axis limits."""

import argparse
import math
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import MaxNLocator


def _normalize_col_name(name):
    return "".join(ch for ch in str(name).strip().lower() if ch.isalnum())


def _find_delay_columns(columns):
    normalized = {_normalize_col_name(column): column for column in columns}
    d_s_col = None
    d_ns_col = None

    for key, original in normalized.items():
        if d_s_col is None and (key == "ds" or key.startswith("ds") or "delayseconds" in key):
            d_s_col = original
        if d_ns_col is None and (key == "dns" or key.startswith("dns") or "delaynanoseconds" in key):
            d_ns_col = original

    return d_s_col, d_ns_col


def _find_sequence_column(columns):
    normalized = {_normalize_col_name(column): column for column in columns}
    seq_col = None
    for key, original in normalized.items():
        if key in {"sn", "seq", "sequence", "sequencenumber", "packetid", "id"}:
            seq_col = original
            break
        if key.startswith("sn") or key.startswith("seq") or key.startswith("id"):
            seq_col = original
            break
    return seq_col


def load_latency(csv_path, latency_threshold_ms=100.0):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File not found: {csv_path}")

    df = pd.read_csv(csv_path, sep=None, engine="python")
    if df.empty:
        raise ValueError(f"CSV is empty: {csv_path}")

    d_s_col, d_ns_col = _find_delay_columns(df.columns)
    if d_s_col is None or d_ns_col is None:
        raise ValueError(
            f"Cannot find delay columns d_s/d_ns in {csv_path}. Detected columns: {list(df.columns)}"
        )

    d_s = pd.to_numeric(df[d_s_col], errors="coerce")
    d_ns = pd.to_numeric(df[d_ns_col], errors="coerce")
    latency_ms = (d_s * 1000.0 + d_ns / 1_000_000.0).replace([np.inf, -np.inf], np.nan).dropna()
    latency_ms = latency_ms[latency_ms >= 0]

    if latency_ms.empty:
        raise ValueError(f"No valid latency values in {csv_path}")

    seq_col = _find_sequence_column(df.columns)
    received_packets = int(latency_ms.size)
    expected_packets = int(latency_ms.size)
    packet_loss_rate = 0.0
    if seq_col is not None:
        seq = pd.to_numeric(df[seq_col], errors="coerce").dropna()
        if not seq.empty:
            seq_unique = pd.Series(seq.astype(np.int64).unique())
            expected_packets = int(seq_unique.max() - seq_unique.min() + 1)
            received_packets = int(seq_unique.size)
            if expected_packets > 0:
                packet_loss_rate = max(0.0, (expected_packets - received_packets) / expected_packets * 100.0)

    mean_latency = float(latency_ms.mean())
    high_latency_rate = float((latency_ms > latency_threshold_ms).mean() * 100.0)

    return {
        "name": os.path.splitext(os.path.basename(csv_path))[0],
        "latency_ms": latency_ms.reset_index(drop=True),
        "samples": int(latency_ms.size),
        "mean_latency": mean_latency,
        "packet_loss_rate": packet_loss_rate,
        "high_latency_rate": high_latency_rate,
        "received_packets": received_packets,
        "expected_packets": expected_packets,
    }


def plot_boxplot(results, output_path, y_max):
    rows = []
    for item in results:
        rows.extend(
            {
                "Dataset": item["name"],
                "Latency (ms)": float(value),
            }
            for value in item["latency_ms"].values
        )

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        raise ValueError("No data to plot boxplot")

    sns.set_theme(
        style="whitegrid",
        rc={
            "font.size": 18,
            "axes.titlesize": 18,
            "axes.labelsize": 18,
            "xtick.labelsize": 18,
            "ytick.labelsize": 18,
        },
    )

    fig, ax = plt.subplots(figsize=(11.0, 8.0))
    sns.boxplot(
        data=plot_df,
        x="Dataset",
        y="Latency (ms)",
        ax=ax,
        color="#4C78A8",
        width=0.72,
        showfliers=True,
        whis=1.5,
        linewidth=1.2,
    )

    ax.set_title("UAV Communication Loopback Latency Boxplot", pad=10)
    ax.set_xlabel("CSV Dataset")
    ax.set_ylabel("Latency (ms)")
    ax.set_ylim(0.0, y_max)
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    ax.tick_params(axis="x", rotation=15)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def plot_histograms(results, output_path, y_max, bins=40, latency_threshold_ms=100.0):
    times_font = FontProperties(family="Times New Roman")
    title_font = FontProperties(family="SimSun")

    sns.set_theme(
        style="whitegrid",
        rc={
            "font.family": "Times New Roman",
            "font.size": 28,
            "axes.titlesize": 32,
            "axes.labelsize": 30,
            "xtick.labelsize": 28,
            "ytick.labelsize": 28,
        },
    )

    n = len(results)
    ncols = min(3, n)
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(7.6 * ncols, 6.0 * nrows), sharey=True)

    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])
    axes = axes.reshape(-1)

    colors = ["#8FBBD9", "#F2B880", "#8BC69C", "#C6A0D5"]
    kde_colors = ["#1F4E79", "#B8610E", "#2E6E4E", "#6A3D9A"]

    # Fixed axes for fair comparison across all subplots.
    x_min, x_max = 0.0, 1600.0
    y_min, y_max_fixed = 0.0, 1000.0
    bin_edges = np.linspace(x_min, x_max, bins + 1)

    fixed_titles = [
        "(a) 10m 直连视距 (LOS)",
        "(b) 10m 多跳中继 (3-Hops)",
        "(c) 10m 直连非视距 (NLOS)",
    ]
    for idx, item in enumerate(results):
        ax = axes[idx]
        latency = item["latency_ms"]

        sns.histplot(
            x=latency,
            bins=bin_edges,
            kde=True,
            stat="count",
            color=colors[idx % len(colors)],
            line_kws={"linewidth": 2.6, "color": kde_colors[idx % len(kde_colors)]},
            edgecolor="white",
            ax=ax,
        )

        if len(results) == 3 and idx < 3:
            _ = fixed_titles[idx]
        else:
            _ = item["name"]
        ax.set_xlabel("Latency (ms)", fontproperties=times_font, fontsize=30)
        ax.set_ylabel("Count", fontproperties=times_font, fontsize=30)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max_fixed)
        ax.axvline(latency_threshold_ms, color="#E45756", linestyle="--", linewidth=2.6, alpha=0.95)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=6, min_n_ticks=4))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6, min_n_ticks=4))
        ax.grid(True, axis="both", linestyle="--", alpha=0.35)

        ax.text(
            0.98,
            0.98,
            (
                f"Mean: {item['mean_latency']:.2f} ms\n"
                f"Packet Loss Rate: {item['packet_loss_rate']:.2f}%\n"
                f"Samples: {item['samples']}\n"
                f"High-Latency Rate (>{latency_threshold_ms:g} ms): {item['high_latency_rate']:.2f}%"
            ),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=13,
            fontproperties=times_font,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7, edgecolor="#4a4a4a"),
        )

    for idx in range(n, len(axes)):
        fig.delaxes(axes[idx])

    fig.text(
        0.5,
        0.02,
        "UAV Communication Loopback Latency Histograms",
        ha="center",
        va="bottom",
        fontproperties=times_font,
        fontsize=28,
    )
    plt.tight_layout(rect=(0, 0.22, 1, 1), w_pad=1.0, h_pad=1.0)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Plot latency boxplot and histogram with shared y-axis limits."
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        required=True,
        help="Input CSV files.",
    )
    parser.add_argument(
        "--labels",
        nargs="+",
        default=None,
        help="Optional custom display labels for each input file, in the same order as --input.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="latency_boxplot.png",
        help="Output path for boxplot image.",
    )
    parser.add_argument(
        "--hist-output",
        default="latency_hist.png",
        help="Output path for histogram image.",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=40,
        help="Histogram bins.",
    )
    parser.add_argument(
        "--y-percentile",
        type=float,
        default=99.0,
        help="Percentile used to define shared y-axis upper bound.",
    )
    parser.add_argument(
        "--y-max",
        type=float,
        default=None,
        help="Manual shared y-axis upper bound in ms.",
    )
    parser.add_argument(
        "--latency-threshold-ms",
        type=float,
        default=100.0,
        help="Threshold used for high-latency-rate statistics and reference line.",
    )

    args = parser.parse_args()

    try:
        if args.bins <= 0:
            raise ValueError("--bins must be positive")

        results = [load_latency(path, latency_threshold_ms=args.latency_threshold_ms) for path in args.input]
        if args.labels is not None:
            if len(args.labels) != len(results):
                raise ValueError("--labels count must match the number of --input files")
            for item, label in zip(results, args.labels):
                item["name"] = str(label)
        latency_all = pd.concat([item["latency_ms"] for item in results], ignore_index=True)

        if args.y_max is not None:
            y_max = float(args.y_max)
        else:
            if not (0.0 < args.y_percentile <= 100.0):
                raise ValueError("--y-percentile must be in (0, 100]")
            y_max = float(np.percentile(latency_all.values, args.y_percentile))

        if y_max <= 0:
            raise ValueError("Shared y-axis upper bound must be positive")

        y_max *= 1.05

        plot_boxplot(results, args.output, y_max=y_max)
        plot_histograms(
            results,
            args.hist_output,
            y_max=y_max,
            bins=args.bins,
            latency_threshold_ms=args.latency_threshold_ms,
        )

        print(f"Done. Boxplot saved to: {args.output}")
        print(f"Done. Histogram saved to: {args.hist_output}")
        print(f"Shared latency y-axis upper bound: {y_max:.2f} ms")
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