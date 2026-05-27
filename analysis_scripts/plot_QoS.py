#!/usr/bin/env python3
"""Plot QoS latency comparison under gradient payloads."""

import os

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


BEST_EFFORT_CSV = r"C:\Users\MC\Desktop\实验数据\test9\2\summary_R2C_BESTEFFORT.csv"
RELIABLE_CSV = r"C:\Users\MC\Desktop\实验数据\test9\2\summary_R2C_RELIABLE.csv"
OUTPUT_PATH = "qos_latency_comparison.png"
LOSS_OUTPUT_PATH = "qos_loss_rate_comparison.png"
LATENCY_INSET_OUTPUT_PATH = "qos_latency_inset.png"
LATENCY_LOGLOG_OUTPUT_PATH = "qos_latency_loglog.png"
COMBO_OUTPUT_PATH = "qos_latency_loss_combo.png"


def _load_font_prop(font_name, font_paths):
    for font_path in font_paths:
        if os.path.exists(font_path):
            font_manager.fontManager.addfont(font_path)
            return FontProperties(fname=font_path)

    return FontProperties(family=font_name)


def _apply_gb_style():
    plt.rcParams.update(
        {
            "font.family": "SimSun",
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "mathtext.fontset": "stix",
            "mathtext.rm": "Times New Roman",
            "axes.unicode_minus": False,
        }
    )


