---
name: django-expert
description: "Use automatically whenever writing, changing or reviewing Django/DRF backend code in this project — models, managers/QuerySets, serializers, views, URLs, permissions, settings, migrations, admin, signals, Celery tasks and backend tests. Use when building Django web applications or REST APIs with Django REST Framework. Invoke when working with settings.py, models.py, manage.py, or any Django project file. Creates Django models with proper indexes, optimizes ORM queries using select_related/prefetch_related, builds DRF serializers and viewsets, and configures JWT authentication. Trigger terms: Django, DRF, Django REST Framework, Django ORM, Django model, serializer, viewset, Python web."
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: backend
  triggers: Django, DRF, Django REST Framework, Django ORM, Django model, serializer, viewset, Python web
  role: specialist
  scope: implementation
  output-format: code
  related-skills: fullstack-guardian, fastapi-expert, test-master, django-storages-s3
---

# Django Expert

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic examples below)

The examples in this skill are generic Django/DRF (SimpleJWT, `ModelViewSet` + router, `APITestCase`).
In Instadash projects the **canonical decisions** (`docs/architecture-guidelines/README.md`), the
backend guideline pages (`docs/architecture-guidelines/backend/`) and the project `DOCS.md` win on
any conflict:

| Upstream advice | Instadash equivalent |
|---|---|
| "Add auth — Permissions, JWT authentication"; SimpleJWT settings, `/api/token/` + refresh views, custom token claims, `Bearer` header (`references/authentication.md`, "Testing JWT") | Opaque, hashed, DB-backed tokens sent as `Authorization: Token <t>` (`user.issue_token()`, `revoke_all_tokens()`). **Never add `djangorestframework-simplejwt`**; JWT only for signed links. Login/logout/refresh live in `apps.accounts`. |
| "Setting up authentication (JWT, session)"; "Use Django's built-in security features (CSRF, etc.)" | Session auth is for the Django admin only (on the obfuscated `ADMIN_URL`); the API carries no ambient credentials, so CSRF stays on for admin/session views only. |
| `class ArticleViewSet(viewsets.ModelViewSet)` + `DefaultRouter` as the default shape (Minimal example, `references/viewsets-views.md`) | Auth tier by base class + DRF generic: `class OrderListView(AuthenticatedView, generics.ListAPIView)` (`AnonymousView` / `AuthenticatedView` / `AdminOnlyView` from `apps.core.views`). Explicit `path()` list in the app's `urls.py` (`app_name`, kebab-case, `<uuid:pk>`, `"<resource>-<action>"` names), mounted under `/api/<app>/`. ViewSets/routers only for custom `@action` verbs. |
| `permission_classes = [IsAuthenticatedOrReadOnly]`, `AllowAny`, `IsAdminUser`, per-action `get_permissions()`, custom `IsOwnerOrReadOnly` | Multi-tenant: declarative `org_permissions = [perms.X_READ]` checked by `HasOrgPermission` (vary by verb in `check_permissions`), `obj.is_accessible_by(user)` on writes. Single-tenant: `min_role` + `HasRole`. Public endpoints subclass `AnonymousView` explicitly. |
| `HasAPIKey` compares `request.headers['X-API-Key'] == settings.API_KEY` | Not a pattern here. If machine keys are ever needed, store them hashed and compare with `hmac.compare_digest` (the upstream `==` is timing-unsafe and single-secret). |
| Unscoped querysets: `Article.objects.select_related("author").all()`, `queryset = Product.objects…`; `serializer.save(author=self.request.user)` | `queryset = Model.objects.none()` (schema only) and `get_queryset()` returns `Model.objects.visible_to(request.user, request.organization)` (+ `select_related`/`prefetch_related`). Stamp the tenant on create: `serializer.save(organization=request.organization)`. Never trust a client-supplied org/owner id. |
| `PrimaryKeyRelatedField(queryset=Category.objects.all())` (`references/drf-serializers.md`) | Related-field querysets are narrowed to the caller's tenant (core `ForeignSerializerField`, narrowed in `__init__`); posting another tenant's id must fail validation. |
| `class Article(models.Model)` with `created_at`/`updated_at`; `"auth.User"`; `User(AbstractUser)` with `username` (`references/models-orm.md`) | Every model extends core `TimeStampedModel` (`created_on`/`modified_on`, already indexed), `UUIDTimeStampedModel` for URL-facing resources, abstract `OrgScopedModel` for tenant data. Custom `accounts.User` (email login, `AbstractBaseUser`) referenced via `settings.AUTH_USER_MODEL`. Register business/security models with `django-auditlog`. No soft-delete/ordered base. |
| Error responses built in views: `Response({'error': 'Insufficient stock'}, status=400)`, `{'message': …}` | Views return plain `Response(payload)`; `LetstreamAPIRenderer` wraps `{status, data, version}`. Errors: `raise self.DataInvalidError(...)` / `self.NotFoundError()` or an app `api_errors.py` exception with a namespaced `err_cd`. Never assemble the envelope by hand. |
| Business logic in views (`purchase` action decrements stock in the view) and nested writes in `Serializer.create()/update()` | Fat models / thin views: behaviour on model methods, custom QuerySets/managers, or a small service/helper class; do concurrent counters atomically (`F()` / `select_for_update()` in `transaction.atomic`). Serializers validate and persist. |
| `PageNumberPagination`, `PAGE_SIZE`, `max_page_size = 1000` | Global `apps.core.pagination.StandardPagination` (limit/offset, `PAGE_SIZE` 20) is the default; don't introduce per-view page classes without a reason. |
| Django 5.0 async views with `sync_to_async` returning `JsonResponse` | Keep DRF views sync on the core base classes (`JsonResponse` bypasses the envelope). Slow work goes to Celery tasks (RabbitMQ broker, idempotent, one worker per queue); async only in Channels consumers when a project opted into realtime. |
| `RegisterSerializer`/`RegisterView`, `CurrentUserView` examples | Already provided by `apps.accounts` (`/api/accounts/register/`, `/api/accounts/me/`) with Django password validators, DRF scoped throttles and `core.SecurityEvent` records — extend those, don't re-create. |
| "run `manage.py makemigrations` and `manage.py migrate`" | Yes, and only that way: `startapp <name> apps/<name>` for new apps, `makemigrations <app>` for schema changes — never hand-write a migration, and never run `makemigrations` from a parallel subagent. |
| Tests: `APITestCase`/`TestCase` classes, `setUp`, `force_authenticate`, JSON fixtures, factory_boy (`references/testing-django.md`) | pytest + pytest-django plain functions with the `app/conftest.py` fixtures (`auth_client`, `org_client`, `user_factory`, `organization`/`other_organization`) and `ddf` `G()`. Assert the envelope (`body["data"]`, `body["err_cd"]`), and add the **mandatory cross-tenant isolation test** for every tenant model/endpoint. |
| "Knowledge: drf-spectacular" (unspecified) | drf-spectacular is the schema tool (not drf-yasg); set `serializer_class` even on plain `APIView`s so the endpoint is described. |

