import argparse
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def load_latency_ms(csv_path):
    df = pd.read_csv(csv_path)
    cols = set(df.columns)

    alt_map = {
        "SN(Sequence Number)": "id",
        "TX_s(Transmit Timestamp Seconds)": "TX_s",
        "TX_ns(Transmit Timestamp Nanoseconds)": "TX_ns",
        "RX_s(Receive Timestamp Seconds)": "RX_s",
        "RX_ns(Receive Timestamp Nanoseconds)": "RX_ns",
        "d_s(Delay Seconds)": "d_s",
        "d_ns(Delay Nanoseconds)": "d_ns",
    }
    rename_cols = {col: alt_map[col] for col in df.columns if col in alt_map}
    if rename_cols:
        df = df.rename(columns=rename_cols)
        cols = set(df.columns)

    if {"d_s", "d_ns"}.issubset(cols):
        d_s = _to_numeric(df["d_s"]).fillna(0)
        d_ns = _to_numeric(df["d_ns"]).fillna(0)
        latency_ns = d_s * 1e9 + d_ns
    elif {"TX_s", "TX_ns", "RX_s", "RX_ns"}.issubset(cols):
        tx_s = _to_numeric(df["TX_s"]).fillna(0)
        tx_ns = _to_numeric(df["TX_ns"]).fillna(0)
        rx_s = _to_numeric(df["RX_s"]).fillna(0)
        rx_ns = _to_numeric(df["RX_ns"]).fillna(0)
        tx_ns_total = tx_s * 1e9 + tx_ns
        rx_ns_total = rx_s * 1e9 + rx_ns
        latency_ns = rx_ns_total - tx_ns_total
    else:
        raise ValueError("CSV missing latency columns. Need d_s/d_ns or TX/RX columns.")

    latency_ms = latency_ns / 1e6
    latency_ms = latency_ms.replace([np.inf, -np.inf], np.nan).dropna()
    return df, latency_ms


def compute_packet_loss(df):
    if "id" not in df.columns:
        return None
    ids = _to_numeric(df["id"]).dropna().astype(int)
    if ids.empty:
        return None
    psent = int(ids.max() - ids.min() + 1)
    precv = int(ids.nunique())
    if psent <= 0:
        return None
    return (psent - precv) / psent * 100.0


def kde_counts(x, grid, bw):
    diff = (grid[:, None] - x[None, :]) / bw
    kernel = np.exp(-0.5 * diff ** 2) / np.sqrt(2 * np.pi)
    density = kernel.mean(axis=1) / bw
    return density


def apply_style():
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#4a4a4a",
            "axes.labelcolor": "#2f2f2f",
            "xtick.color": "#2f2f2f",
            "ytick.color": "#2f2f2f",
            "text.color": "#2f2f2f",
        }
    )


def plot_histogram_kde(
    values,
    metrics,
    title,
    output_path,
    show_table=True,
    show_metrics_text=False,
    x_start_zero=False,
):
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    fig.set_dpi(300)

    bins = 40
    counts, bin_edges, _ = ax.hist(
        values,
        bins=bins,
        color="#7fb7b5",
        edgecolor="white",
        alpha=0.9,
    )
    bin_width = bin_edges[1] - bin_edges[0]
    x_min = values.min()
    x_max = max(values.max(), 120)
    grid = np.linspace(x_min, x_max, 300)
    bw = 1.06 * values.std(ddof=0) * values.size ** (-1 / 5)
    if bw > 0:
        density = kde_counts(values, grid, bw)
        ax.plot(grid, density * values.size * bin_width, color="#4f8f8e", linewidth=2)

    ax.axvline(100, color="#d9534f", linestyle="--", linewidth=2)
    ax.text(
        100,
        ax.get_ylim()[1] * 0.92,
        "100ms Threshold",
        color="#d9534f",
        ha="left",
        va="top",
        fontsize=9,
    )

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Latency (ms)", fontweight="bold")
    ax.set_ylabel("Count", fontweight="bold")
    ax.grid(True, color="#e6e6e6", linewidth=0.6)
    if x_start_zero:
        ax.set_xlim(left=0)

    if show_table:
        table_data = [
            ["Samples", f"{metrics['samples']}"] ,
            ["Mean Latency", f"{metrics['mean_latency']:.2f} ms"],
            ["Packet Loss Rate", metrics.get("packet_loss", "N/A")],
            ["High-Latency Rate (>100 ms)", f"{metrics['high_latency']:.2f}%"],
        ]
        if metrics.get("packet_loss") != "N/A":
            table_data[2][1] = f"{metrics['packet_loss']:.2f}%"

        table = ax.table(
            cellText=table_data,
            colLabels=["Metric", "Value"],
            colLoc="left",
            cellLoc="left",
            bbox=[0.58, 0.6, 0.4, 0.33],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor("#4a4a4a")
            cell.set_linewidth(0.6)
            if row == 0:
                cell.set_facecolor("#f5f5f5")
                cell.set_text_props(weight="bold")

    if show_metrics_text:
        packet_loss_text = "N/A"
        if metrics.get("packet_loss") != "N/A":
            packet_loss_text = f"{metrics['packet_loss']:.2f}%"
        metrics_text = (
            f"Samples: {metrics['samples']}\n"
            f"Mean Latency: {metrics['mean_latency']:.2f} ms\n"
            f"Packet Loss Rate: {packet_loss_text}\n"
            f"High-Latency Rate(>100 ms): {metrics['high_latency']:.2f}%"
        )
        ax.text(
            0.98,
            0.98,
            metrics_text,
            ha="right",
            va="top",
            transform=ax.transAxes,
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.85),
        )

    fig.savefig(output_path, dpi=300, bbox_inches="tight")


