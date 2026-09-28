<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Backend Testing

> Every backend change ships with tests, and `make test` must pass (coverage ≥ 80%) before anything
> is "done". The stack: **pytest + pytest-django + pytest-cov**, with **pytest-mock** for patching and
> **django-dynamic-fixture** (`ddf`) for quick model instances. Tests run against a real PostgreSQL;
> everything else (cache, email, Celery) is in-process. The shared fixtures and example suites are
> in the scaffold ([project](../../bootstrap/scaffold/backend/project.md) → `conftest.py`,
> [core](../../bootstrap/scaffold/backend/core.md), [accounts](../../bootstrap/scaffold/backend/accounts.md),
> [organization](../../bootstrap/scaffold/backend/organization.md)). See [dependency-management](dependency-management.md),
> [multi-tenancy](multi-tenancy.md).

---

## 1. Layout & settings

```
app/
  pytest.ini                 # DJANGO_SETTINGS_MODULE = app.settings.testing, testpaths = apps
  conftest.py                # project-wide fixtures (clients, users, orgs)
  app/settings/testing.py    # the testing settings module
  apps/<app>/tests/
    __init__.py
    test_models.py           # model methods, managers/querysets
    test_api.py              # endpoints: happy + error paths, envelope, permissions, isolation
    test_tasks.py            # Celery tasks
```

- One `tests/` **package** per app (keep `__init__.py` — module names like `test_api.py` repeat
  across apps). Delete the `tests.py` that `startapp` generates.
- File names `test_*.py`; test functions `test_<behaviour>()`; plain functions + fixtures, no
  `unittest.TestCase` classes unless you need one.
- `testing.py` (selected directly by `pytest.ini`): `DEBUG=False` (so Django's JSON error handlers
  run), locmem cache and email, `CELERY_TASK_ALWAYS_EAGER=True` + `CELERY_TASK_EAGER_PROPAGATES=True`
  with a `memory://` broker, local-filesystem storage, MD5 password hasher (speed only). PostgreSQL
  comes from the same `DB_*` variables as every environment; pytest-django creates `test_<DB_NAME>`
  (the DB user needs `CREATEDB`).

---

## 2. Running

```bash
make test         # poetry run pytest --reuse-db --cov --cov-report=term-missing
make test-fresh   # --create-db: after changing migrations or when the test DB is stale
poetry run pytest apps/orders -k isolation -x     # focused run while iterating
```

- `--reuse-db` keeps the test database between runs (fast); use `make test-fresh` after migration
  changes.
- Coverage is configured in `pyproject.toml` (`source = ["apps"]`, migrations/tests omitted,
  **`fail_under = 80`**). Don't lower the bar — add tests. New code should be well above it;
  security-critical paths (auth, permissions, tenancy) aim for full branch coverage.
- CI runs exactly `make lint`, `make check`, `make test` against a PostgreSQL service
  ([containerization-and-deployment](containerization-and-deployment.md) §4).

---

## 3. Fixtures (`app/conftest.py`)

| Fixture | Gives you |
|---------|-----------|
| `_clear_cache` (autouse) | a clean cache per test (throttles, Options) |
| `password` | the known plaintext password of factory users |
| `api_client` | an anonymous `APIClient` |
| `user_factory` | `user_factory(**fields)` → user with the known password and a unique email |
| `user` | "Alice" (`alice@example.com`) |
| `auth_client_factory` | `auth_client_factory(user, organization=None)` → client with `Authorization: Token …` (and `X-Organization-Id` when an org is given) |
| `auth_client` | Alice, token-authenticated, no tenant header |
| `multi_tenant` | skips the test unless `TENANCY_MODE=multi` |
| `organization` / `other_organization` | Org A (owned by Alice) / Org B (owned by Bob, Alice has **no** access) |
| `other_user` | "Bob" |
| `member_role` | the global "Member" role |
| `member` | "Carol", a Member of Org A |
| `org_client` | Alice scoped to Org A |

Organization fixtures import tenancy models lazily and skip in single-tenant projects, so the same
`conftest.py` works in both modes. Use `ddf` for incidental rows:

```python
from ddf import G

order = G(Order, organization=organization, status="open")   # fills required fields for you
```

