# Instadash AI Base

**An opinionated, AI-agent-ready foundation for building production SaaS products with Claude Code
(and other coding agents).** Drop one folder into a project and your agent gets a complete rulebook,
architecture guidelines, exact starter code, safety hooks and vetted skills — so every project it
builds looks, behaves and scales the same way.

By [Letstream](https://www.theletstream.com).

---

## What you get

| | |
|---|---|
| **Stack** | Django 5 + DRF backend · Vue 3 + PrimeVue 4 + Tailwind v4 web app · optional Flutter mobile app · PostgreSQL · Redis · RabbitMQ + Celery · Docker Compose |
| **Agent rulebook** | `AGENTS.md` + `CLAUDE.md`: read-docs-first, write-docs-always, QA-before-done, security rules, multi-agent protocol |
| **Architecture guidelines** | Backend, frontend and mobile pages with a single *Canonical decisions* table (auth, tenancy, envelope, base models, tests, infra…) |
| **Scaffolds** | Exact, tested starter code for `backend/`, `frontend/` and `mobile/`, kept as Markdown and materialised on demand |
| **Guided flows** | `/bootstrap` (new project interview) · `/migrate-to-instadash` (move an existing app onto this stack) · `/upgrade` (adopt a newer base) · `/skills-hub` (find + vet more skills) |
| **Hooks** | Auto-format + lint on every edit, license header insertion, Bootstrap gate, "update `handoff.md` before you stop" enforcement, secure-coding reminder |
| **Skills** | Our own (`frontend-design-guidelines`, `flutter-guidelines`, …) plus reviewed, stack-adapted skills for Django, Python, Vue, TypeScript, testing, architecture, databases and security |
| **Security & compliance** | Tenant isolation rules, opaque hashed tokens, audit logging, secrets hygiene, SOC 2 control mapping |
| **Lineage** | Every project records the base version it's on and can be upgraded safely via a hash-based manifest |

## Quick start

**Requirements:** [Claude Code](https://claude.com/claude-code) (or another agent that reads
`AGENTS.md`), Python ≥ 3.12, Poetry, Node 22, Docker + Compose v2. Flutter only if you build mobile.

1. **Copy the base into your project**
   ```bash
   mkdir -p my-product/docs
   cp -r instadash-ai-base/docs/bootstrap my-product/docs/
   cd my-product
   ```
2. **Install it** — start your agent in `my-product/` and say:
   > Read docs/bootstrap folder and do the initial steps

   It copies the rulebook, hooks, skills and docs into place and writes `.instadash.json`.
3. **Restart the agent session.** Hooks and the new slash commands only load when a session starts.
4. **Set up the project**
   - New product → **`/bootstrap`** (or just type `Bootstrap`). The agent interviews you — what
     you're building, reference docs, legal entity, tenancy, platforms (web / mobile), ports, and
     whether to use your existing Postgres/Redis/RabbitMQ or spin up a dedicated Docker Compose stack
     — then writes `DOCS.md` + `handoff.md`, creates the `infra/` repo, materialises the scaffolds,
     and verifies everything runs.
   - Existing app (Flask, Express, PHP, a template-based Django site…) → **`/migrate-to-instadash`**.
     The agent inventories the codebase, interviews you, writes a migration plan for approval, then
     rebuilds it slice by slice with data import and parity checks. The legacy app stays untouched
     until you sign off.

## Commands

| Command | What it does |
|---|---|
| `/bootstrap` · `Bootstrap` | Interview → `DOCS.md`, `handoff.md`, `.env` files, `infra/`, scaffolds, `scripts/dev.sh` |
| `/migrate-to-instadash` | Discovery → interview → approved plan → rebuild in slices → data rehearsal → cut-over |
| `/upgrade` · `Upgrade` | Sync a newer base: safe updates, guided merges, version bump |
| `/skills-hub` | Find, review and vendor additional skills for a requirement |

## Project layout after Bootstrap

```
my-product/                 # shared docs & agent config (not a git repo)
├── AGENTS.md  CLAUDE.md    # agent rulebook (managed by the base)
├── DOCS.md                 # the project's single source of truth
├── handoff.md              # human-readable build journal
├── .instadash.json         # base version + managed-file manifest
├── .claude/                # settings, hooks, skills
├── docs/
│   ├── bootstrap/          # this base (replaced on upgrade)
│   ├── architecture-guidelines/  setup.md  infra.md  security.md  qa.md  …
├── scripts/dev.sh          # starts everything on the project's ports
├── backend/                # git repo — Django + DRF
├── frontend/               # git repo — Vue 3 + PrimeVue + Tailwind
├── mobile/                 # git repo — Flutter (only if the project has a mobile app)
└── infra/                  # git repo — Docker Compose (data in infra/docker/data/, gitignored)
```

## Upgrading a project

Copy the newer `docs/bootstrap/` over the old one, restart the agent, run **`/upgrade`**. Untouched
managed files are replaced automatically; files your project customised are merged with your
confirmation; `INSTADASH_BASE_VERSION` and the manifest are bumped. See
[`docs/bootstrap/upgrade.md`](docs/bootstrap/upgrade.md) and the
[changelog](docs/bootstrap/CHANGELOG.md).

## Repository layout

```
docs/bootstrap/             # ← the whole shippable base
├── README.md  VERSION  CHANGELOG.md
├── install.md  interview.md  migrate.md  upgrade.md  license-header.md  skills-hub.md
├── files/                  # installed into projects (AGENTS.md, CLAUDE.md, .claude/, docs/)
├── scaffold/               # backend/, frontend/, mobile/ starter code as Markdown
├── skills/                 # optional skills enabled per project
├── templates/              # DOCS.md and handoff.md templates
└── tools/instadash.py      # install / upgrade / skill helper
```

Start with [`docs/bootstrap/README.md`](docs/bootstrap/README.md).

## Contributing

Issues and suggestions are welcome. Changes to the base go under `docs/bootstrap/`; bump `VERSION`,
add a `CHANGELOG.md` entry (with any manual upgrade steps), and verify a simulated install plus the
affected scaffold before opening a pull request — see [CLAUDE.md](CLAUDE.md). Please don't include
credentials, customer data or internal hostnames in issues or pull requests.

## Third-party content

Several skills under `docs/bootstrap/files/.claude/skills/` and `docs/bootstrap/skills/` are vendored
from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills) under the MIT License.
Each keeps its `LICENSE` and an `UPSTREAM.md` describing the source commit and local modifications.
Those files remain under their original license.

## Contact

Letstream Ventures Pvt Ltd — [theletstream.com](https://www.theletstream.com) —
[hello@theletstream.com](mailto:hello@theletstream.com)

---

<sub>

**Instadash AI Base** — Copyright (c) Letstream Ventures Pvt Ltd. All rights reserved.
(Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).

The Instadash AI Base template is provided "AS IS", without warranty of any kind, express or
implied, including merchantability, fitness for a particular purpose and non-infringement, unless
covered by an explicit written agreement with Letstream Ventures Pvt Ltd. Unauthorized use,
copying, modification or redistribution of the template, in whole or in part, is prohibited and may
result in legal action and remedies available under applicable law. Third-party components are
licensed under their own terms as noted above.

</sub>
