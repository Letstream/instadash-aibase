<!-- Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See README.md for terms. -->
# Upgrade — `/upgrade`

> Bring an installed project up to the base version now in `docs/bootstrap/` (the user copied a
> newer folder over it). Run from the project root.

1. **Compare versions.** `python3 docs/bootstrap/tools/instadash.py status` → installed vs available.
   Equal → nothing to do (offer `plan` to check for drift). Available older → stop and tell the user.
2. **Read the changelog** entries between the two versions in [CHANGELOG.md](./CHANGELOG.md) —
   note every *manual upgrade step*.
3. **Plan** (`… plan`) and summarise for the user: `new`, `update` (safe), `modified` (needs merge),
   `customized` (project edits on an unchanged base file — left alone), `removed-upstream`.
4. **Apply** (`… apply`) — copies `new` + `update`.
5. **Merge each `modified` file**: diff the project's copy against `docs/bootstrap/files/<path>`;
   adopt the base's changes, keep the project's intentional additions, and ask when they conflict.
   Then `… resolved <path>`.
6. **Removed upstream**: delete the installed copy unless the project still needs it (ask), then
   `… resolved <path>`.
7. **Code-level changes**: apply the changelog's manual steps to `backend/`, `frontend/`, `infra/`
   using the updated [scaffold](./scaffold/) as the reference (e.g. a changed core class or a new
   middleware) — in each repo, as normal commits, with tests.
8. **Set version**: `… set-version` → updates `.instadash.json` and `INSTADASH_BASE_VERSION` in the
   backend settings, so the `X-Letstream-Instadash-Version` header reports the new version.
9. **Verify** per [QA](../qa.md) (tests, lint, run, Chrome) and log the upgrade in `handoff.md`
   (from → to, merges made, manual steps done) and in `DOCS.md` §8 (decisions log).