Prefer real objects over mocks for anything in your own database; mock only boundaries (email
providers, HTTP APIs, `.delay`).

---

## 4. What to test

### Models, managers, querysets
Behaviour lives on models, so that's where most unit tests go: methods, `save()` side effects,
factory classmethods, custom querysets (`active()`, `for_org()`, `visible_to()`), and constraints
(`pytest.raises(IntegrityError)`).

### Tenant isolation — **mandatory for every tenant model**
For **each** `OrgScopedModel` subclass and each endpoint exposing it, a test must prove that a user
of org A **cannot see or modify** org B's rows — at the queryset level *and* the API level:

```python
pytestmark = pytest.mark.django_db


def test_orders_are_isolated_per_tenant(user, organization, other_organization, org_client):
    mine = G(Order, organization=organization)
    theirs = G(Order, organization=other_organization)

    # queryset level
    assert list(Order.objects.visible_to(user, organization)) == [mine]
    assert not Order.objects.visible_to(user, other_organization).exists()

    # API level: list never leaks, detail/update of a foreign row is 404/403, never 200
    ids = {row["id"] for row in org_client.get("/api/orders/list/").json()["data"]["results"]}
    assert str(theirs.pk) not in ids
    assert org_client.get(f"/api/orders/{theirs.pk}/").status_code in (403, 404)
    assert org_client.patch(f"/api/orders/{theirs.pk}/", {"name": "x"}).status_code in (403, 404)


def test_foreign_tenant_header_is_rejected(auth_client_factory, user, other_organization):
    response = auth_client_factory(user, other_organization).get("/api/orders/list/")
    assert response.status_code == 403
```

Also test RBAC: a member **without** the view's `org_permissions` code gets 403; with it, 2xx. In
single-tenant projects test `min_role` boundaries (guest/member/admin/owner) the same way.

### Serializers
Validation rules (required fields, cross-field `validate()`, uniqueness, allowed values), read-only
fields staying read-only, and related-field querysets narrowed to the tenant (posting another
tenant's id must fail).

### Views — happy and error paths, envelope shape
Every endpoint: one happy path asserting status + `data`, and the relevant error paths asserting
status + `err_cd`. Assert the envelope contract, not just status codes:

```python
body = response.json()
assert body["status"] is False
assert body["err_cd"] == ERR_DATA_INVALID           # import codes; never hard-code strings twice
assert "email" in body["error"]
assert "data" not in body
```

Cover unauthenticated (401 `E-C-COR-0005`), forbidden (403), not found (404), validation (400) and
throttled (429) where applicable.

### Celery tasks
Tasks run eagerly in tests. Test the task function directly for its effect, and test the *enqueue*
separately where the call site matters:

```python
def test_export_task_writes_file(organization):
    result = export_orders(organization_id=str(organization.pk))
    assert result["rows"] == 0


def test_invite_enqueues_email(org_client, member_role, mailoutbox):
    org_client.post("/api/organization/invites/", {"email": "d@example.com", "role_id": str(member_role.pk)})
    assert len(mailoutbox) == 1                      # eager send_email → locmem backend


def test_no_email_for_unknown_address(api_client, mocker):
    delay = mocker.patch("apps.accounts.views.send_email.delay")
    api_client.post("/api/accounts/password-reset/", {"email": "nobody@example.com"})
    delay.assert_not_called()
```

Idempotency deserves a test for any task that can be re-delivered: run it twice, assert one effect.

### Audit & security
Security events are recorded (and contain no secrets), auditlog attributes the actor under token
auth, append-only guards hold — see [audit-logging](audit-logging.md) §9.

---

## 5. Conventions

- Mark DB tests with `pytest.mark.django_db` (module-level `pytestmark` is fine); tests that need
  real transactions (`on_commit`, Channels) use `@pytest.mark.django_db(transaction=True)` — or the
  `django_capture_on_commit_callbacks` fixture.
- Override settings with the pytest-django `settings` fixture, never by mutating `django.conf.settings`.
- Use `mailoutbox` for email assertions and `mocker` (pytest-mock) for patches; patch where the name
  is *looked up* (`apps.accounts.views.send_email.delay`), not where it's defined.
- Keep tests independent (no ordering assumptions) and fast; no network, no sleeping.
- A bug fix starts with a failing test that reproduces it.
