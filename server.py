from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import os
import time
import psutil
import csv
import threading

# =========================
# INIT
# =========================
server = Flask(__name__)
CORS(server)

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


# =========================
# HELPERS
# =========================
def is_running():
    global process
    return process is not None and process.poll() is None


def stop_process(reason="manual"):
    global process, last_stop_reason

    if is_running():
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass

    process = None
    last_stop_reason = reason


def read_last_rps(csv_path="locust_results_stats_history.csv"):
    if not os.path.exists(csv_path):
        return 0

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            if not rows:
                return 0

            last = rows[-1]

            for key in ["Total RPS", "Current RPS", "Requests/s"]:
                if key in last and last[key]:
                    try:
                        return round(float(last[key]), 2)
                    except:
                        pass
    except:
        pass

    return 0


def cleanup_old_csv():
    files = [
        "locust_results_stats.csv",
        "locust_results_stats_history.csv",
        "locust_results_failures.csv",
        "locust_results_exceptions.csv",
    ]
    for f in files:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass


def monitor_cpu():
    global auto_stop_enabled, auto_stop_cpu_threshold

    while is_running():
        if auto_stop_enabled:
            cpu = psutil.cpu_percent(interval=1.0)
            if cpu >= auto_stop_cpu_threshold:
                stop_process(f"CPU limit {cpu}%")
                break
        else:
            time.sleep(1)


# =========================
# FRONTEND (ВАЖНО)
# =========================
@server.route("/")
def index():
    return send_from_directory(".", "index.html")


# =========================
# API
# =========================
@server.route("/health")
def health():
    return jsonify({"status": "ok"})


@server.route("/auto-config")
def auto_config():
    cpu_count = psutil.cpu_count(logical=True) or 4
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)

    return jsonify({
        "cpu": cpu_count,
        "ram": ram_gb
    })


@server.route("/run", methods=["POST"])
def run():
    global process, started_at
    global last_host, last_users, last_spawn
    global last_method, last_preset_name
    global auto_stop_enabled, auto_stop_cpu_threshold

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

    if is_running():
        return jsonify({"status": "already_running"})

    cleanup_old_csv()

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

    process = subprocess.Popen(cmd, env=env)

    started_at = time.time()
    last_host = host
    last_users = users
    last_spawn = spawn
    last_method = method
    last_preset_name = preset_name

    threading.Thread(target=monitor_cpu, daemon=True).start()

    return jsonify({"status": "started"})


@server.route("/stop", methods=["POST"])
def stop():
    stop_process("manual")
    return jsonify({"status": "stopped"})


@server.route("/stats")
def stats():
    running = is_running()

    run_time = int(time.time() - started_at) if started_at and running else 0

    return jsonify({
        "running": running,
        "users": last_users if running else 0,
        "spawn": last_spawn if running else 0,
        "runtime": run_time,
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "rps": read_last_rps(),
        "host": last_host
    })


@server.route("/test")
def test():
    return jsonify({"ok": True})


# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
