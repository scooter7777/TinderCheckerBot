#!/usr/bin/env python3
"""Supervisor - keeps predictor & collector alive, restarts on crash"""
import os, sys, subprocess, time

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "supervisor.log")

def log_msg(msg):
    t = time.strftime("%H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{t}] {msg}\n")
    print(f"[{t}] {msg}")
    sys.stdout.flush()

def start_script(name, args, logfile):
    log_path = os.path.join(DIR, logfile)
    f = open(log_path, "a")
    proc = subprocess.Popen(
        [sys.executable, "-u"] + args,
        stdout=f, stderr=subprocess.STDOUT,
        cwd=DIR
    )
    log_msg(f"Started {name} (PID {proc.pid})")
    return proc

predictor = start_script("predictor", ["adaptive_predictor.py", "--daemon"], "adaptive_predictor_daemon.log")
collector = start_script("collector", ["collector.py", "--loop"], "collector_daemon.log")

log_msg("=== Supervisor started ===")

while True:
    time.sleep(30)
    if predictor.poll() is not None:
        log_msg(f"Predictor died (exit {predictor.returncode}), restarting...")
        predictor = start_script("predictor", ["adaptive_predictor.py", "--daemon"], "adaptive_predictor_daemon.log")
    if collector.poll() is not None:
        log_msg(f"Collector died (exit {collector.returncode}), restarting...")
        collector = start_script("collector", ["collector.py", "--loop"], "collector_daemon.log")
