################################################################################
# Python script to monitor memory usage using docker stats, combine for
# docker-compose that have multiple containers
################################################################################

import subprocess
import json
import time
import csv
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

DEFAULT_INTERVAL = 60


def get_container_ids_for_project(project):
    """Return list of (container_id, container_name) for a compose project"""
    try:
        result = subprocess.run(
            [
                "docker", "ps",
                "--filter", f"label=com.docker.compose.project={project}",
                "--format", "{{.ID}} {{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        containers = []
        for line in result.stdout.splitlines():
            cid, name = line.split(maxsplit=1)
            containers.append((cid, name))
        return containers
    except subprocess.CalledProcessError as e:
        print(f"Error finding containers: {e}")
        return []


def get_container_stats(container_id):
    try:
        result = subprocess.run(
            [
                "docker", "stats",
                container_id,
                "--no-stream",
                "--format", "{{json .}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return None


def parse_mem_to_mib(mem_str):
    """
    Convert docker stats memory strings to MiB.
    Handles:
      123.4MiB
      1.23GiB
      512KiB
      0B
    """
    match = re.match(r"([\d\.]+)\s*([KMG]?i?)B", mem_str)
    if not match:
        return 0.0

    value = float(match.group(1))
    unit = match.group(2)

    if unit == "Gi":
        return value * 1024
    elif unit == "Mi":
        return value
    elif unit == "Ki":
        return value / 1024
    else:  # Bytes
        return value / (1024 * 1024)


def monitor_project(project, interval, duration, csv_path):
    csv_path = Path(csv_path)
    csv_exists = csv_path.exists()

    csv_file = open(csv_path, "a", newline="", buffering=2)
    writer = csv.DictWriter(
        csv_file,
        fieldnames=[
            "timestamp",
            "timestamp_local",
            "project",
            "container_name",
            "container_id",
            "memory_mib",
            "memory_percent",
            "cpu_percent",
            "scope",        # container OR project
        ],
    )

    if not csv_exists:
        writer.writeheader()

    end_time = time.time() + duration + 60 if duration else None

    print("\nMonitoring Configuration:")
    print(f"Duration: {duration} (60 sec buffer)")
    print(f"Interval: {interval}\n")

    print(f"Monitoring compose project: {project}")
    print(f"Writing CSV: {csv_path}\n")

    print("-" * 80)

    try:
        while True:
            if end_time and time.time() >= end_time:
                break

            containers = get_container_ids_for_project(project)
            if not containers:
                print("No containers found (project stopped?)")
                time.sleep(interval)
                continue

            timestamp_utc = int(datetime.now(timezone.utc).timestamp() * 1000)
            timestamp_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            total_mem = 0.0
            total_cpu = 0.0

            for cid, name in containers:
                stats = get_container_stats(cid)
                if not stats:
                    continue

                mem_used = stats["MemUsage"].split("/")[0].strip()
                mem_mib = parse_mem_to_mib(mem_used)
                mem_perc = float(stats["MemPerc"].strip("%"))
                cpu_perc = float(stats["CPUPerc"].strip("%"))

                total_mem += mem_mib
                total_cpu += cpu_perc

                writer.writerow(
                    {
                        "timestamp": timestamp_utc,
                        "timestamp_local": timestamp_local,
                        "project": project,
                        "container_name": name,
                        "container_id": cid,
                        "memory_mib": round(mem_mib, 2),
                        "memory_percent": mem_perc,
                        "cpu_percent": cpu_perc,
                        "scope": "container",
                    }
                )

            # Write aggregated project row
            writer.writerow(
                {
                    "timestamp": timestamp_utc,
                    "timestamp_local": timestamp_local,
                    "project": project,
                    "container_name": "ALL",
                    "container_id": "ALL",
                    "memory_mib": round(total_mem, 2),
                    "memory_percent": "",
                    "cpu_percent": round(total_cpu, 2),
                    "scope": "project",
                }
            )

            print(
                f"[{timestamp_local}] "
                f"containers={len(containers)} "
                f"total_mem={total_mem:.1f}MiB "
                f"total_cpu={total_cpu:.1f}%"
            )

            csv_file.flush()
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        csv_file.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor docker-compose project memory usage")
    parser.add_argument("--project", required=True, help="Compose project name (e.g. myapp)")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Polling interval (seconds)")
    parser.add_argument("--duration", type=int, help="Total duration (seconds), omit to run forever")
    parser.add_argument("--csv", required=True, help="Output CSV file")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    monitor_project(
        project=args.project,
        interval=args.interval,
        duration=args.duration,
        csv_path=args.csv,
    )