Celery tasks, signals and admin are not covered upstream — follow
`docs/architecture-guidelines/backend/background-tasks-and-notifications.md`, `apps-architecture.md`
§1/§10 and `audit-logging.md`.
<!-- instadash: end -->

Senior Django specialist with deep expertise in Django 5.0, Django REST Framework, and production-grade web applications.

## When to Use This Skill

- Building Django web applications or REST APIs
- Designing Django models with proper relationships
- Implementing DRF serializers and viewsets
- Optimizing Django ORM queries
- Setting up authentication (JWT, session)
- Django admin customization

## Core Workflow

1. **Analyze requirements** — Identify models, relationships, API endpoints
2. **Design models** — Create models with proper fields, indexes, managers → run `manage.py makemigrations` and `manage.py migrate`; verify schema before proceeding
3. **Implement views** — DRF viewsets or Django 5.0 async views
4. **Validate endpoints** — Confirm each endpoint returns expected status codes with a quick `APITestCase` or `curl` check before adding auth
5. **Add auth** — Permissions, JWT authentication
6. **Test** — Django TestCase, APITestCase

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Models | `references/models-orm.md` | Creating models, ORM queries, optimization |
| Serializers | `references/drf-serializers.md` | DRF serializers, validation |
| ViewSets | `references/viewsets-views.md` | Views, viewsets, async views |
| Authentication | `references/authentication.md` | JWT, permissions, SimpleJWT |
| Testing | `references/testing-django.md` | APITestCase, fixtures, factories |

## Minimal Working Example

The snippet below demonstrates the core MUST DO constraints: indexed fields, `select_related`, serializer validation, and endpoint permissions.

```python
# models.py
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    author = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="articles"
    )
    published_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-published_at"]
        indexes = [models.Index(fields=["author", "published_at"])]

    def __str__(self):
        return self.title

# serializers.py
from rest_framework import serializers
from .models import Article

class ArticleSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Article
        fields = ["id", "title", "author_username", "published_at"]

    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return value.strip()

# views.py
from rest_framework import viewsets, permissions
from .models import Article
from .serializers import ArticleSerializer

class ArticleViewSet(viewsets.ModelViewSet):
    """
    Uses select_related to avoid N+1 on author lookups.
    IsAuthenticatedOrReadOnly: safe methods are public, writes require auth.
    """
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Article.objects.select_related("author").all()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
```

```python
# tests.py
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

class ArticleAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass")

    def test_list_public(self):
        res = self.client.get("/api/articles/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_create_requires_auth(self):
        res = self.client.post("/api/articles/", {"title": "Test"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_authenticated(self):
        self.client.force_authenticate(self.user)
        res = self.client.post("/api/articles/", {"title": "Hello Django"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
```

## Constraints

### MUST DO
- Use `select_related`/`prefetch_related` for related objects
- Add database indexes for frequently queried fields
- Use environment variables for secrets
- Implement proper permissions on all endpoints
- Write tests for models and API endpoints
- Use Django's built-in security features (CSRF, etc.)

### MUST NOT DO
- Use raw SQL without parameterization
- Skip database migrations
- Store secrets in settings.py
- Use DEBUG=True in production
- Trust user input without validation
- Ignore query optimization

## Output Templates

When implementing Django features, provide:
1. Model definitions with indexes
2. Serializers with validation
3. ViewSet or views with permissions
4. Brief note on query optimization

## Knowledge Reference

Django 5.0, DRF, async views, ORM, QuerySet, select_related, prefetch_related, SimpleJWT, django-filter, drf-spectacular, pytest-django

[Documentation](https://jeffallan.github.io/claude-skills/skills/backend/django-expert/)
