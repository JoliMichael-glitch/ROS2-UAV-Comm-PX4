#!/usr/bin/env python3
import argparse
import time
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def pick_default_file():
    # Prefer one-way log from C node, then fallback to legacy names.
    candidates = [
        'oneway_c.csv',
        'publisher_log.csv',
        'publisher.csv',
    ]
    for file_name in candidates:
        if os.path.exists(file_name):
            return file_name
    return candidates[0]


def load_latency_columns(df):
    # New one-way format from C node.
    if 'delay_ms' in df.columns and 'id' in df.columns:
        return df['delay_ms'].to_numpy(), df['id'].to_numpy()

    # Legacy feedback format.
    if 'd_ns(Delay Nanoseconds)' in df.columns and 'SN(Sequence Number)' in df.columns:
        return (df['d_ns(Delay Nanoseconds)'] / 1e6).to_numpy(), df['SN(Sequence Number)'].to_numpy()

    raise ValueError(f'Unknown CSV schema, columns={list(df.columns)}')


def run_analysis(file_name):
    if not os.path.exists(file_name):
        print(f"错误：未找到数据文件 {file_name}")
        return

    try:
        # Auto-detect delimiter to support both old and new logs.
        df = pd.read_csv(file_name, sep=None, engine='python')
        latencies, sns_list = load_latency_columns(df)
    except Exception as e:
        print(f"数据处理出错: {e}")
        return

    if len(latencies) == 0:
        print("数据为空，暂不生成报告")
        return

    actual_received = len(latencies)
    mean_lat = np.mean(latencies)
    median_lat = np.median(latencies)
    std_dev = np.std(latencies)
    p99_lat = np.percentile(latencies, 99)
    max_lat = np.max(latencies)
    min_lat = np.min(latencies)
    
    total_expected = np.max(sns_list) - np.min(sns_list) + 1
    if total_expected <= 0:
        total_expected = actual_received
    loss_rate = (1 - actual_received / total_expected) * 100

    print("\n" + "="*45)
    print("       UAV 通信链路性能分析报告 (最终版)")
    print("="*45)
    print(f"样本总数: {actual_received} packets")
    print(f"平均延迟 (Mean):   {mean_lat:.3f} ms")
    print(f"中位数 (Median):   {median_lat:.3f} ms")
    print(f"延迟抖动 (Jitter): {std_dev:.3f} ms")
    print(f"99% 分位数 (P99):  {p99_lat:.3f} ms")
    print(f"最高延迟 (Max):    {max_lat:.3f} ms")
    print(f"最低延迟 (Min):    {min_lat:.3f} ms")
    print(f"丢包率 (Loss Rate): {loss_rate:.2f} %")
    print("="*45)

    try:
        plt.figure(figsize=(10, 6))
        plt.hist(latencies, bins=30, color='skyblue', edgecolor='black', alpha=0.7)
        plt.axvline(p99_lat, color='red', linestyle='--', label=f'P99: {p99_lat:.2f}ms')
        plt.axvline(mean_lat, color='green', linestyle='-', label=f'Mean: {mean_lat:.2f}ms')
        plt.title('Communication Latency Distribution (Histogram)')
        plt.xlabel('Latency (ms)')
        plt.ylabel('Packet Count')
        plt.legend()
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.savefig('latency_histogram.png')
        print("已生成直方图: latency_histogram.png")

        plt.figure(figsize=(6, 8))
        plt.boxplot(latencies, patch_artist=True, boxprops=dict(facecolor='lightgreen'))
        plt.title('Latency Consistency Analysis (Boxplot)')
        plt.ylabel('Latency (ms)')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.savefig('latency_boxplot.png')
        print("已生成箱线图: latency_boxplot.png")

        print("\n[方案 B 彻底成功] 图片已生成。")
        plt.show()
    except Exception as e:
        print(f"\n绘图过程出错: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description='Analyze one-way/legacy latency logs')
    parser.add_argument('--input', default=pick_default_file(), help='CSV file path')
    parser.add_argument('--watch', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=float, default=10.0, help='Watch interval seconds')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.watch:
        while True:
            run_analysis(args.input)
            time.sleep(max(args.interval, 1.0))
    else:
        run_analysis(args.input)
