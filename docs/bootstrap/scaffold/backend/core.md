# Scaffold — `apps/core`

> The shared foundation: abstract base models, the append-only `SecurityEvent`, the Options
> registry, error codes, exceptions + global handler, `LetstreamAPIRenderer`, parsers,
> pagination, permissions, base views + health check, audit middleware, utilities, reusable
> serializer fields, tasks, admin and tests. **No domain models.**
> Rationale: [apps-architecture](../../../architecture-guidelines/backend/apps-architecture.md),
> [core-app-reference](../../../architecture-guidelines/backend/core-app-reference.md),
> [audit-logging](../../../architecture-guidelines/backend/audit-logging.md). Index: [README](README.md).

Created with `django-admin startapp core apps/core`; overwrite the generated files with these and
delete `apps/core/tests.py` and `apps/core/views.py`'s placeholder content.

---

### `app/apps/core/apps.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"
```

### `app/apps/core/models.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Abstract base models every app builds on, plus core's cross-cutting tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from django.core.cache import cache
from django.db import models

from .utils import RequestUtils


class TimeStampedModel(models.Model):
    """`created_on` / `modified_on` — EVERY model extends this (directly or via a base)."""

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Keep `modified_on` fresh even on partial `update_fields` saves."""
        update_fields = kwargs.get("update_fields")
        if update_fields and "modified_on" not in update_fields:
            kwargs["update_fields"] = [*update_fields, "modified_on"]
        super().save(*args, **kwargs)


class UUIDTimeStampedModel(TimeStampedModel):
    """TimeStampedModel with a non-enumerable UUID primary key (URL-facing resources)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Options(TimeStampedModel):
    """DB-backed, cache-fronted runtime settings. Read via `apps.core.options.Option`."""

    CACHE_PREFIX = "option:"

    key = models.CharField(max_length=128, unique=True)
    value = models.TextField(blank=True)
    label = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "option"
        verbose_name_plural = "options"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.label or self.key

    @classmethod
    def cache_key(cls, key: str) -> str:
        """Cache key for one option."""
        return f"{cls.CACHE_PREFIX}{key}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist, then invalidate the cached value."""
        super().save(*args, **kwargs)
        cache.delete(self.cache_key(self.key))

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Delete, then invalidate the cached value."""
        cache.delete(self.cache_key(self.key))
        return super().delete(*args, **kwargs)


class ImmutableRecordError(RuntimeError):
    """Raised on any attempt to change or delete an append-only record."""


class SecurityEventQuerySet(models.QuerySet):
    """Append-only: bulk update/delete are blocked; retention uses `purge_older_than`."""

    def update(self, **kwargs: Any) -> int:
        raise ImmutableRecordError("Security events are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableRecordError("Security events are append-only.")

    def purge_older_than(self, cutoff: datetime) -> int:
        """Retention purge — the ONLY sanctioned deletion path (run by a periodic task)."""
        deleted, _ = models.QuerySet.delete(self.filter(created_on__lt=cutoff))
        return deleted


class SecurityEvent(TimeStampedModel):
    """Append-only security/audit trail for events that are not model diffs.

    Model field changes are captured by django-auditlog (`auditlog.LogEntry`); this table
    records authentication and authorization events (SOC 2 CC6/CC7 evidence). Actor and
    tenant are stored as plain identifiers so the trail survives user/org deletion.
    """

    class Type(models.TextChoices):
        USER_REGISTERED = "user_registered", "User registered"
        LOGIN_SUCCEEDED = "login_succeeded", "Login succeeded"
        LOGIN_FAILED = "login_failed", "Login failed"
        LOGOUT = "logout", "Logout"
        TOKEN_ISSUED = "token_issued", "Token issued"
        TOKEN_REVOKED = "token_revoked", "Token revoked"
        PASSWORD_RESET_REQUESTED = (
            "password_reset_requested",
            "Password reset requested",
        )
        PASSWORD_CHANGED = "password_changed", "Password changed"
        ROLE_CHANGED = "role_changed", "Role/permission changed"
        MEMBER_INVITED = "member_invited", "Member invited"
        INVITE_ACCEPTED = "invite_accepted", "Invite accepted"
        MEMBER_REMOVED = "member_removed", "Member removed"
        DATA_EXPORTED = "data_exported", "Data exported"
        HARD_DELETED = "hard_deleted", "Hard delete"
        INTEGRATION_CONNECTED = "integration_connected", "Integration connected"
        INTEGRATION_DISCONNECTED = (
            "integration_disconnected",
            "Integration disconnected",
        )

    event_type = models.CharField(max_length=64, choices=Type.choices, db_index=True)
    actor_id = models.CharField(max_length=64, blank=True, db_index=True)
    actor_email = models.EmailField(blank=True)
    organization_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = SecurityEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_on"]
        indexes = [models.Index(fields=["event_type", "created_on"])]

    def __str__(self) -> str:
        return f"{self.event_type} by {self.actor_email or 'anonymous'} at {self.created_on}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Insert only — an existing event can never be modified."""
        if not self._state.adding:
            raise ImmutableRecordError("Security events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableRecordError("Security events are append-only.")

    @classmethod
    def record(
        cls,
        event_type: str,
        *,
        request: Any = None,
        actor: Any = None,
        organization: Any = None,
        **metadata: Any,
    ) -> SecurityEvent:
        """Append one event. Never pass secrets (passwords, tokens, OTPs) in metadata."""
        if actor is None and request is not None:
            user = getattr(request, "user", None)
            actor = user if user is not None and user.is_authenticated else None
        if organization is None and request is not None:
            organization = RequestUtils.get_organization(request)
        return cls.objects.create(
            event_type=event_type,
            actor_id=str(actor.pk) if actor is not None else "",
            actor_email=getattr(actor, "email", "") or "",
            organization_id=str(organization.pk) if organization else "",
            ip_address=RequestUtils.get_client_ip(request) if request else None,
            user_agent=RequestUtils.get_user_agent(request) if request else "",
            metadata=metadata,
        )
```

### `app/apps/core/options.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Typed facade over the Options table: enum keys, defaults, cache-through reads."""

from __future__ import annotations

from enum import StrEnum

from django.core.cache import cache

from .models import Options


class Option:
    """Runtime-editable settings (editable in the admin; no deploy needed).

    Use `.env` for secrets and anything security-critical; use Options for values
    operators tune live (feature switches, limits, support addresses).
    """

    CACHE_TTL = 60 * 60

    class Keys(StrEnum):
        SIGNUP_ENABLED = "signup_enabled"
        SUPPORT_EMAIL = "support_email"

    # key → (default value, human label)
    DEFAULTS: dict[str, tuple[str, str]] = {
        Keys.SIGNUP_ENABLED: ("true", "Allow self-serve registration"),
        Keys.SUPPORT_EMAIL: ("", "Support e-mail shown in outgoing mail"),
    }

    @classmethod
    def get(cls, key: Option.Keys) -> str:
        """Return the value: cache → DB → default."""
        cache_key = Options.cache_key(key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        value = Options.objects.filter(key=key).values_list("value", flat=True).first()
        if value is None:
            value = cls.DEFAULTS.get(key, ("", ""))[0]
        cache.set(cache_key, value, cls.CACHE_TTL)
        return value

    @classmethod
    def get_bool(cls, key: Option.Keys) -> bool:
        """Interpret the value as a boolean ("true"/"1"/"yes"/"on")."""
        return cls.get(key).strip().lower() in {"true", "1", "yes", "on"}

    @classmethod
    def set(cls, key: Option.Keys, value: str) -> None:
        """Write the value (the model's save() invalidates the cache)."""
        label = cls.DEFAULTS.get(key, ("", ""))[1]
        option, _ = Options.objects.get_or_create(key=key, defaults={"label": label})
        option.value = value
        option.save()
```

### `app/apps/core/api_errors.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Core error codes: E-<class>-<APP>-NNNN. A stable contract the frontend switches on."""

ERR_BASE = "E-"
APP_BASE = ERR_BASE + "C-COR-"

ERR_MISSING_PARAMETERS = APP_BASE + "0001"
ERR_PERMISSION_DENIED = APP_BASE + "0002"
ERR_NOT_FOUND = APP_BASE + "0003"
ERR_DATA_INVALID = APP_BASE + "0004"
ERR_UNAUTHORIZED = APP_BASE + "0005"
ERR_SERVER_ERROR = APP_BASE + "0006"
ERR_THROTTLED = APP_BASE + "0007"
ERR_METHOD_NOT_ALLOWED = APP_BASE + "0008"

MSG_DATA_INVALID = "Some data is invalid, please check."
MSG_UNAUTHORIZED = "You are not authenticated, please log in and try again."
MSG_PERMISSION_DENIED = (
    "Permission denied: you are not allowed to access this resource."
)
MSG_NOT_FOUND = "The requested resource was not found."
MSG_SERVER_ERROR = "The server encountered an error."

_DEFAULTS: dict[int, tuple[str, str]] = {
    400: (ERR_DATA_INVALID, MSG_DATA_INVALID),
    401: (ERR_UNAUTHORIZED, MSG_UNAUTHORIZED),
    403: (ERR_PERMISSION_DENIED, MSG_PERMISSION_DENIED),
    404: (ERR_NOT_FOUND, MSG_NOT_FOUND),
    405: (ERR_METHOD_NOT_ALLOWED, "This method is not allowed."),
    429: (ERR_THROTTLED, "Too many requests, please slow down."),
    500: (ERR_SERVER_ERROR, MSG_SERVER_ERROR),
}


def default_error_for(status_code: int) -> tuple[str, str]:
    """Map an HTTP status to its default (err_cd, err_msg)."""
    if status_code in _DEFAULTS:
        return _DEFAULTS[status_code]
    if status_code >= 500:
        return _DEFAULTS[500]
    return _DEFAULTS[400]
```

### `app/apps/core/api_exceptions.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Custom API exceptions and the global DRF exception handler."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .api_errors import (
    ERR_DATA_INVALID,
    ERR_MISSING_PARAMETERS,
    ERR_NOT_FOUND,
    ERR_PERMISSION_DENIED,
    ERR_SERVER_ERROR,
    MSG_DATA_INVALID,
    MSG_NOT_FOUND,
    MSG_PERMISSION_DENIED,
)


class BaseAPIException(APIException):
    """An APIException carrying a namespaced error code (`err_cd`).

    `fields` lists request fields to flag as required:
    `raise NotFoundError()` / `raise MissingParametersError(fields=["email"])`.
    """

    err_cd: str = ERR_SERVER_ERROR

    def __init__(
        self,
        detail: Any = None,
        code: str | None = None,
        *,
        fields: Iterable[str] | None = None,
    ) -> None:
        super().__init__(detail=detail, code=code)
        self.error_fields = list(fields or [])


class MissingParametersError(BaseAPIException):
    status_code = 400
    default_detail = "Some required fields are missing, please check."
    err_cd = ERR_MISSING_PARAMETERS


class DataInvalidError(BaseAPIException):
    status_code = 400
    default_detail = MSG_DATA_INVALID
    err_cd = ERR_DATA_INVALID


class PermissionDeniedError(BaseAPIException):
    status_code = 403
    default_detail = MSG_PERMISSION_DENIED
    err_cd = ERR_PERMISSION_DENIED


class NotFoundError(BaseAPIException):
    status_code = 404
    default_detail = MSG_NOT_FOUND
    err_cd = ERR_NOT_FOUND


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Turn BaseAPIException into {err_cd, err_msg, error}; defer the rest to DRF.

    The renderer (LetstreamAPIRenderer) folds this payload into the envelope.
    """
    if isinstance(exc, BaseAPIException):
        payload: dict[str, Any] = {"err_cd": exc.err_cd, "err_msg": str(exc.detail)}
        if exc.error_fields:
            payload["error"] = {
                field: ["This field is required."] for field in exc.error_fields
            }
        set_rollback()
        return Response(payload, status=exc.status_code)
    return exception_handler(exc, context)
```

### `app/apps/core/api_renderers.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""The single response envelope. Views return plain Response(payload); this wraps it.

success: {"status": true,  "data": <payload>, "version": "<VERSION>"}
error:   {"status": false, "err_cd": "...", "err_msg": "...", "error": {...}, "version": "..."}
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework.renderers import JSONRenderer

from .api_errors import default_error_for


class LetstreamAPIRenderer(JSONRenderer):
    """Wrap every DRF response in the standard envelope."""

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: dict[str, Any] | None = None,
    ) -> bytes:
        response = (renderer_context or {}).get("response")
        status_code = response.status_code if response is not None else 200
        if status_code == 204:
            return b""
        ok = 200 <= status_code < 300
        envelope: dict[str, Any] = {"status": ok}
        if ok:
            envelope["data"] = data
        else:
            envelope.update(self._error_parts(data, status_code))
        envelope["version"] = settings.APPLICATION_VERSION
        return super().render(envelope, accepted_media_type, renderer_context)

    @staticmethod
    def _error_parts(data: Any, status_code: int) -> dict[str, Any]:
        """Split an error payload into err_cd / err_msg / error."""
        payload: dict[str, Any] = dict(data) if isinstance(data, dict) else {}
        if data is not None and not isinstance(data, dict):
            payload["detail"] = data  # e.g. a bare list from ValidationError
        default_cd, default_msg = default_error_for(status_code)
        err_cd = payload.pop("err_cd", None) or default_cd
        err_msg = payload.pop("err_msg", None) or default_msg
        error = payload.pop("error", None)
        if error is None:
            detail = payload.pop("detail", None)
            if isinstance(detail, dict):
                error = {**detail, **payload}
            elif detail is not None:
                error = {"detail": detail, **payload}
            else:
                error = payload
        return {"err_cd": err_cd, "err_msg": err_msg, "error": error}
```

### `app/apps/core/parsers.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Form/multipart parsers that coerce "null"/"undefined"/"" to real None at the boundary."""

from __future__ import annotations

from typing import Any

from django.http import QueryDict
from rest_framework.parsers import FormParser, MultiPartParser

EMPTY_MARKERS = frozenset({"null", "undefined", ""})


def coerce_empties(data: QueryDict) -> QueryDict:
    """Replace empty-marker strings with None in a (possibly immutable) QueryDict."""
    was_mutable = data._mutable
    data._mutable = True
    for key in list(data.keys()):
        values = data.getlist(key)
        data.setlist(
            key,
            [None if isinstance(v, str) and v in EMPTY_MARKERS else v for v in values],
        )
    data._mutable = was_mutable
    return data


class APIFormParser(FormParser):
    """application/x-www-form-urlencoded with empty-marker coercion."""

    def parse(
        self, stream: Any, media_type: str | None = None, parser_context: Any = None
    ) -> QueryDict:
        return coerce_empties(super().parse(stream, media_type, parser_context))


class APIMultiPartParser(MultiPartParser):
    """multipart/form-data with empty-marker coercion (files untouched)."""

    def parse(
        self, stream: Any, media_type: str | None = None, parser_context: Any = None
    ) -> Any:
        result = super().parse(stream, media_type, parser_context)
        coerce_empties(result.data)
        return result
```

### `app/apps/core/pagination.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Default pagination: ?limit=&offset= → {count, next, previous, results} under `data`."""

from rest_framework.pagination import LimitOffsetPagination


class StandardPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100
```

### `app/apps/core/permissions.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Reusable permission classes. Tenancy-mode aware, no imports of tenancy models."""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Platform superuser only."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class HasOrgPermission(BasePermission):
    """Multi-tenant RBAC: checks the view's `org_permissions` codes in `request.organization`.

    - View without `org_permissions` → no tenant check (any authenticated user).
    - Bypass order: platform superuser → org owner (inside org.has_permission) → role codes.
    - `request.organization` is resolved + membership-validated by TenantMiddleware from
      the X-Organization-Id header; an absent org denies.
    """

    message = "You do not have permission to perform this action in this organization."

    def has_permission(self, request: Any, view: Any) -> bool:
        codes = getattr(view, "org_permissions", None)
        if codes is None:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        if not codes or "*" in codes:
            return True
        organization = getattr(request, "organization", None)
        if not organization:  # truthiness, not `is None` — it is a lazy object
            return False
        return all(organization.has_permission(user, code) for code in codes)


class HasRole(BasePermission):
    """Single-tenant RBAC on `User.role` (owner > admin > member > guest).

    Usable as `HasRole` (reads the view's `min_role`; no `min_role` → any authenticated
    user) or as `HasRole("admin")` directly in `permission_classes`.
    """

    message = "Your role does not allow this action."

    def __init__(self, min_role: str | None = None) -> None:
        self.min_role = min_role

    def __call__(self) -> HasRole:
        """DRF instantiates permission classes; an instance returns itself."""
        return self

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        required = self.min_role or getattr(view, "min_role", None)
        if required is None or user.is_superuser:
            return True
        return user.has_role(required)
```

### `app/apps/core/views.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Base API views (auth tier by class), Django error handlers, and the health check."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.renderers import BaseRenderer, BrowsableAPIRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import api_exceptions
from .api_errors import default_error_for
from .api_renderers import LetstreamAPIRenderer
from .parsers import APIFormParser, APIMultiPartParser
from .permissions import HasOrgPermission, HasRole, IsAdmin


def prepare_response(
    *, status: bool, data: Any = None, error: Any = None, status_code: int = 200
) -> dict[str, Any]:
    """Build the envelope for non-DRF responses (Django error handlers)."""
    body: dict[str, Any] = {"status": status}
    if status:
        body["data"] = data
    else:
        err_cd, err_msg = default_error_for(status_code)
        body.update(err_cd=err_cd, err_msg=err_msg, error=error or {})
    body["version"] = settings.APPLICATION_VERSION
    return body


def _error(status_code: int) -> JsonResponse:
    return JsonResponse(
        prepare_response(status=False, status_code=status_code), status=status_code
    )


def bad_request(request: HttpRequest, exception: Exception) -> JsonResponse:
    return _error(400)


def permission_denied(request: HttpRequest, exception: Exception) -> JsonResponse:
    return _error(403)


def page_not_found(request: HttpRequest, exception: Exception) -> JsonResponse:
    return _error(404)


def server_error(request: HttpRequest) -> JsonResponse:
    return _error(500)


def _tenant_permission() -> type[BasePermission]:
    """HasOrgPermission for multi-tenant projects, HasRole for single-tenant ones."""
    return HasOrgPermission if settings.MULTI_TENANT else HasRole


class AnonymousView(APIView):
    """Public endpoints. Parsers, envelope renderer and ergonomic nested exceptions."""

    permission_classes = [AllowAny]
    parser_classes = [JSONParser, APIFormParser, APIMultiPartParser]
    renderer_classes = [LetstreamAPIRenderer, BrowsableAPIRenderer]

    # raise self.NotFoundError() / self.MissingParametersError(fields=["x"]) — no imports
    MissingParametersError = api_exceptions.MissingParametersError
    DataInvalidError = api_exceptions.DataInvalidError
    PermissionDeniedError = api_exceptions.PermissionDeniedError
    NotFoundError = api_exceptions.NotFoundError

    def get_renderers(self) -> list[BaseRenderer]:
        """Browsable API in DEBUG only; production is JSON-envelope only."""
        if settings.DEBUG:
            return super().get_renderers()
        return [LetstreamAPIRenderer()]


class AuthenticatedView(AnonymousView):
    """The 90% case: authenticated + tenant/role permission check."""

    permission_classes = [IsAuthenticated, _tenant_permission()]


class AdminOnlyView(AuthenticatedView):
    """Platform-superuser tools."""

    permission_classes = [IsAuthenticated, IsAdmin]


class HealthView(AnonymousView):
    """GET /api/health/ — liveness + dependency check for load balancers and compose."""

    authentication_classes: list[type] = []
    throttle_classes: list[type] = []

    @extend_schema(responses={200: dict, 503: dict})
    def get(self, request: Request) -> Response:
        checks = {"database": self._check_database(), "cache": self._check_cache()}
        healthy = all(value == "ok" for value in checks.values())
        return Response({"checks": checks}, status=200 if healthy else 503)

    @staticmethod
    def _check_database() -> str:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:  # report only; never leak details to the client
            return "error"
        return "ok"

    @staticmethod
    def _check_cache() -> str:
        try:
            cache.set("health:ping", "pong", 5)
            return "ok" if cache.get("health:ping") == "pong" else "error"
        except Exception:
            return "error"
```

### `app/apps/core/middleware.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Project-wide middlewares: base-lineage header and DRF-aware audit actor capture."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from auditlog.cid import set_cid
from auditlog.context import set_actor
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.functional import SimpleLazyObject

from .utils import RequestUtils


class InstadashVersionMiddleware:
    """Stamp every response with the Instadash AI Base version this project derives from.

    Managed by bootstrap/upgrade via settings.INSTADASH_BASE_VERSION — do not remove.
    """

    HEADER = "X-Letstream-Instadash-Version"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response[self.HEADER] = settings.INSTADASH_BASE_VERSION
        return response


class AuditActorMiddleware:
    """Replacement for `auditlog.middleware.AuditlogMiddleware` under token auth.

    auditlog's middleware reads `request.user` eagerly — before DRF has authenticated the
    `Authorization: Token …` header — so API writes would be logged without an actor.
    Here the actor is a lazy object resolved when the first LogEntry is written, by which
    time DRF has set `request.user`.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        set_cid(request)  # correlation id (X-Correlation-ID header) on every LogEntry
        actor = SimpleLazyObject(lambda: self._resolve_actor(request))
        with set_actor(actor=actor, remote_addr=RequestUtils.get_client_ip(request)):
            return self.get_response(request)

    @staticmethod
    def _resolve_actor(request: HttpRequest) -> Any:
        user = getattr(request, "user", None)
        return user if user is not None and user.is_authenticated else None
```

### `app/apps/core/utils.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Namespaced helpers shared across apps."""

from __future__ import annotations

import ipaddress
from typing import Any

import nh3
from django.conf import settings
from django.core.exceptions import PermissionDenied


class RequestUtils:
    """Request introspection that never raises."""

    @staticmethod
    def get_client_ip(request: Any) -> str | None:
        """Client IP; honours X-Forwarded-For only when TRUST_X_FORWARDED_FOR is set."""
        meta = getattr(request, "META", {}) or {}
        candidate = meta.get("REMOTE_ADDR", "")
        forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
        if settings.TRUST_X_FORWARDED_FOR and forwarded:
            candidate = forwarded.split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            return None

    @staticmethod
    def get_user_agent(request: Any) -> str:
        """User-Agent header, truncated to fit the audit columns."""
        meta = getattr(request, "META", {}) or {}
        return str(meta.get("HTTP_USER_AGENT", ""))[:512]

    @staticmethod
    def get_organization(request: Any) -> Any:
        """The resolved tenant, or None (never raises on an invalid tenant header)."""
        organization = getattr(request, "organization", None)
        try:
            return organization if organization else None
        except PermissionDenied:
            return None


class HtmlSanitizer:
    """Server-side allowlist sanitiser (nh3) for any stored rich-text/HTML field."""

    TAGS = frozenset(
        "a b blockquote br code em h1 h2 h3 h4 hr i img li ol p pre s span strong "
        "sub sup table tbody td th thead tr u ul".split()
    )
    ATTRIBUTES = {
        "a": {"href", "title"},
        "img": {"src", "alt", "title", "width", "height"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
    }
    URL_SCHEMES = frozenset({"http", "https", "mailto"})

    @classmethod
    def clean(cls, html: str | None) -> str:
        """Return sanitised HTML ("" for empty input)."""
        if not html:
            return ""
        return nh3.clean(
            html,
            tags=set(cls.TAGS),
            attributes={tag: set(attrs) for tag, attrs in cls.ATTRIBUTES.items()},
            url_schemes=set(cls.URL_SCHEMES),
            link_rel="noopener noreferrer nofollow",
        )


def sanitize_html(html: str | None) -> str:
    """Shortcut for HtmlSanitizer.clean — call before persisting any *_html field."""
    return HtmlSanitizer.clean(html)
```

### `app/apps/core/custom_serializer_fields.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Reusable serializer fields: write-by-id/read-nested relations and base64 uploads."""

from __future__ import annotations

import base64
import binascii
import uuid
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from rest_framework import serializers


class ForeignSerializerField(serializers.RelatedField):
    """Write by id (or {"id": …}); read as a nested object via `serializer_class`.

    Always pass a *scoped* queryset for tenant data:
    `ForeignSerializerField(queryset=Customer.objects.all(), serializer_class=…)` and narrow
    it in the parent serializer's __init__ (e.g. `.for_org(org)`).
    """

    def __init__(self, serializer_class: type[serializers.Serializer], **kwargs: Any):
        self.serializer_class = serializer_class
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> Any:
        pk = data.get("id") if isinstance(data, dict) else data
        if pk in (None, ""):
            raise serializers.ValidationError("A valid id is required.")
        try:
            return self.get_queryset().get(pk=pk)
        except (
            ObjectDoesNotExist,
            DjangoValidationError,
            ValueError,
            TypeError,
        ) as exc:
            raise serializers.ValidationError("Invalid id.") from exc

    def to_representation(self, value: Any) -> Any:
        return self.serializer_class(value, context=self.context).data


class M2MSerializerField(ForeignSerializerField):
    """Many-valued variant: accepts a list of ids/objects, renders a nested list."""

    def to_internal_value(self, data: Any) -> list[Any]:
        if not isinstance(data, list):
            raise serializers.ValidationError("Expected a list.")
        parent = super().to_internal_value
        return [parent(item) for item in data]

    def to_representation(self, value: Any) -> Any:
        return self.serializer_class(value.all(), many=True, context=self.context).data


class Base64FileField(serializers.FileField):
    """Accept a data URI ("data:<mime>;base64,…") with a mime allowlist and size cap."""

    ALLOWED_TYPES: frozenset[str] = frozenset({"application/pdf"})
    MAX_FILE_SIZE_MB = 10

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str) and data.startswith("data:") and ";base64," in data:
            header, encoded = data.split(";base64,", 1)
            mime = header.removeprefix("data:")
            if mime not in self.ALLOWED_TYPES:
                raise serializers.ValidationError("Unsupported file type.")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise serializers.ValidationError("Invalid base64 payload.") from exc
            if len(raw) > self.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise serializers.ValidationError(
                    f"File size must not exceed {self.MAX_FILE_SIZE_MB} MB."
                )
            extension = mime.split("/")[-1].split("+")[0]
            data = ContentFile(raw, name=f"{uuid.uuid4()}.{extension}")
        return super().to_internal_value(data)


