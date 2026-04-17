from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import os
import time
import psutil
import threading

app = Flask(__name__)
CORS(app)

process = None
started_at = None

last_users = 0
last_spawn = 0
last_method = "GET"
last_host = ""

# =====================
# HELPERS
# =====================

def running():
    return process is not None and process.poll() is None


def stop(reason="manual"):
    global process
    if running():
        process.terminate()
    process = None


# =====================
# AUTO CONFIG FIX
# =====================

@app.route("/auto-config")
def auto_config():
    cpu = psutil.cpu_count() or 4

    return jsonify({
        "users": cpu * 50,
        "spawn": cpu * 5,
        "time": 60,
        "preset_name": "auto"
    })


# =====================
# RUN
# =====================

@app.route("/run", methods=["POST"])
def run():
    global process, started_at
    global last_users, last_spawn, last_method, last_host

    d = request.json

    if running():
        return jsonify({"status":"already_running"})

    last_users = d["users"]
    last_spawn = d["spawn"]
    last_method = d["method"]
    last_host = d["host"]

    cmd = [
        "locust",
        "-f","locustfile.py",
        "--headless",
        "--host", d["host"],
        "-u", str(d["users"]),
        "-r", str(d["spawn"]),
        "--run-time", f"{d['time']}s"
    ]

    process = subprocess.Popen(cmd)
    started_at = time.time()

    return jsonify({"status":"started"})


# =====================
# STOP
# =====================

@app.route("/stop", methods=["POST"])
def stop_route():
    stop()
    return jsonify({"status":"stopped"})


# =====================
# STATS FIX
# =====================

@app.route("/stats")
def stats():
    run_time = int(time.time() - started_at) if started_at and running() else 0

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    return jsonify({
        "users": last_users,
        "spawn": last_spawn,
        "runtime": run_time,
        "cpu": cpu,
        "ram": ram,
        "rps": 0,
        "method": last_method
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
