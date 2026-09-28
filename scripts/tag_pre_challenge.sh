#!/usr/bin/env bash
# Create (or, before any push and before Oct 4 09:00 Riyadh, move) the annotated `pre-challenge` tag to HEAD.
# Refuses after the deadline, with a dirty tree, or once the tag exists on a remote.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
DEADLINE=$(TZ=Asia/Riyadh date -d "2026-10-04 09:00" +%s)
[ "$(date +%s)" -lt "$DEADLINE" ] || { echo "refusing: past 2026-10-04 09:00 Riyadh"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "refusing: uncommitted changes"; exit 1; }
if git remote | grep -q . && git ls-remote --tags "$(git remote | head -1)" pre-challenge | grep -q .; then
  echo "refusing: pre-challenge already pushed; do not move a published tag"; exit 1
fi
NOW=$(TZ=Asia/Riyadh date "+%Y-%m-%d %H:%M")
HASH=$(git rev-parse --short HEAD)
git tag -d pre-challenge >/dev/null 2>&1 || true
git tag -a pre-challenge -m "Nūn starting version before the build days.

Commit ${HASH}, tagged ${NOW} Riyadh (UTC+3).
Everything up to and including this commit is prior work (docs/PRIOR_WORK.md).
Only commits after this tag are challenge work (2026-10-04 09:00 to 2026-10-06 23:59 Riyadh)."
git tag -n6 pre-challenge