class Base64ImageField(Base64FileField):
    """Images only (SVG deliberately excluded — it can carry script)."""

    ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
    MAX_FILE_SIZE_MB = 5
```

### `app/apps/core/tasks.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Cross-cutting Celery tasks: outbound email and audit retention."""

from __future__ import annotations

from datetime import timedelta
from smtplib import SMTPException

from auditlog.models import LogEntry
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import SecurityEvent


@shared_task(bind=True, max_retries=5, default_retry_delay=60, acks_late=True)
def send_email(
    self, to: str | list[str], subject: str, text: str, html: str | None = None
) -> None:
    """Send one email (routed to the `emails` queue). Domain code enqueues, never sends."""
    recipients = [to] if isinstance(to, str) else list(to)
    message = EmailMultiAlternatives(subject=subject, body=text, to=recipients)
    if html:
        message.attach_alternative(html, "text/html")
    try:
        message.send()
    except (SMTPException, OSError) as exc:
        raise self.retry(exc=exc, countdown=60 * 2**self.request.retries) from exc


@shared_task
def purge_audit_logs() -> dict[str, int]:
    """Retention: drop audit rows older than AUDIT_RETENTION_DAYS (runs daily via beat)."""
    cutoff = timezone.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
    security_events = SecurityEvent.objects.purge_older_than(cutoff)
    log_entries, _ = LogEntry.objects.filter(timestamp__lt=cutoff).delete()
    return {"security_events": security_events, "log_entries": log_entries}
```

### `app/apps/core/admin.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Core admin: Options (editable), audit tables (strictly read-only)."""

