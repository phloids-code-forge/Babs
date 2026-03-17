#!/bin/bash
# babs-seed.sh - Seed the OpenClaw sandbox after any restart.
# Called automatically by openclaw-dashboard-tunnel.service.
# Can also be run manually: bash /usr/local/bin/babs-seed.sh

set -euo pipefail

source /etc/babs-reseed.env  # GITHUB_TOKEN

SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null openshell-nemoclaw"
WORKSPACE=/home/dave/babs/openclaw-workspace

log() { echo "[babs-seed] $*"; }

# Wait for sandbox SSH to be reachable (up to 60s)
log "waiting for sandbox..."
for i in $(seq 1 30); do
    if $SSH "true" 2>/dev/null; then break; fi
    sleep 2
done
$SSH "true" || { log "ERROR: sandbox not reachable after 60s"; exit 1; }

log "sandbox reachable, seeding..."

# Directories
$SSH "mkdir -p /sandbox/.openclaw/workspace"

# openclaw.json (providers, API keys, gateway config)
$SSH "cat > /sandbox/.openclaw/openclaw.json && chmod 600 /sandbox/.openclaw/openclaw.json" \
    < /etc/babs-openclaw.json

# Workspace identity files
for f in SOUL IDENTITY USER TOOLS; do
    $SSH "cat > /sandbox/.openclaw/workspace/${f}.md" < "${WORKSPACE}/${f}.md"
done

# Git credentials
$SSH "printf 'https://%s@github.com\n' '${GITHUB_TOKEN}' > /sandbox/.git-credentials \
      && chmod 600 /sandbox/.git-credentials"
$SSH "git config --global credential.helper store \
      && git config --global user.name 'Babs' \
      && git config --global user.email 'babs@openclaw'"

# Clone or pull repo
$SSH "if [ -d /sandbox/babs/.git ]; then
          cd /sandbox/babs && git pull --ff-only 2>&1 | tail -1
      else
          cd /sandbox && git clone https://github.com/phloids-code-forge/Babs.git babs 2>&1 | tail -1
      fi"

log "done."
