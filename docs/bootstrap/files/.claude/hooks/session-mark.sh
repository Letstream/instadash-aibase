#!/usr/bin/env bash
# Instadash AI Base (managed file) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com.
# Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use
# or redistribution is prohibited.
# SessionStart: record when this session began, so the Stop hook only judges this session's edits.
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
sid=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("session_id","default"))' 2>/dev/null)
mkdir -p "$root/.claude/state" && touch "$root/.claude/state/session-${sid:-default}"
# prune markers older than 14 days
find "$root/.claude/state" -name 'session-*' -mtime +14 -delete 2>/dev/null
exit 0
