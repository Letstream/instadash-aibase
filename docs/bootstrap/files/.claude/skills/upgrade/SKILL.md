---
name: upgrade
description: Upgrade this project to the newer Instadash AI Base version placed in docs/bootstrap/ — compare versions, read the changelog, sync managed files via the manifest, merge locally modified files, apply manual code steps, and bump INSTADASH_BASE_VERSION. Use on /upgrade or when the user says they copied a new base/bootstrap folder in.
---

<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->

# Upgrade

Follow [`docs/bootstrap/upgrade.md`](../../../docs/bootstrap/upgrade.md) **exactly**; the helper is
`python3 docs/bootstrap/tools/instadash.py` (status / plan / apply / resolved / set-version), run from
the project root.

Guardrails:
- Never overwrite a `modified` file without showing the user the merge; never touch seed files
  (`docs/data-model.md`) or `DOCS.md` / `handoff.md` beyond logging the upgrade.
- Apply the changelog's manual steps as normal commits in the right repo, with tests.
- Finish with `set-version`, QA, and a `handoff.md` + `DOCS.md` §8 entry (from → to).
