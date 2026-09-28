#!/usr/bin/env bash
# Instadash AI Base (managed file) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com.
# Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use
# or redistribution is prohibited.
# PostToolUse (Edit|Write|MultiEdit): format + lint the file that was just written.
# Header  -> project license header inserted if missing (license_header.py)
# Python  -> black + ruff --fix (tools from the nearest pyproject's .venv, else PATH)
# FE code -> prettier --write + eslint --fix (from the nearest package.json's node_modules/.bin)
# Dart    -> dart format + dart analyze (nearest pubspec.yaml)
# Unfixable lint errors are printed to stderr with exit 2 so the agent sees and fixes them.
# Missing tools are skipped silently (e.g. before the scaffold is materialised).
set -uo pipefail

read -r sid file < <(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("session_id","default"), (d.get("tool_input") or {}).get("file_path",""))' 2>/dev/null)
[[ -z "$file" || ! -f "$file" ]] && exit 0
case "$file" in
  */node_modules/*|*/.venv/*|*/migrations/*|*/dist/*|*/docker/data/*) exit 0 ;;
esac

# license header first (no-op before bootstrap / for unsupported types) — docs/bootstrap/license-header.md
python3 "$(dirname "$0")/license_header.py" "${CLAUDE_PROJECT_DIR:-$(pwd)}" "$file" 2>/dev/null

# nearest ancestor dir containing $1
find_up() {
  local dir; dir=$(dirname "$file")
  while [[ "$dir" != "/" ]]; do
    [[ -e "$dir/$1" ]] && { echo "$dir"; return 0; }
    dir=$(dirname "$dir")
  done
  return 1
}

errors=""
case "$file" in
  *.py)
    root=$(find_up pyproject.toml) || exit 0
    venv_bin=""
    for c in "$root/.venv/bin" "$(dirname "$root")/.venv/bin"; do [[ -d "$c" ]] && venv_bin="$c" && break; done
    black=${venv_bin:+$venv_bin/}black; ruff=${venv_bin:+$venv_bin/}ruff
    command -v "$black" >/dev/null && (cd "$root" && "$black" -q "$file" 2>&1) >/dev/null
    if command -v "$ruff" >/dev/null; then
      out=$(cd "$root" && "$ruff" check --fix --quiet "$file" 2>&1) || errors+="$out"$'\n'
    fi
    ;;
  *.vue|*.ts|*.tsx|*.js|*.mjs|*.cjs|*.scss|*.css|*.json)
    root=$(find_up package.json) || exit 0
    bin="$root/node_modules/.bin"
    [[ -x "$bin/prettier" ]] && (cd "$root" && "$bin/prettier" --write --log-level warn "$file" 2>&1) >/dev/null
    case "$file" in
      *.vue|*.ts|*.tsx|*.js|*.mjs|*.cjs)
        if [[ -x "$bin/eslint" ]]; then
          out=$(cd "$root" && "$bin/eslint" --fix "$file" 2>&1) || errors+="$out"$'\n'
        fi ;;
    esac
    ;;
  *.dart)
    root=$(find_up pubspec.yaml) || exit 0
    if command -v dart >/dev/null; then
      (cd "$root" && dart format "$file" 2>&1) >/dev/null
      out=$(cd "$root" && dart analyze --fatal-infos "$file" 2>&1) || errors+="$out"$'\n'
    fi
    ;;
  *) exit 0 ;;
esac

# once per session, on the first code edit: make sure the secure-coding skill is in play
proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
case "$file" in
  "$proj"/backend/*.py|"$proj"/frontend/src/*|"$proj"/mobile/lib/*)
    mark="$proj/.claude/state/secguard-${sid:-default}"
    if [[ ! -e "$mark" && -z "${errors//[$'\n ']/}" ]]; then
      mkdir -p "$proj/.claude/state" && touch "$mark"
      printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"First code edit this session: load the secure-code-guardian skill (and the stack skill for this code: django-expert / vue-expert / typescript-pro / flutter-guidelines) if not already loaded, and run the security-reviewer skill on the diff before declaring the task done."}}'
    fi ;;
esac

if [[ -n "${errors//[$'\n ']/}" ]]; then
  printf 'Lint errors remain in %s — fix them before continuing:\n%s' "$file" "$(echo "$errors" | head -n 40)" >&2
  exit 2
fi
exit 0
