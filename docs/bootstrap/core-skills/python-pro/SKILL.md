---
name: python-pro
description: Use automatically whenever writing, changing or reviewing any Python code in this project (backend apps, services and helper classes, management commands, Celery tasks, tests, pyproject/Poetry tooling). Use when building Python 3.11+ applications requiring type safety, async programming, or robust error handling. Generates type-annotated Python code, configures mypy in strict mode, writes pytest test suites with fixtures and mocking, and validates code with black and ruff. Invoke for type hints, async/await patterns, dataclasses, dependency injection, logging configuration, and structured error handling.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: language
  triggers: Python development, type hints, async Python, pytest, mypy, dataclasses, Python best practices, Pythonic code
  role: specialist
  scope: implementation
  output-format: code
  related-skills: fastapi-expert, devops-engineer
---

# Python Pro

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic examples below)

The examples in this skill target a generic, library-style Python 3.11 package. In Instadash
projects the **canonical decisions** (`docs/architecture-guidelines/README.md`),
`docs/architecture-guidelines/backend/dependency-management.md`, `backend/testing.md` and the
project `DOCS.md` win on any conflict:

| Upstream advice | Instadash equivalent |
|---|---|
| "Python 3.11+"; `python_version = "3.11"`, `target-version = "py311"`, `python = "^3.11"` | Latest supported Python, **minimum 3.12**: `python = ">=3.12,<4.0"`; black `target-version = ["py312"]`, ruff `target-version = "py312"`. |
| Validate with `mypy --strict`; "Ignore mypy errors in strict mode" is a MUST NOT; "mypy --strict passes" in the output template | Type hints on every signature are required, but the project gate is `make lint` (codespell + `black --check` + `ruff check`), `make check` and `make test`. mypy/pyright is optional — adopt it only as a recorded project decision; don't add a strict mypy config unasked. |
| "Test coverage exceeding 90%"; `--cov-fail-under=90` | Coverage floor is `fail_under = 80` in `pyproject.toml` (security-critical paths — auth, permissions, tenancy — aim for full branch coverage). Don't change the configured threshold. |
| Tool config: line-length 100, top-level `[tool.ruff] select`, extra rule sets (`W`, `C4`), per-file ignores | Use the scaffold's `pyproject.toml` as is: line-length 88, `[tool.ruff.lint] select = ["E","F","I","B","UP"]`, `ignore = ["E501"]`, isort first-party `app`/`apps`, codespell config. Don't rewrite tool config. |
| Packaging: hatchling / PEP 621 `[project]`, `src/` layout, `py.typed`, `setup.py`, `MANIFEST.in`, `poetry build/publish`, `twine upload`, `requirements*.txt`, `pip install -e`, `pip freeze` (`references/packaging.md`) | The backend is an application, not a library: Poetry with `package-mode = false`, in-project `.venv` (`poetry.toml`), `poetry add <pkg>` / `poetry add --group dev <pkg>`, committed `poetry.lock` (never hand-edited). Layout is Django's `app/` project package + `apps/<name>`. Never publish packages. |
| `poetry shell` | Use `poetry run …` (or the `Makefile` targets that wrap it). |
| GitHub Actions with `pip install -e ".[dev]"`, Codecov, pre-commit mirrors | CI runs exactly `make lint`, `make check`, `make test` (see `backend/containerization-and-deployment.md`). Add Codecov/pre-commit only as a project decision. |
| "Async/await for I/O-bound operations"; `httpx` + `asyncio.gather`; `sync_wrapper` creating a new event loop | Django/DRF request code is sync. Slow or external I/O goes to Celery tasks (RabbitMQ broker, small, idempotent, `acks_late`); async code lives only in Channels consumers when a project opted into realtime. Never spin up event loops inside a request. |
| Tests against SQLite/SQLAlchemy sessions (`Database("test.db")`), engines parametrized over sqlite/postgresql/mysql, `@pytest.mark.asyncio` (`references/testing.md`) | pytest + pytest-django against real PostgreSQL (`pytest.mark.django_db`), fixtures from `app/conftest.py`, `ddf` `G()` for rows, `mocker` (pytest-mock), the `settings` fixture, `mailoutbox`. `pytest-asyncio` only for the realtime opt-in. `hypothesis`/`syrupy` are not in the baseline — add via `poetry add --group dev` only by decision. |
| `logging.basicConfig(...)` with a `FileHandler('app.log')` | Logging is configured once in Django `LOGGING` (level from `LOG_LEVEL`, stdout for containers, Sentry). Never log secrets, tokens or PII; security events go through `core.SecurityEvent.record()`. |
| `query_user` builds SQL with an f-string (`f"SELECT * FROM users WHERE id = {user_id}"`, `references/type-system.md`); `AsyncDatabaseConnection.query(sql)` | SQL-injection anti-pattern — never copy it. Django ORM only; raw SQL only as `cursor.execute(sql, params)`. |
| `@lru_cache` on a DB-backed `fetch_user()` (`references/standard-library.md`) | Don't cache DB or tenant data in process-local caches (stale across workers, cross-tenant leak risk). Use the Redis-backed Django cache with tenant-keyed keys, or the core Options registry for runtime settings. |
| "Dataclasses over manual `__init__`"; Pydantic in the knowledge list | Domain state lives in Django models; request validation in DRF serializers. Dataclasses are fine for plain value objects inside services; Pydantic is not part of the baseline. |
| Loose module-level helper functions | OOP-first: behaviour on models / custom QuerySets, or namespaced helper classes (`class LinkValidationUtils: @staticmethod …`) grouped by concern. Google-style docstrings, as upstream says. |
<!-- instadash: end -->

