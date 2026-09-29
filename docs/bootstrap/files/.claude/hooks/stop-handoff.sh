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
# A parallel-agent wave is in progress (lead waiting on background subagents): don't demand a final
# handoff yet. The marker expires after 4h so a forgotten one can't disable the check for good.
wave="$root/.claude/state/parallel-wave"
if [[ -f "$wave" ]]; then
  if [[ -n "$(find "$wave" -mmin -240 2>/dev/null)" ]]; then exit 0; fi
  rm -f "$wave"
fi
marker="$root/.claude/state/session-${sid:-default}"
[[ -f "$marker" ]] || exit 0

dirs=(); for d in backend frontend mobile infra; do [[ -d "$root/$d" ]] && dirs+=("$root/$d"); done
(( ${#dirs[@]} )) || exit 0

changed=$(find "${dirs[@]}" \
  \( -name node_modules -o -name .venv -o -name .git -o -name dist -o -name data -o -name __pycache__ \
     -o -name .pytest_cache -o -name staticfiles -o -name coverage -o -name .vite -o -name .dart_tool -o -name build -o -name .ruff_cache -o -name .mypy_cache \
     -o -name htmlcov -o -name .flutter-plugins-dependencies \) -prune -o \
  -type f ! -name '.coverage*' ! -name '*.log' ! -name '*.pid' -newer "$marker" -newer "$root/handoff.md" -print 2>/dev/null | head -n 5 | paste -sd, -)

if [[ -n "$changed" ]]; then
  reason="Code changed this session after the last handoff.md update (e.g. ${changed//$root\//}). Before stopping: update handoff.md (changed / verified / next), the matching docs/ page(s), DOCS.md if the overview, ports, services or decisions changed, and save agent state with the remember skill if the work session is ending."
  python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":sys.argv[1]}))' "$reason"
fi
exit 0
