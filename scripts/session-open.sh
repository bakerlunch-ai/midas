#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Desktop/midas"

echo "==> Fetching origin..."
git fetch origin main --quiet

LOCAL_AHEAD=$(git rev-list --count origin/main..HEAD)
REMOTE_AHEAD=$(git rev-list --count HEAD..origin/main)

if [[ "$LOCAL_AHEAD" -gt 0 ]]; then
  echo ""
  echo "⚠️  WARNING: $LOCAL_AHEAD local commits NOT pushed to GitHub:"
  git log --oneline origin/main..HEAD
  echo ""
  echo "Run: git push origin main"
  echo "Or, if these are old session-close docs: ./scripts/session-close.sh <date> <msg>"
  exit 1
fi

if [[ "$REMOTE_AHEAD" -gt 0 ]]; then
  echo "==> Remote has $REMOTE_AHEAD new commits. Pulling..."
  git pull --rebase origin main
fi

UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
if [[ "$UNCOMMITTED" -gt 0 ]]; then
  echo ""
  echo "⚠️  Uncommitted changes in working tree:"
  git status --short
  echo ""
  echo "Decide before starting work: commit them, stash them, or discard them."
fi

echo ""
echo "==> ✅ Repo in sync with GitHub. Ready to start session."
git log -1 --oneline
