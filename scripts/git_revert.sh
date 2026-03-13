#!/bin/bash
#
# Git Revert Helper
#
# Usage:
#   ./scripts/git_revert.sh [checkpoint_tag]
#
# This script helps safely revert to a previous checkpoint.
# If no tag is provided, shows available checkpoints.
#

set -e

if [ -z "$1" ]; then
    echo "=== Available Checkpoints ==="
    echo ""
    git tag -l "checkpoint-*" --sort=-creatordate | while read tag; do
        commit=$(git rev-list -n 1 "$tag")
        date=$(git log -1 --format=%ai "$commit" | cut -d' ' -f1,2)
        msg=$(git tag -l --format='%(contents:subject)' "$tag")
        echo "$tag"
        echo "  Date: $date"
        echo "  Message: $msg"
        echo "  Commit: ${commit:0:8}"
        echo ""
    done
    echo "Usage: $0 <checkpoint_tag>"
    echo ""
    echo "Example:"
    echo "  $0 checkpoint-20260313-133000"
    echo ""
    echo "Warning: This will HARD RESET your working directory."
    echo "All uncommitted changes will be lost."
    exit 0
fi

TAG="$1"

# Verify tag exists
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Error: Tag '$TAG' not found"
    echo ""
    echo "Available checkpoints:"
    git tag -l "checkpoint-*" | tail -10
    exit 1
fi

# Show what we're reverting to
echo "=== Revert to Checkpoint ==="
echo "Tag: $TAG"
echo "Commit: $(git rev-list -n 1 "$TAG")"
echo "Message: $(git tag -l --format='%(contents:subject)' "$TAG")"
echo ""

# Show current state
echo "=== Current State ==="
git log -1 --oneline
echo ""
git status --short
echo ""

# Warn about uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "WARNING: You have uncommitted changes!"
    echo "These will be LOST if you proceed."
    echo ""
fi

# Confirm
read -p "Are you sure you want to HARD RESET to $TAG? (type 'yes' to confirm) " -r
echo
if [[ ! $REPLY == "yes" ]]; then
    echo "Revert cancelled."
    exit 1
fi

# Create backup tag before reverting
BACKUP_TAG="backup-before-revert-$(date +%Y%m%d-%H%M%S)"
git tag "$BACKUP_TAG"
echo "Created backup tag: $BACKUP_TAG"
echo ""

# Revert
echo "Reverting to $TAG..."
git reset --hard "$TAG"

echo ""
echo "=== Revert Complete ==="
echo "Current state:"
git log -1 --oneline
echo ""
echo "If you need to undo this revert:"
echo "  git reset --hard $BACKUP_TAG"
echo ""