from __future__ import annotations

from typing import Any

from auditlog.admin import LogEntryAdmin
from auditlog.models import LogEntry
from django.contrib import admin

from .models import Options, SecurityEvent


class ReadOnlyAdminMixin:
    """No add / change / delete from the admin — audit evidence is immutable."""

    def has_add_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False


@admin.register(Options)
class OptionsAdmin(admin.ModelAdmin):
    list_display = ["key", "label", "modified_on"]
    search_fields = ["key", "label"]


@admin.register(SecurityEvent)
class SecurityEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "created_on",
        "event_type",
        "actor_email",
        "organization_id",
        "ip_address",
    ]
    list_filter = ["event_type"]
    search_fields = ["actor_email", "actor_id", "organization_id"]
    date_hierarchy = "created_on"


if admin.site.is_registered(LogEntry):
    admin.site.unregister(LogEntry)


@admin.register(LogEntry)
class ImmutableLogEntryAdmin(ReadOnlyAdminMixin, LogEntryAdmin):
    """auditlog's admin, with delete disabled as well."""
```

### `app/apps/core/tests/__init__.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.
```

### `app/apps/core/tests/test_envelope.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""The response envelope is a contract — test its shape on success and error paths."""

import pytest
from django.conf import settings

from apps.core.api_errors import ERR_NOT_FOUND, ERR_UNAUTHORIZED


@pytest.mark.django_db
def test_health_success_envelope(api_client):
    response = api_client.get("/api/health/")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] is True
    assert body["data"]["checks"] == {"database": "ok", "cache": "ok"}
    assert body["version"] == settings.APPLICATION_VERSION
    assert "error" not in body


@pytest.mark.django_db
def test_responses_carry_base_version_header(api_client):
    response = api_client.get("/api/health/")
    assert response["X-Letstream-Instadash-Version"] == settings.INSTADASH_BASE_VERSION


@pytest.mark.django_db
def test_unauthenticated_error_envelope(api_client):
    body = api_client.get("/api/accounts/me/").json()
    assert body["status"] is False
    assert body["err_cd"] == ERR_UNAUTHORIZED
    assert body["err_msg"]
    assert "data" not in body


@pytest.mark.django_db
def test_django_404_uses_envelope(api_client):
    response = api_client.get("/definitely-not-a-route/")
    body = response.json()
    assert response.status_code == 404
    assert body["status"] is False
    assert body["err_cd"] == ERR_NOT_FOUND
```

### `app/apps/core/tests/test_building_blocks.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Parsers, reusable serializer fields and audit retention."""