def plot_jitter_series(jitter_series, baseline, title, output_path, x_start_zero=False, y_start_zero=False):
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    fig.set_dpi(300)

    x = np.arange(1, jitter_series.size + 1)
    ax.plot(x, jitter_series, color="#2c7fb8", linewidth=1.2)
    ax.axhline(baseline, color="#f0ad4e", linestyle="--", linewidth=2)

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Sample Sequence Number", fontweight="bold")
    ax.set_ylabel("Jitter [ms]", fontweight="bold")
    ax.grid(True, color="#e6e6e6", linewidth=0.6)

    if x_start_zero:
        ax.set_xlim(left=0)
    if y_start_zero:
        ax.set_ylim(bottom=0)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")


def plot_box_plot(values, title, output_path, x_start_zero=False):
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    fig.set_dpi(300)

    ax.boxplot(
        values,
        vert=False,
        widths=0.6,
        patch_artist=True,
        boxprops=dict(facecolor="#4682b4", color="#2f4f4f"),
        medianprops=dict(color="#f0ad4e", linewidth=2),
        whiskerprops=dict(color="#2f4f4f"),
        capprops=dict(color="#2f4f4f"),
        flierprops=dict(
            marker="o",
            markersize=4,
            markerfacecolor="none",
            markeredgecolor="#2f4f4f",
            linestyle="none",
        ),
    )
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Latency (ms)", fontweight="bold")
    ax.set_yticks([])
    ax.grid(True, axis="x", color="#e6e6e6", linewidth=0.6)

    if x_start_zero:
        ax.set_xlim(left=0)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")


def plot_latency_report(
    csv_path,
    output_dir,
    prefix=None,
    show_table=True,
    show_metrics_text=False,
    x_start_zero=False,
    y_start_zero=False,
):
    df, latency_ms = load_latency_ms(csv_path)
    values = latency_ms.to_numpy()

    if values.size == 0:
        raise ValueError("No valid latency samples found.")

    n = values.size
    mean_latency = values.mean()
    jitter = np.sqrt(np.mean((values - mean_latency) ** 2))
    packet_loss = compute_packet_loss(df)
    high_latency_rate = (values > 100).mean() * 100.0

    title = os.path.splitext(os.path.basename(csv_path))[0]
    if not prefix:
        prefix = title

    os.makedirs(output_dir, exist_ok=True)

    metrics = {
        "samples": n,
        "mean_latency": mean_latency,
        "packet_loss": packet_loss if packet_loss is not None else "N/A",
        "high_latency": high_latency_rate,
    }

    jitter_series = np.abs(values - mean_latency)

    histogram_path = os.path.join(output_dir, f"{prefix}_hist_kde.png")
    jitter_path = os.path.join(output_dir, f"{prefix}_jitter.png")
    box_path = os.path.join(output_dir, f"{prefix}_box.png")

    apply_style()
    plot_histogram_kde(
        values,
        metrics,
        title,
        histogram_path,
        show_table=show_table,
        show_metrics_text=show_metrics_text,
        x_start_zero=x_start_zero,
    )
    plot_jitter_series(
        jitter_series,
        jitter,
        f"Jitter (Std Dev): {jitter:.2f} ms",
        jitter_path,
        x_start_zero=x_start_zero,
        y_start_zero=y_start_zero,
    )
    plot_box_plot(values, "Latency Box Plot", box_path, x_start_zero=x_start_zero)

    return histogram_path, jitter_path, box_path


def main():
    parser = argparse.ArgumentParser(description="Plot latency histogram, jitter, and box plot.")
    parser.add_argument("--csv", required=True, help="Input CSV file path")
    parser.add_argument("--out-dir", required=True, help="Output directory for images")
    parser.add_argument("--prefix", default=None, help="Output file prefix")
    parser.add_argument(
        "--no-table",
        action="store_true",
        help="Disable summary table on the histogram.",
    )
    parser.add_argument(
        "--metrics-text",
        action="store_true",
        help="Show summary metrics as a text box on the histogram.",
    )
    parser.add_argument(
        "--x-start-zero",
        action="store_true",
        help="Force x-axis to start at zero.",
    )
    parser.add_argument(
        "--y-start-zero",
        action="store_true",
        help="Force y-axis to start at zero (jitter plot).",
    )
    args = parser.parse_args()

    hist_path, jitter_path, box_path = plot_latency_report(
        args.csv,
        args.out_dir,
        args.prefix,
        show_table=not args.no_table,
        show_metrics_text=args.metrics_text,
        x_start_zero=args.x_start_zero,
        y_start_zero=args.y_start_zero,
    )
    print(f"Saved: {hist_path}")
    print(f"Saved: {jitter_path}")
    print(f"Saved: {box_path}")


if __name__ == "__main__":
    main()
