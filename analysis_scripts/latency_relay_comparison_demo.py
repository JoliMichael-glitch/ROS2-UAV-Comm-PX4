#!/usr/bin/env python3
"""
Generate simulated latency datasets and plot publication-quality comparison figures:
1) Joint boxplot (log-scale y-axis)
2) Overlaid KDE + histogram

Dataset A: No Relay (Single-hop NLoS), severe long-tail
Dataset B: With Relay (Multi-hop), stable around ~55 ms with sparse outliers
"""

import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import seaborn as sns


def simulate_no_relay(n=1000, seed=42):
    """Severely right-skewed latency with heavy long-tail up to ~1600 ms."""
    rng = np.random.default_rng(seed)

    # Main body around 50-200 ms
    main_count = int(n * 0.82)
    main = rng.lognormal(mean=np.log(95.0), sigma=0.45, size=main_count)

    # Long-tail component mostly in 200-1600 ms
    tail_count = n - main_count
    tail = rng.lognormal(mean=np.log(360.0), sigma=0.85, size=tail_count)

    data = np.concatenate([main, tail])
    data = np.clip(data, 20.0, 1600.0)
    rng.shuffle(data)
    return data


def simulate_with_relay(n=1000, seed=43):
    """Highly stable latency near ~55.2 ms plus sparse outliers (P99 ~350 ms)."""
    rng = np.random.default_rng(seed)

    # Stable core: narrow IQR roughly 40-60 ms
    base_count = int(n * 0.985)
    base = rng.normal(loc=55.2, scale=7.0, size=base_count)
    base = np.clip(base, 30.0, 90.0)

    # Sparse outliers: a few high-latency events
    outlier_count = n - base_count
    outliers = rng.lognormal(mean=np.log(180.0), sigma=0.55, size=outlier_count)
    outliers = np.clip(outliers, 100.0, 380.0)

    data = np.concatenate([base, outliers])
    rng.shuffle(data)
    return data


def compute_loss_rate(expected_count, received_count):
    """Compute packet loss percentage and always return a numeric value."""
    expected = int(expected_count)
    received = int(received_count)
    if expected <= 0:
        return 0.0
    return max(0.0, (expected - received) / expected * 100.0)


def apply_random_drop(data, drop_rate, seed):
    """Drop a configurable fraction of packets to simulate packet loss."""
    if drop_rate <= 0.0:
        return data
    if drop_rate >= 1.0:
        return np.array([], dtype=float)

    rng = np.random.default_rng(seed)
    keep_mask = rng.random(len(data)) >= float(drop_rate)
    return data[keep_mask]


