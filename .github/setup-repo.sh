#!/usr/bin/env bash
# One-time repository setup for the public comment window.
# Enables the Issues tab and creates the triage labels. Idempotent: re-running
# updates existing labels rather than failing. Requires the gh CLI, authenticated
# with admin rights on the repo.
#
#   ./.github/setup-repo.sh
set -euo pipefail

REPO="SPUR-Coalition/telemetry"

echo "Enabling Issues on $REPO..."
gh repo edit "$REPO" --enable-issues

create_label() {
  local name="$1" color="$2" desc="$3"
  if gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null; then
    echo "  created  $name"
  else
    gh label edit "$name" --repo "$REPO" --color "$color" --description "$desc"
    echo "  updated  $name"
  fi
}

echo "Creating triage labels..."
create_label "open-question"     "5319e7" "An unresolved design question under active discussion"
create_label "out-of-scope-0.1"  "bfd4f2" "Deferred beyond v0.1 (see SPECIFICATION.md 1.3 and 8.9)"
create_label "needs-discussion"  "fbca04" "Needs maintainer or working-group discussion before action"
create_label "editorial"         "c5def5" "Wording, clarity, or typo - non-normative"

echo "Done."
