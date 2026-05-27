#!/usr/bin/env python3
import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime
from statistics import fmean

PAYLOADS = [
    ("256b", 256),
    ("16kb", 16 * 1024),
    ("256kb", 256 * 1024),
    ("1mb", 1 * 1024 * 1024),
    ("4mb", 4 * 1024 * 1024),
]


def _normalize_col(name):
    return "".join(ch for ch in str(name).strip().lower() if ch.isalnum())


def _find_columns(headers):
    normalized = {_normalize_col(col): col for col in headers}
    d_s_col = None
    d_ns_col = None
    sn_col = None

    for key, original in normalized.items():
        if d_s_col is None and (key == "ds" or key.startswith("ds") or "delayseconds" in key):
            d_s_col = original
        if d_ns_col is None and (key == "dns" or key.startswith("dns") or "delaynanoseconds" in key):
            d_ns_col = original
        if sn_col is None and (key in {"sn", "seq", "sequence", "sequencenumber", "packetid", "id"} or key.startswith(("sn", "seq", "id"))):
            sn_col = original

    return d_s_col, d_ns_col, sn_col


def analyze_csv(csv_path, expected_packets):
    if not os.path.exists(csv_path):
        return None, f"missing csv: {csv_path}"

    latencies = []
    seqs = []

    with open(csv_path, "r", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return None, "csv has no header"
        d_s_col, d_ns_col, sn_col = _find_columns(reader.fieldnames)
        if d_s_col is None or d_ns_col is None:
            return None, f"cannot find delay columns in {reader.fieldnames}"

        for row in reader:
            try:
                d_s = float(row.get(d_s_col, ""))
                d_ns = float(row.get(d_ns_col, ""))
            except (TypeError, ValueError):
                continue
            latency_ms = d_s * 1000.0 + d_ns / 1_000_000.0
            if latency_ms >= 0:
                latencies.append(latency_ms)

            if sn_col is not None:
                try:
                    seqs.append(int(float(row.get(sn_col, ""))))
                except (TypeError, ValueError):
                    pass

    if not latencies:
        return None, "no valid latency samples"

    received = len(set(seqs)) if seqs else len(latencies)
    expected = int(expected_packets) if expected_packets is not None else received
    if expected <= 0:
        expected = received

    loss_rate = max(0.0, (expected - received) / expected * 100.0)

    return {
        "samples": len(latencies),
        "mean_latency_ms": fmean(latencies),
        "received_packets": received,
        "expected_packets": expected,
        "loss_rate_percent": loss_rate,
        "seq_min": min(seqs) if seqs else None,
        "seq_max": max(seqs) if seqs else None,
    }, None


def run_publisher(args, payload_label, payload_bytes, output_dir):
    log_file = os.path.join(output_dir, f"publisher_{payload_label}.csv")
    cmd = [
        "ros2",
        "run",
        "dds_study",
        "publisher",
        "--ros-args",
        "-p",
        f"ip_addr:={args.ip_addr}",
        "-p",
        f"publisher_topic:={args.publisher_topic}",
        "-p",
        f"port:={args.port}",
        "-p",
        f"payload_bytes:={payload_bytes}",
        "-p",
        f"history:={args.history}",
        "-p",
        f"packets_to_send:={args.packets_to_send}",
        "-p",
        f"publisher_period_ms:={args.publisher_period_ms}",
        "-p",
        f"file_name:={log_file}",
    ]
    if args.best_effort:
        cmd.extend(["-p", "use_default_reliability:=false"])

    print(f"\n=== running payload {payload_label} ({payload_bytes} bytes) ===")
    start_time = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start_time
    if result.returncode != 0:
        print(f"publisher exited with code {result.returncode}")

    metrics, err = analyze_csv(log_file, args.packets_to_send + 1)
    if err:
        print(f"analysis warning: {err}")

    return {
        "payload_label": payload_label,
        "payload_bytes": payload_bytes,
        "log_file": log_file,
        "return_code": result.returncode,
        "elapsed_sec": elapsed,
        "metrics": metrics,
        "error": err,
    }


def write_summary(results, output_dir):
    summary_path = os.path.join(output_dir, "summary.csv")
    with open(summary_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "payload_label",
            "payload_bytes",
            "mean_latency_ms",
            "loss_rate_percent",
            "samples",
            "received_packets",
            "expected_packets",
            "seq_min",
            "seq_max",
            "return_code",
            "elapsed_sec",
            "log_file",
            "error",
        ])
        for item in results:
            metrics = item.get("metrics") or {}
            writer.writerow([
                item["payload_label"],
                item["payload_bytes"],
                metrics.get("mean_latency_ms"),
                metrics.get("loss_rate_percent"),
                metrics.get("samples"),
                metrics.get("received_packets"),
                metrics.get("expected_packets"),
                metrics.get("seq_min"),
                metrics.get("seq_max"),
                item["return_code"],
                f"{item['elapsed_sec']:.2f}",
                item["log_file"],
                item.get("error"),
            ])

    print(f"\nsummary written to: {summary_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run publisher for multiple payload sizes and summarize results")
    parser.add_argument("--ip-addr", dest="ip_addr", default="172.20.10.2")
    parser.add_argument("--publisher-topic", dest="publisher_topic", default="/rel")
    parser.add_argument("--port", type=int, default=2077)
    parser.add_argument("--history", type=int, default=10)
    parser.add_argument("--packets-to-send", type=int, default=500)
    parser.add_argument("--publisher-period-ms", type=int, default=50)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--best-effort", action="store_true", help="Use best effort reliability for this run")
    return parser.parse_args()


def main():
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.join(os.path.dirname(__file__), "..", "experiment_outputs")
    output_dir = args.output_dir or os.path.join(base_dir, f"payload_sweep_{stamp}")
    os.makedirs(output_dir, exist_ok=True)

    results = []
    for label, size in PAYLOADS:
        results.append(run_publisher(args, label, size, output_dir))

    write_summary(results, output_dir)


if __name__ == "__main__":
    main()
