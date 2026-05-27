#!/usr/bin/env python3
"""Compare latency and loss metrics for two CSV datasets without CDF plots."""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


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
    for key, original in normalized.items():
        if key in {"sn", "seq", "sequence", "sequencenumber", "packetid", "id"}:
            return original
        if key.startswith(("sn", "seq", "id")):
            return original
    return None


def load_metrics(csv_path, latency_threshold_ms=100.0, fixed_expected_packets=None):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File not found: {csv_path}")

    df = pd.read_csv(csv_path, sep=None, engine="python")
    if df.empty:
        raise ValueError(f"CSV is empty: {csv_path}")

    d_s_col, d_ns_col = _find_delay_columns(df.columns)
    if d_s_col is None or d_ns_col is None:
        raise ValueError(f"Cannot find delay columns in {csv_path}. Detected columns: {list(df.columns)}")

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
    seq_min = None
    seq_max = None

    if seq_col is not None:
        seq = pd.to_numeric(df[seq_col], errors="coerce").dropna()
        if not seq.empty:
            seq_unique = pd.Series(seq.astype(np.int64).unique())
            received_packets = int(seq_unique.size)
            seq_min = int(seq_unique.min())
            seq_max = int(seq_unique.max())
            expected_packets = int(seq_unique.max() - seq_unique.min() + 1)
            if fixed_expected_packets is not None:
                expected_packets = int(fixed_expected_packets)
            if expected_packets > 0:
                packet_loss_rate = max(0.0, (expected_packets - received_packets) / expected_packets * 100.0)
    elif fixed_expected_packets is not None:
        expected_packets = int(fixed_expected_packets)
        packet_loss_rate = max(0.0, (expected_packets - received_packets) / expected_packets * 100.0)

    mean_latency = float(latency_ms.mean())
    median_latency = float(latency_ms.median())
    p95_latency = float(np.percentile(latency_ms.values, 95))
    p99_latency = float(np.percentile(latency_ms.values, 99))
    high_latency_rate = float((latency_ms > latency_threshold_ms).mean() * 100.0)

    return {
        "name": os.path.splitext(os.path.basename(csv_path))[0],
        "csv_path": csv_path,
        "latency_ms": latency_ms.reset_index(drop=True),
        "samples": int(latency_ms.size),
        "mean_latency": mean_latency,
        "median_latency": median_latency,
        "p95_latency": p95_latency,
        "p99_latency": p99_latency,
        "packet_loss_rate": packet_loss_rate,
        "high_latency_rate": high_latency_rate,
        "received_packets": received_packets,
        "expected_packets": expected_packets,
        "seq_min": seq_min,
        "seq_max": seq_max,
    }


def _setup_theme():
    sns.set_theme(
        style="whitegrid",
        rc={
            "font.size": 24,
            "axes.titlesize": 26,
            "axes.labelsize": 24,
            "xtick.labelsize": 24,
            "ytick.labelsize": 24,
        },
    )


