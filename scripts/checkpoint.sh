#!/bin/bash
#
# Checkpoint automation script
#
# Usage:
#   ./scripts/checkpoint.sh "Waypoint description" [phase_name] [--commit]
#
# This script automates checkpoints:
# 1. Shows running containers and git status
# 2. Verifies handoff documentation exists
# 3. Optionally commits to git with proper tagging
#
# Example:
#   ./scripts/checkpoint.sh "Phase 7 complete" "phase7" --commit
#

set -e

if [ -z "$1" ]; then
    echo "Error: Waypoint description required"
    echo "Usage: $0 \"Waypoint description\" [phase_name] [--commit]"
    exit 1
fi

WAYPOINT_DESC="$1"
PHASE_NAME="${2:-current}"
COMMIT_FLAG="${3:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M %Z')
DATE_ONLY=$(date '+%Y-%m-%d')

echo "=== Checkpoint: $WAYPOINT_DESC ==="
echo "Timestamp: $TIMESTAMP"
echo "Phase: $PHASE_NAME"
echo ""

# Show running containers
echo "=== Running Containers ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -20
echo ""

# Show git status
echo "=== Git Status ==="
git status --short
echo ""

# Create handoff filename
HANDOFF_FILE="HANDOFF-${DATE_ONLY}-${PHASE_NAME}.md"

echo "=== Documentation Check ==="
if [ -f "$HANDOFF_FILE" ]; then
    echo "✓ Handoff exists: $HANDOFF_FILE"
else
    echo "✗ Handoff missing: $HANDOFF_FILE"
    echo "Create handoff before running with --commit"
fi
echo ""

if [ "$COMMIT_FLAG" == "--commit" ]; then
    if [ ! -f "$HANDOFF_FILE" ]; then
        echo "Error: Cannot commit without handoff file"
        exit 1
    fi

    echo "=== Running Git Checkpoint ==="
    ./scripts/git_checkpoint.sh "$WAYPOINT_DESC" "$HANDOFF_FILE"
else
    echo "=== Next Steps ==="
    echo "1. Verify CLAUDE.md is up to date"
    echo "2. Verify handoff is complete: $HANDOFF_FILE"
    echo "3. Run with --commit to create git checkpoint:"
    echo "   ./scripts/checkpoint.sh \"$WAYPOINT_DESC\" \"$PHASE_NAME\" --commit"
    echo ""
fi