import base64
import io
from datetime import timedelta

import pytest
from django.db import models
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.core.custom_serializer_fields import Base64ImageField, ForeignSerializerField
from apps.core.models import SecurityEvent
from apps.core.parsers import APIFormParser
from apps.core.tasks import purge_audit_logs

PNG_1PX = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
).decode()


def test_form_parser_coerces_empty_markers():
    data = APIFormParser().parse(
        io.BytesIO(b"a=null&b=&c=undefined&d=keep"), None, {"encoding": "utf-8"}
    )
    assert (data["a"], data["b"], data["c"], data["d"]) == (None, None, None, "keep")


@pytest.mark.django_db
def test_foreign_serializer_field_writes_by_id_reads_nested(user):
    class Holder(serializers.Serializer):
        owner = ForeignSerializerField(
            queryset=User.objects.all(), serializer_class=UserSerializer
        )

    holder = Holder(data={"owner": {"id": user.pk}})
    assert holder.is_valid(), holder.errors
    assert holder.validated_data["owner"] == user
    assert Holder({"owner": user}).data["owner"]["email"] == user.email
    assert not Holder(data={"owner": 999999}).is_valid()


def test_base64_image_field_enforces_mime_allowlist():
    class Upload(serializers.Serializer):
        image = Base64ImageField()

    ok = Upload(data={"image": f"data:image/png;base64,{PNG_1PX}"})
    assert ok.is_valid(), ok.errors
    svg = Upload(data={"image": "data:image/svg+xml;base64,PHN2Zy8+"})
    assert not svg.is_valid()