def _load_latency(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required_cols = {"payload_bytes", "mean_latency_ms"}
    if not required_cols.issubset(df.columns):
        raise ValueError(
            f"CSV missing required columns {sorted(required_cols)}. Found: {list(df.columns)}"
        )

    x = df["payload_bytes"].astype(float).to_list()
    y = df["mean_latency_ms"].astype(float).to_list()
    return x, y


def _filter_payloads(x_values, y_values, payloads):
    payload_map = {int(x): y for x, y in zip(x_values, y_values)}
    filtered_x = []
    filtered_y = []
    for payload in payloads:
        if int(payload) in payload_map:
            filtered_x.append(payload)
            filtered_y.append(payload_map[int(payload)])
    return filtered_x, filtered_y


def _load_loss_rate(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required_cols = {"payload_bytes", "loss_rate_percent"}
    if not required_cols.issubset(df.columns):
        raise ValueError(
            f"CSV missing required columns {sorted(required_cols)}. Found: {list(df.columns)}"
        )

    x = df["payload_bytes"].astype(float).to_list()
    y = df["loss_rate_percent"].astype(float).to_list()
    return x, y


def plot_qos_latency(best_effort_csv, reliable_csv, output_path):
    _apply_gb_style()

    x_best, y_best = _load_latency(best_effort_csv)
    x_rel, y_rel = _load_latency(reliable_csv)

    simsun_prop = _load_font_prop(
        "SimSun",
        [r"C:\\Windows\\Fonts\\simsun.ttc", r"C:\\Windows\\Fonts\\simsun.ttf"],
    )
    times_prop = _load_font_prop(
        "Times New Roman",
        [r"C:\\Windows\\Fonts\\times.ttf", r"C:\\Windows\\Fonts\\timesbd.ttf"],
    )

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.plot(
        x_best,
        y_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=7,
        linewidth=1.6,
        label="尽力而为策略 ($\\mathrm{Best\\ Effort}$)",
    )
    ax.plot(
        x_rel,
        y_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=7,
        linewidth=1.6,
        label="可靠策略 ($\\mathrm{Reliable}$)",
    )

    ax.set_xscale("log")
    ax.set_xticks([256, 16384, 262144, 1048576, 4194304])
    ax.set_xticklabels(["256b", "16kb", "256kb", "1mb", "4mb"])

    ax.set_xlabel(r"有效载荷 $L$", fontproperties=simsun_prop)
    ax.set_ylabel(r"端到端平均延迟 $D\,(\mathrm{ms})$", fontproperties=simsun_prop)
    ax.set_title("QoS 策略在梯度负载下的通信延迟", pad=8, fontproperties=simsun_prop)

    ax.grid(True, which="both", color="gray", linestyle=":", alpha=0.5)
    ax.legend(loc="upper left", frameon=True, framealpha=0.7, prop=simsun_prop)

    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontproperties(times_prop)

    fig.tight_layout()
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_qos_latency_inset(best_effort_csv, reliable_csv, output_path):
    _apply_gb_style()

    x_best, y_best = _load_latency(best_effort_csv)
    x_rel, y_rel = _load_latency(reliable_csv)
    payloads = [256, 16384, 262144, 1048576, 4194304]
    x_best, y_best = _filter_payloads(x_best, y_best, payloads)
    x_rel, y_rel = _filter_payloads(x_rel, y_rel, payloads)

    simsun_prop = _load_font_prop(
        "SimSun",
        [r"C:\\Windows\\Fonts\\simsun.ttc", r"C:\\Windows\\Fonts\\simsun.ttf"],
    )
    times_prop = _load_font_prop(
        "Times New Roman",
        [r"C:\\Windows\\Fonts\\times.ttf", r"C:\\Windows\\Fonts\\timesbd.ttf"],
    )

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.plot(
        x_best,
        y_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=8,
        markerfacecolor="#1f77b4",
        markeredgewidth=1.5,
        linewidth=2.0,
        label="尽力而为策略 ($\\mathrm{Best\\ Effort}$)",
    )
    ax.plot(
        x_rel,
        y_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=8,
        markerfacecolor="#d62728",
        markeredgewidth=1.5,
        linewidth=2.0,
        label="可靠策略 ($\\mathrm{Reliable}$)",
    )

    ax.set_xscale("log")
    ax.set_xticks([256, 16384, 262144, 1048576, 4194304])
    ax.set_xticklabels(["256B", "16KB", "256KB", "1MB", "4MB"])

    ax.set_xlabel(r"有效载荷 $L$ (Bytes)", fontproperties=simsun_prop)
    ax.set_ylabel(r"端到端平均延迟 $D$ (ms)", fontproperties=simsun_prop)
    ax.set_title("R2C 链路平均延迟", pad=8, fontproperties=simsun_prop, fontweight="bold")

    ax.grid(True, which="both", linestyle=":", alpha=0.4)
    ax.legend(
        loc="lower right",
        frameon=True,
        framealpha=1.0,
        edgecolor="black",
        prop=simsun_prop,
    )

    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontproperties(times_prop)

    axins = inset_axes(ax, width="38%", height="34%", loc="upper left")
    axins.plot(
        x_best,
        y_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=5,
        markerfacecolor="white",
        markeredgewidth=1.2,
        linewidth=1.2,
    )
    axins.plot(
        x_rel,
        y_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=5,
        markerfacecolor="white",
        markeredgewidth=1.2,
        linewidth=1.2,
    )
    axins.set_xscale("log")
    axins.set_xlim(200, 20000)
    axins.set_ylim(0, 100)
    axins.set_title("中低负载区间放大图", fontproperties=simsun_prop, fontsize=10.5)
    axins.grid(True, which="both", linestyle=":", alpha=0.4)

    plt.tight_layout()
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_qos_latency_loglog(best_effort_csv, reliable_csv, output_path):
    _apply_gb_style()

    x_best, y_best = _load_latency(best_effort_csv)
    x_rel, y_rel = _load_latency(reliable_csv)
    payloads = [256, 16384, 262144, 1048576, 4194304]
    x_best, y_best = _filter_payloads(x_best, y_best, payloads)
    x_rel, y_rel = _filter_payloads(x_rel, y_rel, payloads)

    simsun_prop = _load_font_prop(
        "SimSun",
        [r"C:\\Windows\\Fonts\\simsun.ttc", r"C:\\Windows\\Fonts\\simsun.ttf"],
    )
    times_prop = _load_font_prop(
        "Times New Roman",
        [r"C:\\Windows\\Fonts\\times.ttf", r"C:\\Windows\\Fonts\\timesbd.ttf"],
    )

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.plot(
        x_best,
        y_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=7,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=1.6,
        label="尽力而为策略 ($\\mathrm{Best\\ Effort}$)",
    )
    ax.plot(
        x_rel,
        y_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=7,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=1.6,
        label="可靠策略 ($\\mathrm{Reliable}$)",
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([256, 16384, 262144, 1048576, 4194304])
    ax.set_xticklabels(["256b", "16kb", "256kb", "1mb", "4mb"])
    ax.set_ylim(5, 20000)
    ax.set_yticks([10, 100, 1000, 10000])
    ax.set_yticklabels(["10", "100", "1000", "10000"])

    ax.set_xlabel(r"有效载荷 $L$ (Bytes)", fontproperties=simsun_prop)
    ax.set_ylabel(r"端到端平均延迟 $D$ (ms)", fontproperties=simsun_prop)
    ax.set_title("R2C 链路平均延迟", pad=8, fontproperties=simsun_prop, fontweight="bold")

    ax.grid(True, which="major", color="gray", alpha=0.5, linestyle="-", linewidth=0.8)
    ax.grid(True, which="minor", color="lightgray", alpha=0.4, linestyle="--", linewidth=0.5)
    ax.legend(
        loc="upper left",
        frameon=True,
        framealpha=1.0,
        edgecolor="black",
        prop=simsun_prop,
    )

    ax.tick_params(direction="in", which="both", top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(1.5)

    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontproperties(times_prop)

    plt.tight_layout()
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_qos_loss_rate(best_effort_csv, reliable_csv, output_path):
    _apply_gb_style()

    x_best, y_best = _load_loss_rate(best_effort_csv)
    x_rel, y_rel = _load_loss_rate(reliable_csv)

    simsun_prop = _load_font_prop(
        "SimSun",
        [r"C:\\Windows\\Fonts\\simsun.ttc", r"C:\\Windows\\Fonts\\simsun.ttf"],
    )
    times_prop = _load_font_prop(
        "Times New Roman",
        [r"C:\\Windows\\Fonts\\times.ttf", r"C:\\Windows\\Fonts\\timesbd.ttf"],
    )

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.plot(
        x_best,
        y_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=7,
        linewidth=1.6,
        label="尽力而为策略 ($\\mathrm{Best\\ Effort}$)",
    )
    ax.plot(
        x_rel,
        y_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=7,
        linewidth=1.6,
        label="可靠策略 ($\\mathrm{Reliable}$)",
    )

    ax.set_xscale("log")
    ax.set_xticks([256, 16384, 262144, 1048576, 4194304])
    ax.set_xticklabels(["256b", "16kb", "256kb", "1mb", "4mb"])

    ax.set_xlabel(r"有效载荷 $L$", fontproperties=simsun_prop)
    ax.set_ylabel(r"丢包率 $P$ (\%)", fontproperties=simsun_prop)
    ax.set_title("QoS 策略在梯度负载下的丢包率", pad=8, fontproperties=simsun_prop)

    ax.grid(True, which="both", color="gray", linestyle=":", alpha=0.5)
    ax.legend(loc="upper left", frameon=True, framealpha=0.7, prop=simsun_prop)

    for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
        tick_label.set_fontproperties(times_prop)

    fig.tight_layout()
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_latency_loss_combo(output_path):
    _apply_gb_style()

    x_vals = [256, 16384, 262144, 1048576, 4194304]
    x_labels = ["256B", "16KB", "256KB", "1MB", "4MB"]
    latency_best = [10.69, 22.00, 574.86, 1414.35, 11353.30]
    latency_rel = [18.29, 76.81, 586.53, 2047.10, 11872.67]
    loss_best = [1.40, 1.80, 2.99, 5.79, 48.50]
    loss_rel = [0.60, 0.80, 1.20, 3.39, 20.16]

    simsun_prop = _load_font_prop(
        "SimSun",
        [r"C:\\Windows\\Fonts\\simsun.ttc", r"C:\\Windows\\Fonts\\simsun.ttf"],
    )
    times_prop = _load_font_prop(
        "Times New Roman",
        [r"C:\\Windows\\Fonts\\times.ttf", r"C:\\Windows\\Fonts\\timesbd.ttf"],
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8), dpi=300)

    for ax in (ax1, ax2):
        ax.tick_params(direction="in", which="both", top=True, right=True)
        for spine in ax.spines.values():
            spine.set_linewidth(1.5)

    ax1.plot(
        x_vals,
        latency_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.0,
        label="尽力而为策略 ($\\mathrm{Best\\ Effort}$)",
    )
    ax1.plot(
        x_vals,
        latency_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.0,
        label="可靠策略 ($\\mathrm{Reliable}$)",
    )

    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_ylim(5, 25000)
    ax1.set_yticks([10, 100, 1000, 10000])
    ax1.set_yticklabels(["10", "100", "1000", "10000"])
    ax1.set_xticks(x_vals)
    ax1.set_xticklabels(x_labels)
    ax1.set_xlabel(r"有效载荷 $L$", fontproperties=simsun_prop, fontsize=11)
    ax1.set_ylabel(r"平均延迟 $D$ (ms)", fontproperties=simsun_prop, fontsize=11)
    ax1.set_title("(a) R2C 链路端到端平均延迟", fontproperties=simsun_prop, fontsize=12, fontweight="bold", pad=10)
    ax1.grid(True, which="major", color="gray", alpha=0.3, linestyle="-", linewidth=0.8)
    ax1.grid(True, which="minor", color="lightgray", alpha=0.3, linestyle="--", linewidth=0.5)
    ax1.legend(loc="upper left", frameon=True, framealpha=1.0, edgecolor="black", prop=simsun_prop)

    ax2.plot(
        x_vals,
        loss_best,
        color="#1f77b4",
        linestyle="-",
        marker="s",
        markersize=8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.0,
        label="尽力而为策略 ($\\mathrm{Best\\ Effort}$)",
    )
    ax2.plot(
        x_vals,
        loss_rel,
        color="#d62728",
        linestyle="--",
        marker="^",
        markersize=8,
        markerfacecolor="white",
        markeredgewidth=1.5,
        linewidth=2.0,
        label="可靠策略 ($\\mathrm{Reliable}$)",
    )

    ax2.set_xscale("log")
    ax2.set_ylim(0, 55)
    ax2.set_xticks(x_vals)
    ax2.set_xticklabels(x_labels)
    ax2.set_xlabel(r"有效载荷 $L$", fontproperties=simsun_prop, fontsize=11)
    ax2.set_ylabel(r"丢包率 $P$ (%)", fontproperties=simsun_prop, fontsize=11)
    ax2.set_title("(b) R2C 链路数据包丢失率", fontproperties=simsun_prop, fontsize=12, fontweight="bold", pad=10)
    ax2.grid(True, which="major", color="gray", alpha=0.3, linestyle="-", linewidth=0.8)
    ax2.grid(True, which="minor", color="lightgray", alpha=0.3, linestyle="--", linewidth=0.5)
    ax2.legend(loc="upper left", frameon=True, framealpha=1.0, edgecolor="black", prop=simsun_prop)

    for ax in (ax1, ax2):
        for tick_label in ax.get_xticklabels() + ax.get_yticklabels():
            tick_label.set_fontproperties(times_prop)
            tick_label.set_fontsize(10.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    plot_qos_latency(BEST_EFFORT_CSV, RELIABLE_CSV, OUTPUT_PATH)
    plot_qos_loss_rate(BEST_EFFORT_CSV, RELIABLE_CSV, LOSS_OUTPUT_PATH)
    plot_qos_latency_inset(BEST_EFFORT_CSV, RELIABLE_CSV, LATENCY_INSET_OUTPUT_PATH)
    plot_qos_latency_loglog(BEST_EFFORT_CSV, RELIABLE_CSV, LATENCY_LOGLOG_OUTPUT_PATH)
    plot_latency_loss_combo(COMBO_OUTPUT_PATH)
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Saved: {LOSS_OUTPUT_PATH}")
    print(f"Saved: {LATENCY_INSET_OUTPUT_PATH}")
    print(f"Saved: {LATENCY_LOGLOG_OUTPUT_PATH}")
    print(f"Saved: {COMBO_OUTPUT_PATH}")


if __name__ == "__main__":
    main()