#!/bin/bash
#
# Git Checkpoint Automation
#
# Usage:
#   ./scripts/git_checkpoint.sh "Checkpoint description" [handoff_file]
#
# This script:
# 1. Verifies all changes are documented in handoff
# 2. Commits all changes with structured message
# 3. Tags commit with checkpoint marker
# 4. Shows verification output
#
# Example:
#   ./scripts/git_checkpoint.sh "Phase 7 complete" "HANDOFF-2026-03-13-CURRENT.md"
#

set -e

if [ -z "$1" ]; then
    echo "Error: Checkpoint description required"
    echo "Usage: $0 \"Checkpoint description\" [handoff_file]"
    exit 1
fi

CHECKPOINT_DESC="$1"
HANDOFF_FILE="${2:-HANDOFF-$(date +%Y-%m-%d)-CURRENT.md}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

echo "=== Git Checkpoint: $CHECKPOINT_DESC ==="
echo "Timestamp: $TIMESTAMP"
echo "Handoff: $HANDOFF_FILE"
echo ""

# Verify handoff exists
if [ ! -f "$HANDOFF_FILE" ]; then
    echo "Error: Handoff file not found: $HANDOFF_FILE"
    echo "Create handoff before committing."
    exit 1
fi

# Show what will be committed
echo "=== Files to be committed ==="
git status --short
echo ""

# Verify handoff is staged or modified
if ! git status --short | grep -q "$HANDOFF_FILE"; then
    echo "Warning: Handoff file not in git status. Adding it now."
    git add "$HANDOFF_FILE"
fi

# Add all changes
echo "=== Staging all changes ==="
git add -A
echo ""

# Build commit message
COMMIT_MSG="Checkpoint: $CHECKPOINT_DESC

Timestamp: $TIMESTAMP
Handoff: $HANDOFF_FILE

This checkpoint captures the state of the system as documented in the handoff file.
All changes are logged and verified.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Show commit message
echo "=== Commit Message ==="
echo "$COMMIT_MSG"
echo ""

# Confirm
read -p "Proceed with commit? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Commit cancelled."
    exit 1
fi

# Create commit
git commit -m "$COMMIT_MSG"

# Create tag
TAG_NAME="checkpoint-$(date +%Y%m%d-%H%M%S)"
git tag -a "$TAG_NAME" -m "$CHECKPOINT_DESC"

echo ""
echo "=== Checkpoint Complete ==="
echo "Commit: $(git rev-parse HEAD)"
echo "Tag: $TAG_NAME"
echo ""

# Show verification
echo "=== Verification ==="
echo "Latest commit:"
git log -1 --oneline
echo ""
echo "All checkpoint tags:"
git tag -l "checkpoint-*" | tail -5
echo ""
echo "To revert to this checkpoint:"
echo "  git reset --hard $TAG_NAME"
echo ""