@pytest.mark.django_db
def test_purge_audit_logs_respects_retention(settings):
    settings.AUDIT_RETENTION_DAYS = 30
    old = SecurityEvent.record(SecurityEvent.Type.LOGOUT)
    fresh = SecurityEvent.record(SecurityEvent.Type.LOGOUT)
    # bypass the append-only guard exactly like a data fixture would
    models.QuerySet.update(
        SecurityEvent.objects.filter(pk=old.pk),
        created_on=timezone.now() - timedelta(days=31),
    )
    assert purge_audit_logs()["security_events"] == 1
    assert list(SecurityEvent.objects.values_list("pk", flat=True)) == [fresh.pk]
```

### `app/apps/core/tests/test_core.py`

```python
# <Project Name>
# Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
# Author: <Legal Entity Name>
#
# Built on Instadash AI Base by Letstream
# (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
# Template portions (c) Letstream Ventures Pvt Ltd.
#
# The Instadash AI Base template is provided "AS IS", without warranty of any
# kind, express or implied, including merchantability, fitness for a particular
# purpose and non-infringement, unless covered by an explicit written agreement
# with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
# redistribution of the template, in whole or in part, is prohibited and may
# result in legal action and remedies available under applicable law.

"""Unit tests for core building blocks."""

import pytest
from rest_framework.test import APIRequestFactory

