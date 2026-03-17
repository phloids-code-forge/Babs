#!/bin/bash
# Kill any stale gateway, start fresh, then hold the port forward tunnel
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null openshell-nemoclaw \
    "openclaw gateway stop 2>/dev/null; pkill -9 -f openclaw-gatewa 2>/dev/null; sleep 2; openclaw gateway --bind loopback --allow-unconfigured &>/tmp/gw.log &"
sleep 4
exec ssh \
    -N \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -L 0.0.0.0:18789:127.0.0.1:18789 \
    openshell-nemoclaw
