#!/usr/bin/env bash
# Instadash AI Base (managed file) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com.
# Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use
# or redistribution is prohibited.
# UserPromptSubmit: route "Bootstrap" and fresh repos to the Bootstrap flow; otherwise remind the
# agent of the read/write-docs rule. Stdout is added to the agent's context.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
prompt=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))' 2>/dev/null)
trimmed=$(printf '%s' "$prompt" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')

is_empty() { [[ ! -s "$1" ]] || ! grep -q '[^[:space:]]' "$1"; }

if [[ ! -f "$root/.instadash.json" && -d "$root/docs/bootstrap/files" ]]; then
  echo "BASE NOT INSTALLED: docs/bootstrap/ is present but .instadash.json is missing. Do the initial steps in docs/bootstrap/install.md first (unless the user is asking something unrelated)."
elif [[ "$trimmed" == "upgrade" ]]; then
  echo "UPGRADE REQUESTED: invoke the 'upgrade' skill and follow docs/bootstrap/upgrade.md exactly."
elif [[ "$trimmed" == "bootstrap" ]]; then
  echo "BOOTSTRAP REQUESTED: invoke the 'bootstrap' skill and follow docs/bootstrap/interview.md exactly (interview first, no code until confirmed)."
elif [[ -d "$root/docs/migration" ]] && is_empty "$root/DOCS.md"; then
  echo "MIGRATION IN PROGRESS: continue /migrate-to-instadash from docs/migration/ (inventory → features → plan) per docs/bootstrap/migrate.md; no new code until plan.md is approved; log progress in handoff.md."
elif is_empty "$root/DOCS.md" || is_empty "$root/handoff.md"; then
  legacy=$(find "$root" -maxdepth 2 \( -name node_modules -o -name .venv -o -name .git -o -name docs -o -name .claude -o -name backend -o -name frontend -o -name infra \) -prune -o \
    -type f \( -name package.json -o -name requirements.txt -o -name pyproject.toml -o -name app.py -o -name manage.py -o -name composer.json -o -name Gemfile -o -name go.mod -o -name '*.html' \) -print -quit 2>/dev/null)
  if [[ -n "$legacy" ]]; then
    echo "EXISTING CODEBASE, NOT SET UP: DOCS.md/handoff.md are empty but an application exists (e.g. ${legacy#$root/}). Tell the user and propose /migrate-to-instadash (docs/bootstrap/migrate.md) rather than /bootstrap; don't change code before that flow's plan is approved."
  else
    echo "FRESH REPO: DOCS.md and/or handoff.md is empty. Before anything else, tell the user this is a new setup and run the Bootstrap flow (the 'bootstrap' skill / docs/bootstrap/interview.md)."
  fi
else
  echo "Reminder: align with DOCS.md, handoff.md and the relevant docs/ page (frontend: load the frontend-design-guidelines skill) before changing anything; update the touched docs and handoff.md before you stop."
fi
exit 0
