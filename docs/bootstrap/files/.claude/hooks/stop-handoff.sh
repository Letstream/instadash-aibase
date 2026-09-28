#!/usr/bin/env bash
# Instadash AI Base (managed file) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com.
# Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use
# or redistribution is prohibited.
# Stop: block ending the turn when code in backend/ frontend/ mobile/ infra/ changed during this session
# after the last handoff.md update. Fires at most once per stop (stop_hook_active guard).
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
read -r sid active < <(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("session_id","default"), str(d.get("stop_hook_active",False)).lower())' 2>/dev/null)
[[ "$active" == "true" ]] && exit 0
[[ -s "$root/DOCS.md" && -f "$root/handoff.md" ]] || exit 0      # not bootstrapped yet
marker="$root/.claude/state/session-${sid:-default}"
[[ -f "$marker" ]] || exit 0

dirs=(); for d in backend frontend mobile infra; do [[ -d "$root/$d" ]] && dirs+=("$root/$d"); done
(( ${#dirs[@]} )) || exit 0

changed=$(find "${dirs[@]}" \
  \( -name node_modules -o -name .venv -o -name .git -o -name dist -o -name data -o -name __pycache__ \
     -o -name .pytest_cache -o -name staticfiles -o -name coverage -o -name .vite -o -name .dart_tool -o -name build \) -prune -o \
  -type f -newer "$marker" -newer "$root/handoff.md" -print 2>/dev/null | head -n 5 | paste -sd, -)

if [[ -n "$changed" ]]; then
  reason="Code changed this session after the last handoff.md update (e.g. ${changed//$root\//}). Before stopping: update handoff.md (changed / verified / next), the matching docs/ page(s), DOCS.md if the overview, ports, services or decisions changed, and save agent state with the remember skill if the work session is ending."
  python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":sys.argv[1]}))' "$reason"
fi
exit 0
