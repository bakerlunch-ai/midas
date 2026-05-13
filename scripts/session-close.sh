#!/usr/bin/env bash
set -euo pipefail

# Session-close script — single source of truth for shipping a session.
# Usage: ./scripts/session-close.sh YYYY-MM-DD "commit message body"
# Example: ./scripts/session-close.sh 2026-05-13 "phase 1 task 10 — kalshi client scaffolded"

DATE="${1:?Usage: session-close.sh YYYY-MM-DD \"message\"}"
MSG="${2:?Usage: session-close.sh YYYY-MM-DD \"message\"}"
REPO="$HOME/Desktop/midas"

cd "$REPO"

echo "==> Sanity: are we in the right repo?"
git remote -v | grep -q "bakerlunch-ai/midas" || { echo "FAIL: not in midas repo"; exit 1; }

echo "==> Checking the five required docs exist in docs/"
for f in PROJECT_HANDOFF.html TODO.md JOURNEY.md SESSION_HISTORY.md "SESSION_REPORT_${DATE}.html"; do
  [[ -f "docs/$f" ]] || { echo "FAIL: docs/$f missing"; exit 1; }
done
echo "    all five present"

echo "==> Creating archive folder session-archive/${DATE}/"
mkdir -p "session-archive/${DATE}"

echo "==> Copying five files into archive"
cp "docs/PROJECT_HANDOFF.html"          "session-archive/${DATE}/"
cp "docs/TODO.md"                       "session-archive/${DATE}/"
cp "docs/JOURNEY.md"                    "session-archive/${DATE}/"
cp "docs/SESSION_HISTORY.md"            "session-archive/${DATE}/"
cp "docs/SESSION_REPORT_${DATE}.html"   "session-archive/${DATE}/"

echo "==> Cleaning up older session reports from docs/ (only latest stays)"
for old in docs/SESSION_REPORT_*.html; do
  [[ -e "$old" ]] || continue
  base=$(basename "$old" .html)
  old_date="${base#SESSION_REPORT_}"
  if [[ "$old_date" != "$DATE" ]]; then
    if [[ -f "session-archive/${old_date}/SESSION_REPORT_${old_date}.html" ]]; then
      echo "    removing stale docs/$base.html (archived at session-archive/${old_date}/)"
      git rm -q "$old"
    else
      echo "    WARN: docs/$base.html has no archive — leaving in place, please archive manually"
    fi
  fi
done

echo "==> Staging docs/ and session-archive/"
git add docs/ session-archive/

echo "==> Showing what's about to be committed:"
git status --short

echo ""
read -p "==> Proceed with commit and push? [y/N] " ok
[[ "$ok" == "y" || "$ok" == "Y" ]] || { echo "Aborted. Nothing committed."; exit 1; }

echo "==> Pulling latest from origin/main with rebase (in case Peter pushed)"
git pull --rebase origin main

echo "==> Committing"
git commit -m "docs: session close ${DATE} — ${MSG}"

echo "==> Pushing to origin/main"
git push origin main

NEW_SHA=$(git rev-parse --short HEAD)
echo ""
echo "==> ✅ Session ${DATE} closed and pushed."
echo "==> Commit SHA: ${NEW_SHA}"
echo "==> GitHub:     https://github.com/bakerlunch-ai/midas/commit/${NEW_SHA}"
