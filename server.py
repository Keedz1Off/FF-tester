from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import time
import psutil
import csv
import threading


process = None
started_at = None
last_host = None
last_users = 0
last_spawn = 0
last_method = "GET"
last_preset_name = "manual"
last_stop_reason = None

auto_stop_enabled = False
auto_stop_cpu_threshold = 85
monitor_thread = None


def is_running():
    global process
    return process is not None and process.poll() is None


def read_last_rps(csv_path="locust_results_stats_history.csv"):
    if not os.path.exists(csv_path):
        return 0

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            if not rows:
                return 0

            last = rows[-1]

            preferred_keys = [
                "Total RPS",
                "Current RPS",
                "Requests/s",
                "total_rps",
                "current_rps"
            ]

            for key in preferred_keys:
                if key in last and last[key]:
                    try:
                        return round(float(last[key]), 2)
                    except Exception:
                        pass

            for k, v in last.items():
                lk = k.strip().lower()
                if "rps" in lk and v:
                    try:
                        return round(float(v), 2)
                    except Exception:
                        continue

    except Exception:
        return 0

    return 0


def cleanup_old_csv():
    for name in [
        "locust_results_stats.csv",
        "locust_results_stats_history.csv",
        "locust_results_failures.csv",
        "locust_results_exceptions.csv",
    ]:
        if os.path.exists(name):
            try:
                os.remove(name)
            except Exception:
                pass


def stop_process(reason="manual"):
    global process, last_stop_reason

    if is_running():
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    process = None
    last_stop_reason = reason


def monitor_cpu():
    global auto_stop_enabled, auto_stop_cpu_threshold
    while is_running():
        if auto_stop_enabled:
            cpu = psutil.cpu_percent(interval=1.0)
            if cpu >= auto_stop_cpu_threshold:
                stop_process(reason=f"CPU threshold reached: {cpu}% >= {auto_stop_cpu_threshold}%")
                break
        else:
            time.sleep(1)


def build_auto_config():
    cpu_count = psutil.cpu_count(logical=True) or 4
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)

    if cpu_count <= 4 or ram_gb <= 8:
        return {
            "preset_name": "light-auto",
            "users": 50,
            "spawn": 4,
            "time": 30,
            "cpu_count": cpu_count,
            "ram_gb": ram_gb
        }

    if cpu_count <= 8 or ram_gb <= 16:
        return {
            "preset_name": "medium-auto",
            "users": 300,
            "spawn": 20,
            "time": 60,
            "cpu_count": cpu_count,
            "ram_gb": ram_gb
        }

    return {
        "preset_name": "strong-auto",
        "users": 1000,
        "spawn": 50,
        "time": 120,
        "cpu_count": cpu_count,
        "ram_gb": ram_gb
    }


@server.route("/auto-config")
def auto_config():
    return jsonify(build_auto_config())