def plot_comparison(no_relay, with_relay, output_path, expected_no_relay, expected_with_relay):
    sns.set_theme(style="whitegrid")

    # Publication-friendly font sizes
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.titlesize": 15,
            "axes.labelsize": 13,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "legend.fontsize": 12,
        }
    )

    color_a = "#D95F5F"  # red-ish for control
    color_b = "#2C7FB8"  # blue-ish for relay

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=160)

    # --- Subplot 1: Joint boxplot ---
    df_box = pd.DataFrame(
        {
            "Topology": ["No Relay"] * len(no_relay) + ["With Relay"] * len(with_relay),
            "Latency (ms)": np.concatenate([no_relay, with_relay]),
        }
    )

    sns.boxplot(
        data=df_box,
        x="Topology",
        y="Latency (ms)",
        palette=[color_a, color_b],
        showfliers=True,
        width=0.55,
        linewidth=1.2,
        order=["No Relay", "With Relay"],
        ax=axes[0],
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Latency Distribution by Topology (Boxplot)")
    axes[0].set_xlabel("Network Topology")
    axes[0].set_ylabel("Latency (ms, log scale)")
    axes[0].tick_params(axis="x", rotation=0)

    # --- Subplot 2: Overlaid KDE + histogram ---
    bins = np.linspace(0, 1000, 60)
    sns.histplot(
        no_relay,
        bins=bins,
        stat="density",
        color=color_a,
        alpha=0.35,
        kde=True,
        line_kws={"linewidth": 2},
        ax=axes[1],
    )
    sns.histplot(
        with_relay,
        bins=bins,
        stat="density",
        color=color_b,
        alpha=0.35,
        kde=True,
        line_kws={"linewidth": 2},
        ax=axes[1],
    )
    axes[1].set_xlim(0, 1000)
    axes[1].set_title("Overlaid Latency Density")
    axes[1].set_xlabel("Latency (ms)")
    axes[1].set_ylabel("Density")
    if axes[1].get_legend() is not None:
        axes[1].get_legend().remove()

    no_relay_loss = compute_loss_rate(expected_no_relay, len(no_relay))
    with_relay_loss = compute_loss_rate(expected_with_relay, len(with_relay))

    # Place key statistics in a safe corner with semi-transparent background.
    stats_text = (
        f"No Relay: Samples={len(no_relay)}, Packet Loss={no_relay_loss:.2f}%, P99={np.percentile(no_relay, 99):.1f} ms\n"
        f"With Relay: Samples={len(with_relay)}, Packet Loss={with_relay_loss:.2f}%, P99={np.percentile(with_relay, 99):.1f} ms"
    )
    axes[1].text(
        0.98,
        0.98,
        stats_text,
        transform=axes[1].transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8, edgecolor="none"),
    )

    # Global legend shared by both subplots.
    legend_handles = [
        Patch(facecolor=color_a, edgecolor="none", label="No Relay (Single-hop NLoS)"),
        Patch(facecolor=color_b, edgecolor="none", label="With Relay (Multi-hop)"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.03),
        ncol=2,
        frameon=False,
    )

    # Global title and spacing
    fig.suptitle("Single-hop NLoS vs Multi-hop Relay: Latency Comparison", fontsize=16, y=1.08)
    fig.subplots_adjust(top=0.80)
    plt.tight_layout(rect=[0, 0, 1, 0.88])

    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def print_summary(no_relay, with_relay):
    def describe(x):
        return {
            "mean": float(np.mean(x)),
            "median": float(np.median(x)),
            "p90": float(np.percentile(x, 90)),
            "p99": float(np.percentile(x, 99)),
            "max": float(np.max(x)),
        }

    a = describe(no_relay)
    b = describe(with_relay)

    print("No Relay (Single-hop NLoS):")
    print(f"  mean={a['mean']:.2f} ms, median={a['median']:.2f} ms, p90={a['p90']:.2f} ms, p99={a['p99']:.2f} ms, max={a['max']:.2f} ms")
    print("With Relay (Multi-hop):")
    print(f"  mean={b['mean']:.2f} ms, median={b['median']:.2f} ms, p90={b['p90']:.2f} ms, p99={b['p99']:.2f} ms, max={b['max']:.2f} ms")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate and plot latency comparison: No Relay vs With Relay"
    )
    parser.add_argument("--n", type=int, default=1000, help="Number of samples per dataset")
    parser.add_argument(
        "-o",
        "--output",
        default="relay_latency_comparison.png",
        help="Output figure path",
    )
    parser.add_argument(
        "--drop-rate-no-relay",
        type=float,
        default=0.0,
        help="Simulated packet drop rate for No Relay dataset in [0,1).",
    )
    parser.add_argument(
        "--drop-rate-with-relay",
        type=float,
        default=0.0,
        help="Simulated packet drop rate for With Relay dataset in [0,1).",
    )
    args = parser.parse_args()

    if not (0.0 <= args.drop_rate_no_relay < 1.0):
        raise ValueError("--drop-rate-no-relay must be in [0, 1)")
    if not (0.0 <= args.drop_rate_with_relay < 1.0):
        raise ValueError("--drop-rate-with-relay must be in [0, 1)")

    no_relay_raw = simulate_no_relay(n=args.n, seed=42)
    with_relay_raw = simulate_with_relay(n=args.n, seed=43)
    no_relay = apply_random_drop(no_relay_raw, args.drop_rate_no_relay, seed=4201)
    with_relay = apply_random_drop(with_relay_raw, args.drop_rate_with_relay, seed=4301)

    plot_comparison(
        no_relay,
        with_relay,
        output_path=args.output,
        expected_no_relay=args.n,
        expected_with_relay=args.n,
    )
    print_summary(no_relay, with_relay)
    print(
        "Packet loss: "
        f"No Relay={compute_loss_rate(args.n, len(no_relay)):.2f}%, "
        f"With Relay={compute_loss_rate(args.n, len(with_relay)):.2f}%"
    )
    print(f"Saved figure: {args.output}")


if __name__ == "__main__":
    main()
