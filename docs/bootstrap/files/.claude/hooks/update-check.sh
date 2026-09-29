#!/usr/bin/env bash
# Instadash AI Base (managed file) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com.
# Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use
# or redistribution is prohibited.
# SessionStart: at most once a day, check GitHub for a newer Instadash AI Base release. Silent when
# offline, up to date, not installed, or disabled (INSTADASH_NO_UPDATE_CHECK=1 or
# "update_check": false in .instadash.json). Output (if any) is added to the agent's context.
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
tool="$root/docs/bootstrap/tools/instadash.py"
[[ -f "$root/.instadash.json" && -f "$tool" ]] || exit 0
msg=$(cd "$root" && timeout 6 python3 "$tool" check-update --quiet --cached 2>/dev/null)
[[ -n "$msg" ]] && echo "BASE UPDATE AVAILABLE: $msg Mention this to the user once, briefly; don't upgrade without their go-ahead."
exit 0
