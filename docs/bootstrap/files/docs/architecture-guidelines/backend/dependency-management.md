<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Dependency Management (Poetry) & Tooling

> Poetry manages backend dependencies; all linter/formatter/coverage config is centralized in
> `pyproject.toml`; a `Makefile` and CI run the **same** commands so local == CI. The exact files are
> in [scaffold/project](../../bootstrap/scaffold/backend/project.md). See [testing](testing.md).

---

## 1. Python version

Use the **latest Python the system supports, minimum 3.12**. Write the constraint as:

```toml
python = ">=3.12,<4.0"
```

The floor (3.12) is the decision. The `<4.0` cap is a Poetry formality: the resolver refuses an
open-ended `>=3.12` as soon as any dependency declares `python_requires="<4"` (django-environ does).
The Docker image defaults to the newest supported CPython (`ARG PYTHON_VERSION`), and tool targets
(`black` `target-version = ["py312"]`, ruff `target-version = "py312"`) track the **minimum**.

---

## 2. Poetry setup

- One `pyproject.toml` in the backend working dir (`app/`), with `poetry.lock` committed.
- The project is an application, not a library — `package-mode = false` (no wheel built).
- **Two dependency groups**: main (runtime) and `dev` (tests, linters, formatters).

**Runtime baseline** (the scaffold pins caret ranges on current majors):

| Concern | Packages |
|---------|----------|
| Web/API | `django` (5.2 LTS), `djangorestframework`, `django-filter`, `django-cors-headers`, `drf-spectacular` |
| Config | `django-environ` |
| Data | `psycopg[binary]` (v3), `django-redis` |
| Async | `celery` (RabbitMQ broker via kombu/AMQP) |
| Storage | `django-storages[s3]`, `boto3` |
| Security/audit | `django-auditlog`, `nh3` |
| Ops | `gunicorn`, `uvicorn[standard]`, `sentry-sdk[django,celery]` |

**Dev baseline:** `pytest`, `pytest-django`, `pytest-cov`, `pytest-mock`, `django-dynamic-fixture`,
`black`, `ruff`, `codespell`. Opt-in features add their own (`channels`, `channels-redis`,
`pytest-asyncio` for [realtime](realtime-channels.md)).

Add deps with `poetry add <pkg>` (runtime) or `poetry add --group dev <pkg>`. Never hand-edit
`poetry.lock`. Never add product-specific SDKs to the base scaffold — they belong to the project.

---

## 3. In-project virtualenv

Force the venv inside the project so CI can cache it and editors/Docker find it deterministically:

```toml
# poetry.toml
[virtualenvs]
create = true
in-project = true          # → app/.venv  (gitignored, dockerignored)
```

---

## 4. Centralized tool config (all in `pyproject.toml`)

Keep formatter/linter/spell/coverage config in `pyproject.toml` — no scattered
`setup.cfg`/`.flake8`/`.coveragerc`.

```toml
[tool.black]
line-length = 88
target-version = ["py312"]
extend-exclude = '(migrations|static|staticfiles)'

[tool.ruff]
line-length = 88
target-version = "py312"
extend-exclude = ["migrations", "static", "staticfiles"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]   # pycodestyle, pyflakes, isort, bugbear, pyupgrade
ignore = ["E501"]                     # black owns line length

[tool.ruff.lint.isort]
known-first-party = ["app", "apps"]

[tool.codespell]
skip = ".git,*.lock,.venv,static,staticfiles,htmlcov,migrations"

[tool.coverage.run]
source = ["apps"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

- **Black** is the formatter; **Ruff** covers linting + import sorting (add `"D"` with the Google
  convention if the project enforces docstrings); **Codespell** catches typos in code and docs.
- Type checking (mypy/pyright) is recommended; add it to the dev group and CI when you adopt it.

---

## 5. Testing bootstrap (`pytest` + `pytest-django`)

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = app.settings.testing
pythonpath = .
testpaths = apps
python_files = test_*.py
norecursedirs = .git .venv */migrations/* static staticfiles node_modules
addopts = --tb=short --strict-markers -p no:warnings
```

Shared fixtures live in `app/conftest.py`; tests in each app's `tests/` package. Conventions,
fixtures and what to test: [testing](testing.md).

---

## 6. Makefile — local mirrors CI

A thin `Makefile` wraps `poetry run …` so contributors run exactly what CI runs:

```make
install:    ; poetry install --with dev
format:     ; poetry run ruff check --fix --select I . && poetry run black .
lint:       ; poetry run codespell && poetry run black --check . && poetry run ruff check .
test:       ; poetry run pytest --reuse-db --cov --cov-report=term-missing
test-fresh: ; poetry run pytest --create-db --cov --cov-report=term-missing
check:      ; poetry run python manage.py check && poetry run python manage.py makemigrations --check --dry-run
```

CI invokes the same targets (see [containerization-and-deployment](containerization-and-deployment.md)).
A change is **not done** until `make lint`, `make check` and `make test` pass.
