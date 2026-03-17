#!/bin/bash
# babs-sync.sh - Push Babs repo docs into the OpenClaw sandbox workspace.
#
# Run from Spark whenever you want Babs to have fresh access to the repo.
# Uses tar-over-SSH since rsync is not available inside the sandbox.
#
# Usage:
#   ./scripts/babs-sync.sh       # sync docs into sandbox
#   ./scripts/babs-sync.sh -n    # dry-run (list files only)

set -e

REPO="$HOME/babs"
SANDBOX_DEST="/sandbox/.openclaw/workspace/babs"
SSH_TARGET="openshell-nemoclaw"

if [[ "$1" == "-n" || "$1" == "--dry-run" ]]; then
    echo "[babs-sync] DRY RUN -- files that would sync:"
    cd "$REPO"
    find . \( \
        -name "CLAUDE.md" -o \
        -path "./docs/*" -o \
        \( -path "./src/*" \( -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.yaml" -o -name "*.sh" \) \) \
    \) -not -name "*.swp" | sort
    exit 0
fi

echo "[babs-sync] syncing babs docs to sandbox..."

# Ensure destination exists
ssh "$SSH_TARGET" "mkdir -p $SANDBOX_DEST/docs $SANDBOX_DEST/src"

# CLAUDE.md
cat "$REPO/CLAUDE.md" | ssh "$SSH_TARGET" "cat > $SANDBOX_DEST/CLAUDE.md"
echo "  CLAUDE.md"

# docs/ directory (all markdown + yaml)
cd "$REPO/docs"
find . -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) | \
    tar -czf - -T - | \
    ssh "$SSH_TARGET" "cd $SANDBOX_DEST/docs && tar -xzf -"
echo "  docs/"

# src/ (code files only, no large assets)
cd "$REPO/src"
find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.yaml" -o -name "*.json" -o -name "*.sh" \) | \
    tar -czf - -T - | \
    ssh "$SSH_TARGET" "cd $SANDBOX_DEST/src && tar -xzf -"
echo "  src/"

# Write sync timestamp
STAMP="Last synced: $(date -u '+%Y-%m-%d %H:%M UTC') from Spark"
echo "$STAMP" | ssh "$SSH_TARGET" "cat > $SANDBOX_DEST/SYNC_STATUS.md"

echo "[babs-sync] done. Babs can read docs at: $SANDBOX_DEST"
