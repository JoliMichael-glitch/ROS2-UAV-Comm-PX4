#!/usr/bin/env python3
"""Batch SSH controller for ROS 2 swarm hosts.

Features:
- Start publisher on all or selected hosts (background, with logs)
- Stop publisher processes
- Check publisher process status
- Run custom command on hosts

Usage examples:
  python3 swarm_ssh_controller.py start --config scripts/swarm_hosts.yaml
  python3 swarm_ssh_controller.py status --config scripts/swarm_hosts.yaml
  python3 swarm_ssh_controller.py stop --config scripts/swarm_hosts.yaml
  python3 swarm_ssh_controller.py exec --config scripts/swarm_hosts.yaml --cmd "hostname"
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

try:
    import yaml
except ModuleNotFoundError as exc:
    raise SystemExit("Missing dependency: pyyaml. Install with: pip install pyyaml") from exc


@dataclass
class HostConfig:
    name: str
    host: str
    user: str
    workdir: str
    ros_setup: str
    log_dir: str
    ssh_key: Optional[str]
    ssh_port: int
    env: Dict[str, str]
    publisher_params: Dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control remote ROS 2 hosts over SSH.")
    parser.add_argument("action", choices=["start", "stop", "status", "exec"], help="Action to run")
    parser.add_argument("--config", required=True, help="YAML config path")
    parser.add_argument(
        "--hosts",
        default="all",
        help="Comma-separated host names to target (default: all)",
    )
    parser.add_argument("--parallel", type=int, default=8, help="Parallel SSH workers")
    parser.add_argument("--timeout", type=int, default=30, help="SSH command timeout in seconds")
    parser.add_argument("--cmd", help="Custom command for action=exec")
    parser.add_argument("--build", action="store_true", help="Run colcon build before start")
    parser.add_argument("--dry-run", action="store_true", help="Print commands but do not execute")
    return parser.parse_args()


def normalize_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return str(value)


def build_ros_args(params: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for key, value in params.items():
        if value is None:
            continue
        val = normalize_value(value)
        chunks.append(f"-p {shlex.quote(str(key))}:={shlex.quote(val)}")
    return " ".join(chunks)


def load_hosts(config_path: str, selected_names: str) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")

    defaults: Dict[str, Any] = data.get("defaults", {}) or {}
    publisher: Dict[str, Any] = data.get("publisher", {}) or {}
    hosts = data.get("hosts", [])
    if not hosts:
        raise ValueError("No hosts found in config")

    selected_set = None
    if selected_names.strip().lower() != "all":
        selected_set = {h.strip() for h in selected_names.split(",") if h.strip()}

    parsed: List[HostConfig] = []
    for item in hosts:
        if not isinstance(item, dict):
            raise ValueError("Each host entry must be a mapping")

        name = str(item["name"])
        if selected_set and name not in selected_set:
            continue

        host = str(item["host"])
        user = str(item.get("user", defaults.get("user", "root")))
        workdir = str(item.get("workdir", defaults.get("workdir", "~")))
        ros_setup = str(
            item.get(
                "ros_setup",
                defaults.get("ros_setup", "/opt/ros/humble/setup.bash"),
            )
        )
        log_dir = str(item.get("log_dir", defaults.get("log_dir", "~/dds_logs")))
        ssh_key = item.get("ssh_key", defaults.get("ssh_key"))
        ssh_port = int(item.get("ssh_port", defaults.get("ssh_port", 22)))

        base_env: Dict[str, str] = dict(defaults.get("env", {}) or {})
        base_env.update(item.get("env", {}) or {})

        params: Dict[str, Any] = dict(publisher.get("params", {}) or {})
        params.update(item.get("publisher_params", {}) or {})

        if "ip_addr" not in params:
            params["ip_addr"] = host

        parsed.append(
            HostConfig(
                name=name,
                host=host,
                user=user,
                workdir=workdir,
                ros_setup=ros_setup,
                log_dir=log_dir,
                ssh_key=str(ssh_key) if ssh_key else None,
                ssh_port=ssh_port,
                env=base_env,
                publisher_params=params,
            )
        )

    if not parsed:
        raise ValueError("No hosts matched --hosts filter")

    return {
        "defaults": defaults,
        "publisher": publisher,
        "hosts": parsed,
    }


def to_env_prefix(env: Dict[str, str]) -> str:
    if not env:
        return ""
    segments = [f"export {k}={shlex.quote(str(v))}" for k, v in env.items()]
    return " && ".join(segments)


def build_start_command(host: HostConfig, publisher_cfg: Dict[str, Any], do_build: bool) -> str:
    package = str(publisher_cfg.get("package", "dds_study"))
    executable = str(publisher_cfg.get("executable", "publisher"))

    ros_args = build_ros_args(host.publisher_params)
    ros_cmd = f"ros2 run {shlex.quote(package)} {shlex.quote(executable)} --ros-args {ros_args}".strip()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = str(PurePosixPath(host.log_dir) / f"{host.name}_publisher_{stamp}.log")

    setup = (
        f"mkdir -p {shlex.quote(host.log_dir)} && "
        f"cd {shlex.quote(host.workdir)} && "
        f"source {shlex.quote(host.ros_setup)}"
    )
    env_prefix = to_env_prefix(host.env)

    commands: List[str] = [setup]
    if env_prefix:
        commands.append(env_prefix)

    if do_build:
        commands.append("colcon build")
        commands.append("source install/setup.bash")

    commands.append(
        f"nohup {ros_cmd} > {shlex.quote(logfile)} 2>&1 < /dev/null & echo STARTED_PID:$! LOG:{logfile}"
    )
    return " && ".join(commands)


def build_stop_command(host: HostConfig, publisher_cfg: Dict[str, Any]) -> str:
    package = str(publisher_cfg.get("package", "dds_study"))
    executable = str(publisher_cfg.get("executable", "publisher"))
    pattern = f"ros2 run {package} {executable}"
    return f"pkill -f {shlex.quote(pattern)} || true"


def build_status_command(host: HostConfig, publisher_cfg: Dict[str, Any]) -> str:
    package = str(publisher_cfg.get("package", "dds_study"))
    executable = str(publisher_cfg.get("executable", "publisher"))
    pattern = f"ros2 run {package} {executable}"
    return f"pgrep -fa {shlex.quote(pattern)} || echo NOT_RUNNING"


def run_ssh(host: HostConfig, remote_command: str, timeout: int, dry_run: bool) -> Dict[str, Any]:
    ssh_cmd = ["ssh", "-p", str(host.ssh_port)]
    if host.ssh_key:
        ssh_cmd.extend(["-i", host.ssh_key])

    # Keep the full remote shell command as a single argument so bash -lc parses it correctly.
    remote_entry = f"bash -lc {shlex.quote(remote_command)}"

    ssh_cmd.extend([
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{host.user}@{host.host}",
        remote_entry,
    ])

    if dry_run:
        return {
            "host": host.name,
            "returncode": 0,
            "stdout": "DRY_RUN",
            "stderr": " ".join(shlex.quote(x) for x in ssh_cmd),
        }

    try:
        proc = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "host": host.name,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "host": host.name,
            "returncode": 124,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
        }


def main() -> int:
    args = parse_args()

    if args.action == "exec" and not args.cmd:
        print("--cmd is required when action=exec", file=sys.stderr)
        return 2

    cfg = load_hosts(args.config, args.hosts)
    hosts: List[HostConfig] = cfg["hosts"]
    publisher_cfg: Dict[str, Any] = cfg["publisher"]

    if args.action == "start":
        command_builder = lambda h: build_start_command(h, publisher_cfg, args.build)
    elif args.action == "stop":
        command_builder = lambda h: build_stop_command(h, publisher_cfg)
    elif args.action == "status":
        command_builder = lambda h: build_status_command(h, publisher_cfg)
    else:
        command_builder = lambda h: args.cmd

    results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
        future_map = {
            pool.submit(run_ssh, host, command_builder(host), args.timeout, args.dry_run): host
            for host in hosts
        }
        for fut in concurrent.futures.as_completed(future_map):
            results.append(fut.result())

    results.sort(key=lambda x: x["host"])
    failed = 0
    for item in results:
        status = "OK" if item["returncode"] == 0 else "FAIL"
        if status == "FAIL":
            failed += 1
        print(f"[{status}] {item['host']}")
        if item["stdout"]:
            print(f"stdout: {item['stdout']}")
        if item["stderr"]:
            print(f"stderr: {item['stderr']}")
        print("-" * 60)

    print(f"Done. total={len(results)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