from apps.core.models import ImmutableRecordError, SecurityEvent
from apps.core.options import Option
from apps.core.permissions import HasRole
from apps.core.utils import sanitize_html


def test_sanitize_html_strips_script_and_handlers():
    dirty = (
        '<p onclick="x()">Hi<script>alert(1)</script><a href="javascript:x">l</a></p>'
    )
    clean = sanitize_html(dirty)
    assert "<script" not in clean
    assert "onclick" not in clean
    assert "javascript:" not in clean
    assert clean.startswith("<p>Hi")


@pytest.mark.django_db
def test_security_event_is_append_only(user):
    event = SecurityEvent.record(SecurityEvent.Type.LOGIN_SUCCEEDED, actor=user)
    assert event.actor_email == user.email
    event.metadata = {"tampered": True}
    with pytest.raises(ImmutableRecordError):
        event.save()
    with pytest.raises(ImmutableRecordError):
        event.delete()
    with pytest.raises(ImmutableRecordError):
        SecurityEvent.objects.all().update(actor_email="x@example.com")
    with pytest.raises(ImmutableRecordError):
        SecurityEvent.objects.all().delete()


@pytest.mark.django_db
def test_option_defaults_and_overrides():
    assert Option.get_bool(Option.Keys.SIGNUP_ENABLED) is True
    Option.set(Option.Keys.SIGNUP_ENABLED, "false")
    assert Option.get_bool(Option.Keys.SIGNUP_ENABLED) is False


@pytest.mark.django_db
def test_has_role_hierarchy(user_factory):
    guest = user_factory(role="guest")
    admin_user = user_factory(role="admin")
    request = APIRequestFactory().get("/")

    class View:
        min_role = "member"

    request.user = guest
    assert HasRole().has_permission(request, View()) is False
    request.user = admin_user
    assert HasRole().has_permission(request, View()) is True
    assert HasRole("owner").has_permission(request, View()) is False
```