Modern Python 3.11+ specialist focused on type-safe, async-first, production-ready code.

## When to Use This Skill

- Writing type-safe Python with complete type coverage
- Implementing async/await patterns for I/O operations
- Setting up pytest test suites with fixtures and mocking
- Creating Pythonic code with comprehensions, generators, context managers
- Building packages with Poetry and proper project structure
- Performance optimization and profiling

## Core Workflow

1. **Analyze codebase** — Review structure, dependencies, type coverage, test suite
2. **Design interfaces** — Define protocols, dataclasses, type aliases
3. **Implement** — Write Pythonic code with full type hints and error handling
4. **Test** — Create comprehensive pytest suite with >90% coverage
5. **Validate** — Run `mypy --strict`, `black`, `ruff`
   - If mypy fails: fix type errors reported and re-run before proceeding
   - If tests fail: debug assertions, update fixtures, and iterate until green
   - If ruff/black reports issues: apply auto-fixes, then re-validate

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Type System | `references/type-system.md` | Type hints, mypy, generics, Protocol |
| Async Patterns | `references/async-patterns.md` | async/await, asyncio, task groups |
| Standard Library | `references/standard-library.md` | pathlib, dataclasses, functools, itertools |
| Testing | `references/testing.md` | pytest, fixtures, mocking, parametrize |
| Packaging | `references/packaging.md` | poetry, pip, pyproject.toml, distribution |

## Constraints

### MUST DO
- Type hints for all function signatures and class attributes
- PEP 8 compliance with black formatting
- Comprehensive docstrings (Google style)
- Test coverage exceeding 90% with pytest
- Use `X | None` instead of `Optional[X]` (Python 3.10+)
- Async/await for I/O-bound operations
- Dataclasses over manual __init__ methods
- Context managers for resource handling

### MUST NOT DO
- Skip type annotations on public APIs
- Use mutable default arguments
- Mix sync and async code improperly
- Ignore mypy errors in strict mode
- Use bare except clauses
- Hardcode secrets or configuration
- Use deprecated stdlib modules (use pathlib not os.path)

## Code Examples

### Type-annotated function with error handling
```python
from pathlib import Path

def read_config(path: Path) -> dict[str, str]:
    """Read configuration from a file.

    Args:
        path: Path to the configuration file.

    Returns:
        Parsed key-value configuration entries.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If a line cannot be parsed.
    """
    config: dict[str, str] = {}
    with path.open() as f:
        for line in f:
            key, _, value = line.partition("=")
            if not key.strip():
                raise ValueError(f"Invalid config line: {line!r}")
            config[key.strip()] = value.strip()
    return config
```

### Dataclass with validation
```python
from dataclasses import dataclass, field

@dataclass
class AppConfig:
    host: str
    port: int
    debug: bool = False
    allowed_origins: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port: {self.port}")
```

### Async pattern
```python
import asyncio
import httpx

async def fetch_all(urls: list[str]) -> list[bytes]:
    """Fetch multiple URLs concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return [r.content for r in responses]
```

### pytest fixture and parametrize
```python
import pytest
from pathlib import Path

@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.txt"
    cfg.write_text("host=localhost\nport=8080\n")
    return cfg

@pytest.mark.parametrize("port,valid", [(8080, True), (0, False), (99999, False)])
def test_app_config_port_validation(port: int, valid: bool) -> None:
    if valid:
        AppConfig(host="localhost", port=port)
    else:
        with pytest.raises(ValueError):
            AppConfig(host="localhost", port=port)
```

### mypy strict configuration (pyproject.toml)
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

Clean `mypy --strict` output looks like:
```
Success: no issues found in 12 source files
```
Any reported error (e.g., `error: Function is missing a return type annotation`) must be resolved before the implementation is considered complete.

## Output Templates

When implementing Python features, provide:
1. Module file with complete type hints
2. Test file with pytest fixtures
3. Type checking confirmation (mypy --strict passes)
4. Brief explanation of Pythonic patterns used

## Knowledge Reference

Python 3.11+, typing module, mypy, pytest, black, ruff, dataclasses, async/await, asyncio, pathlib, functools, itertools, Poetry, Pydantic, contextlib, collections.abc, Protocol

[Documentation](https://jeffallan.github.io/claude-skills/skills/language/python-pro/)