@server.route("/run", methods=["POST"])
def run():
    global process, started_at, last_host, last_users, last_spawn
    global last_method, last_preset_name, auto_stop_enabled, auto_stop_cpu_threshold
    global monitor_thread, last_stop_reason

    data = request.json or {}

    host = data.get("host")
    path = data.get("path", "/")
    users = int(data.get("users", 10))
    spawn = int(data.get("spawn", 2))
    duration = int(data.get("time", 10))
    method = data.get("method", "GET")
    preset_name = data.get("preset_name", "manual")

    auto_stop_enabled = bool(data.get("auto_stop_on_cpu", False))
    auto_stop_cpu_threshold = int(data.get("cpu_stop_threshold", 85))

    if not host:
        return jsonify({"error": "host required"}), 400

    users = max(1, min(users, 5000))
    spawn = max(1, min(spawn, 500))
    duration = max(5, min(duration, 3600))

    if is_running():
        return jsonify({"status": "already_running"})

    cleanup_old_csv()
    last_stop_reason = None

    wait_min = 0.2
    wait_max = 1.0

    if preset_name == "light":
        wait_min = 0.5
        wait_max = 1.5
    elif preset_name == "medium":
        wait_min = 0.2
        wait_max = 1.0
    elif preset_name == "strong":
        wait_min = 0.05
        wait_max = 0.3
    elif preset_name == "extreme":
        wait_min = 0.0
        wait_max = 0.05
    elif "auto" in preset_name:
        if users <= 100:
            wait_min = 0.4
            wait_max = 1.2
        elif users <= 500:
            wait_min = 0.1
            wait_max = 0.5
        else:
            wait_min = 0.0
            wait_max = 0.1

    cmd = [
        "locust",
        "-f", "locustfile.py",
        "--headless",
        "--host", host,
        "-u", str(users),
        "-r", str(spawn),
        "--run-time", f"{duration}s",
        "--csv", "locust_results"
    ]

    env = os.environ.copy()
    env["TARGET_PATH"] = path
    env["WAIT_MIN"] = str(wait_min)
    env["WAIT_MAX"] = str(wait_max)

    try:
        print("\n🔥 STARTING LOCUST:")
        print(" ".join(cmd))
        print("TARGET_PATH =", path)
        print("METHOD =", method)
        print("PRESET =", preset_name)
        print("WAIT_MIN =", wait_min)
        print("WAIT_MAX =", wait_max)
        print("=================================\n")

        process = subprocess.Popen(cmd, env=env)

        started_at = time.time()
        last_host = host
        last_users = users
        last_spawn = spawn
        last_method = method
        last_preset_name = preset_name

        monitor_thread = threading.Thread(target=monitor_cpu, daemon=True)
        monitor_thread.start()

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "status": "started",
        "cmd": " ".join(cmd),
        "config": {
            "host": host,
            "path": path,
            "users": users,
            "spawn": spawn,
            "time": duration,
            "method": method,
            "preset_name": preset_name,
            "auto_stop_on_cpu": auto_stop_enabled,
            "cpu_stop_threshold": auto_stop_cpu_threshold,
            "wait": {
                "min": wait_min,
                "max": wait_max
            }
        }
    })


@server.route("/stop", methods=["POST"])
def stop():
    if is_running():
        print("\n🛑 STOPPING LOCUST\n")
        stop_process(reason="manual")
        return jsonify({"status": "stopped"})

    return jsonify({"status": "not running"})


@server.route("/stats")
def stats():
    global started_at, last_users, last_spawn

    running = is_running()

    run_time = 0
    if started_at:
        run_time = int(time.time() - started_at)

    cpu_percent = psutil.cpu_percent(interval=0.15)
    memory_percent = psutil.virtual_memory().percent
    rps = read_last_rps()

    return jsonify({
        "status": "running" if running else "stopped",
        "users": last_users if running else 0,
        "spawn_rate": last_spawn if running else 0,
        "run_time_seconds": run_time if running else 0,
        "method": last_method,
        "cpu_percent": round(cpu_percent, 1),
        "memory_percent": round(memory_percent, 1),
        "rps": rps,
        "target_host": last_host if running else None,
        "preset_name": last_preset_name,
        "stop_reason": last_stop_reason
    })


@server.route("/health")
def health():
    return jsonify({"status": "ok"})


@server.route("/test-cpu")
def test_cpu():
    loops = min(int(request.args.get("loops", 150000)), 300000)
    x = 0
    for i in range(loops):
        x += (i * i) % 97
    return jsonify({
        "status": "ok",
        "result": x,
        "loops": loops
    })


@server.route("/test-json")
def test_json():
    size = min(int(request.args.get("size", 200)), 1000)
    payload = [{"id": i, "value": f"item-{i}", "square": i * i} for i in range(size)]
    return jsonify({
        "status": "ok",
        "count": size,
        "items": payload
    })


@server.route("/test-mixed")
def test_mixed():
    loops = min(int(request.args.get("loops", 60000)), 150000)
    size = min(int(request.args.get("size", 100)), 500)

    x = 0
    for i in range(loops):
        x += (i * 7) % 31

    payload = [{"id": i, "value": f"mixed-{i}", "calc": (i * i) % 17} for i in range(size)]

    return jsonify({
        "status": "ok",
        "cpu_result": x,
        "count": size,
        "items": payload
    })


@server.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    server.run(port=5000, debug=True)