def plot_overlaid_histogram(results, output_path, bins=50, latency_threshold_ms=100.0):
    _setup_theme()
    fig, ax = plt.subplots(figsize=(11.5, 7.2))

    combined = pd.concat([item["latency_ms"] for item in results], ignore_index=True)
    y_max = float(np.percentile(combined.values, 99.0)) * 1.05
    if not np.isfinite(y_max) or y_max <= 0:
        y_max = float(combined.max()) * 1.05
    bin_edges = np.linspace(0.0, y_max, bins + 1)

    colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756"]
    for idx, item in enumerate(results):
        sns.histplot(
            x=item["latency_ms"],
            bins=bin_edges,
            stat="density",
            element="step",
            fill=False,
            common_norm=False,
            color=colors[idx % len(colors)],
            linewidth=2.0,
            label=f'{item["name"]} (mean {item["mean_latency"]:.2f} ms)',
            ax=ax,
        )

    ax.axvline(latency_threshold_ms, color="#E45756", linestyle="--", linewidth=2.0, label=f"{latency_threshold_ms:g} ms threshold")
    ax.set_xlim(0.0, y_max)
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Density")
    ax.set_title("Latency Distribution Comparison")
    ax.legend(frameon=True, fontsize=24)
    ax.grid(True, linestyle="--", alpha=0.35)
    plt.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def plot_box_violin(results, output_path):
    _setup_theme()
    rows = []
    for item in results:
        rows.extend({"Dataset": item["name"], "Latency (ms)": float(value)} for value in item["latency_ms"].values)

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        raise ValueError("No data to plot box/violin chart")

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.5), sharey=True)
    sns.boxplot(data=plot_df, x="Dataset", y="Latency (ms)", ax=axes[0], palette=["#4C78A8", "#F58518"], showfliers=True, whis=1.5)
    sns.violinplot(data=plot_df, x="Dataset", y="Latency (ms)", ax=axes[1], palette=["#4C78A8", "#F58518"], inner="quartile", cut=0)

    for ax, title in zip(axes, ["Boxplot", "Violin plot"]):
        ax.set_title(title)
        ax.set_xlabel("")
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        ax.tick_params(axis="both", labelsize=18)

    axes[0].set_ylabel("Latency (ms)")
    axes[1].set_ylabel("")
    plt.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def plot_metric_bars(results, output_path):
    _setup_theme()
    metrics = [
        ("Mean", "mean_latency"),
        (">100ms %", "high_latency_rate"),
        ("Loss %", "packet_loss_rate"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6.5))
    axes = np.atleast_1d(axes).reshape(-1)
    palette = ["#4C78A8", "#F58518"]

    for ax, (label, key) in zip(axes, metrics):
        values = [item[key] for item in results]
        bars = ax.bar([item["name"] for item in results], values, color=palette, width=0.6)
        ax.set_title(label)
        ax.grid(True, axis="y", linestyle="--", alpha=0.35)
        ax.tick_params(axis="x", rotation=12)
        ax.tick_params(axis="both", labelsize=24)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.2f}", ha="center", va="bottom", fontsize=24)

    plt.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def plot_packet_index_scatter(results, output_path):
    _setup_theme()
    fig, ax = plt.subplots(figsize=(11.5, 7.2))
    colors = ["#4C78A8", "#F58518"]

    for idx, item in enumerate(results):
        values = item["latency_ms"].values
        packet_index = np.arange(len(values))
        ax.scatter(packet_index, values, s=10, alpha=0.45, color=colors[idx % len(colors)], label=item["name"])
        ax.plot(packet_index, values, color=colors[idx % len(colors)], linewidth=1.0, alpha=0.35)

    ax.set_xlabel("Packet Index")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency vs Packet Index")
    ax.tick_params(axis="both", labelsize=24)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(fontsize=24)
    plt.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def write_summary(results, output_path):
    rows = []
    for item in results:
        rows.append(
            {
                "dataset": item["name"],
                "samples": item["samples"],
                "received_packets": item["received_packets"],
                "expected_packets": item["expected_packets"],
                "packet_loss_rate_pct": item["packet_loss_rate"],
                "high_latency_rate_pct": item["high_latency_rate"],
                "mean_latency_ms": item["mean_latency"],
                "median_latency_ms": item["median_latency"],
                "p95_latency_ms": item["p95_latency"],
                "p99_latency_ms": item["p99_latency"],
                "seq_min": item["seq_min"],
                "seq_max": item["seq_max"],
            }
        )

    pd.DataFrame(rows).to_csv(output_path, index=False)


def main():
    parser = argparse.ArgumentParser(description="Compare latency/loss metrics for two CSV datasets.")
    parser.add_argument("-i", "--input", nargs=2, required=True, help="Two input CSV files to compare.")
    parser.add_argument("--labels", nargs=2, default=None, help="Optional display labels for the two inputs.")
    parser.add_argument("--output-dir", default="compare_outputs", help="Directory for output figures.")
    parser.add_argument("--latency-threshold-ms", type=float, default=100.0, help="Threshold for high-latency rate.")
    parser.add_argument("--fixed-expected-packets", type=int, default=1200, help="Use a fixed expected packet count for loss rate.")
    parser.add_argument("--bins", type=int, default=50, help="Histogram bins.")
    args = parser.parse_args()

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        results = [load_metrics(path, latency_threshold_ms=args.latency_threshold_ms, fixed_expected_packets=args.fixed_expected_packets) for path in args.input]
        if args.labels is not None:
            for item, label in zip(results, args.labels):
                item["name"] = str(label)

        summary_path = os.path.join(args.output_dir, "summary.csv")
        hist_path = os.path.join(args.output_dir, "latency_distribution_comparison.png")
        box_path = os.path.join(args.output_dir, "box_violin_comparison.png")
        bar_path = os.path.join(args.output_dir, "metric_three_bars_comparison.png")
        scatter_path = os.path.join(args.output_dir, "latency_vs_packet_index.png")

        write_summary(results, summary_path)
        plot_overlaid_histogram(results, hist_path, bins=args.bins, latency_threshold_ms=args.latency_threshold_ms)
        plot_box_violin(results, box_path)
        plot_metric_bars(results, bar_path)
        plot_packet_index_scatter(results, scatter_path)

        print("Saved:")
        print(summary_path)
        print(hist_path)
        print(box_path)
        print(bar_path)
        print(scatter_path)
        for item in results:
            print(
                f"{item['name']}: samples={item['samples']}, received={item['received_packets']}, expected={item['expected_packets']}, "
                f"loss={item['packet_loss_rate']:.2f}%, mean={item['mean_latency']:.2f} ms, median={item['median_latency']:.2f} ms, "
                f"p95={item['p95_latency']:.2f} ms, p99={item['p99_latency']:.2f} ms, high>={args.latency_threshold_ms:g}ms={item['high_latency_rate']:.2f}%"
            )
    except Exception as error:
        print(f"[Error] {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()