#!/bin/bash
cd /Users/scooter/Documents/New\ project
rm -f adaptive_predictor_daemon.log collector_daemon.log
python3 -u adaptive_predictor.py --daemon > adaptive_predictor_daemon.log 2>&1 &
echo $! > adaptive_predictor.pid
python3 -u collector.py --loop > collector_daemon.log 2>&1 &
echo $! > collector.pid
echo "Daemons started: $(cat adaptive_predictor.pid) $(cat collector.pid)"
