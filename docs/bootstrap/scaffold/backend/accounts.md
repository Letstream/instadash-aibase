# Scaffold — `apps/accounts`

> Identity: custom `User` (email login; `role` used only in single-tenant mode), hashed opaque
> `Token` (`Authorization: Token <token>`), `TokenAuthentication`, register / login / logout /
> me / password reset, throttles, admin, audit registration, tests.
> Rationale: [accounts-and-auth](../../../architecture-guidelines/backend/accounts-and-auth.md),
> [audit-logging](../../../architecture-guidelines/backend/audit-logging.md). Index: [README](README.md).

Created with `django-admin startapp accounts apps/accounts`; overwrite the generated files and
delete `apps/accounts/tests.py`. `AUTH_USER_MODEL = "accounts.User"` is already set in `base.py` —
the first `migrate` must happen **after** this app's initial migration exists.

---

### `app/apps/accounts/apps.py`

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


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        """Register audited models (sensitive fields excluded)."""
        from auditlog.registry import auditlog

        from . import schema  # noqa: F401  (registers the OpenAPI auth scheme)
        from .models import Token, User

        auditlog.register(
            User, exclude_fields=["password", "last_login", "modified_on"]
        )
        auditlog.register(
            Token,
            exclude_fields=[
                "key_hash",
                "last_used_on",
                "last_ip",
                "user_agent",
                "expires_on",
                "modified_on",
            ],
        )
```

### `app/apps/accounts/models.py`

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

"""Custom user (email is the login) and hashed, opaque, DB-backed API tokens."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.utils import RequestUtils

# Single-tenant role hierarchy (owner > admin > member > guest).
ROLE_RANK: dict[str, int] = {"guest": 0, "member": 1, "admin": 2, "owner": 3}

# Single-tenant: permission codes each role expands to in the user payload (UI gating).
# Extend with the project's own "resource:action" codes; keep it consistent with the
# `min_role` each view enforces. Multi-tenant permissions come from my-orgs instead.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": ["*"],
    "admin": ["user:read", "user:manage", "settings:read", "settings:edit"],
    "member": ["user:read", "settings:read"],
    "guest": [],
}


class UserManager(BaseUserManager):
    """Email-based manager; emails are stored lower-cased (case-insensitive login)."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)  # None → unusable password
        user.save(using=self._db)
        return user

    def create_user(
        self, email: str, password: str | None = None, **extra: Any
    ) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(
        self, email: str, password: str | None = None, **extra: Any
    ) -> User:
        extra.update(is_staff=True, is_superuser=True)
        extra.setdefault("role", "owner")
        extra.setdefault("email_confirmed", True)
        return self._create_user(email, password, **extra)

    def get_by_natural_key(self, username: str) -> User:
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})


class User(TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    """The account. Tenancy (multi-tenant) lives in the organization app's membership rows."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
        GUEST = "guest", "Guest"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
        help_text="Used only when TENANCY_MODE=single.",
    )
    email_confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self) -> str:
        return self.first_name or self.email

    def is_admin(self) -> bool:
        """Platform superuser."""
        return self.is_superuser

    def has_role(self, min_role: str) -> bool:
        """Single-tenant check: is this user's role at least `min_role`?"""
        if self.is_superuser:
            return True
        return ROLE_RANK.get(str(self.role), -1) >= ROLE_RANK[str(min_role)]

    def get_permissions(self) -> list[str]:
        """Codes for the user payload: superuser → ["*"]; single-tenant → role expansion.

        Multi-tenant projects return [] here — per-org permissions come from
        GET /api/organization/my-orgs/.
        """
        if self.is_superuser:
            return ["*"]
        if settings.MULTI_TENANT:
            return []
        return list(ROLE_PERMISSIONS.get(str(self.role), []))

    def issue_token(self, request: Any = None) -> tuple[str, Token]:
        """Create a new API token; returns (plaintext — shown once, Token row)."""
        return Token.issue(self, request=request)

    def revoke_all_tokens(self) -> int:
        """Revoke every active token (password change, suspension)."""
        return self.auth_tokens.active().update(revoked_on=timezone.now())

    def get_login_payload(self, request: Any = None) -> dict[str, Any]:
        """Issue a token and return {token, expires_on, user} for login/register."""
        from .serializers import UserSerializer

        raw, token = self.issue_token(request)
        return {
            "token": raw,
            "expires_on": token.expires_on,
            "user": UserSerializer(self).data,
        }


class TokenQuerySet(models.QuerySet):
    def active(self) -> TokenQuerySet:
        """Not revoked and not expired."""
        return self.filter(revoked_on__isnull=True, expires_on__gt=timezone.now())

    def stale(self, grace: timedelta) -> TokenQuerySet:
        """Expired or revoked for longer than `grace` — safe to purge."""
        cutoff = timezone.now() - grace
        return self.filter(Q(expires_on__lt=cutoff) | Q(revoked_on__lt=cutoff))


class Token(TimeStampedModel):
    """Opaque API token. Only the SHA-256 of the key is stored; plaintext is shown once."""

    TOUCH_INTERVAL = timedelta(minutes=1)

    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens"
    )
    expires_on = models.DateTimeField()
    last_used_on = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    revoked_on = models.DateTimeField(null=True, blank=True)

    objects = TokenQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["user", "revoked_on"])]

    def __str__(self) -> str:
        return f"Token {self.pk} (user {self.user_id})"  # never render the hash

    @staticmethod
    def hash_key(raw: str) -> str:
        """SHA-256 hex digest of a plaintext key."""
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(
        cls, user: User, *, request: Any = None, ttl: timedelta | None = None
    ) -> tuple[str, Token]:
        """Create a token; return (plaintext, row). The plaintext is never stored."""
        raw = secrets.token_urlsafe(32)
        token = cls.objects.create(
            user=user,
            key_hash=cls.hash_key(raw),
            expires_on=timezone.now() + (ttl or settings.AUTH_TOKEN_TTL),
            last_ip=RequestUtils.get_client_ip(request) if request else None,
            user_agent=RequestUtils.get_user_agent(request) if request else "",
        )
        return raw, token

    @classmethod
    def find_active(cls, raw: str) -> Token | None:
        """Look up an active token by its plaintext key."""
        return (
            cls.objects.select_related("user")
            .active()
            .filter(key_hash=cls.hash_key(raw))
            .first()
        )

    @property
    def is_active(self) -> bool:
        return self.revoked_on is None and self.expires_on > timezone.now()

    def touch(self, request: Any = None) -> None:
        """Sliding expiry + last-use bookkeeping, written at most once per interval."""
        now = timezone.now()
        if self.last_used_on and now - self.last_used_on < self.TOUCH_INTERVAL:
            return
        self.last_used_on = now
        self.expires_on = max(self.expires_on, now + settings.AUTH_TOKEN_TTL)
        self.last_ip = RequestUtils.get_client_ip(request) if request else self.last_ip
        self.save(update_fields=["last_used_on", "expires_on", "last_ip"])

    def revoke(self) -> None:
        """Revoke (logout). Rows are purged later by a periodic task."""
        if self.revoked_on is None:
            self.revoked_on = timezone.now()
            self.save(update_fields=["revoked_on"])
```

### `app/apps/accounts/authentication.py`

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

"""DRF authentication: `Authorization: Token <plaintext>`."""

from __future__ import annotations

from typing import Any

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import Token


class TokenAuthentication(BaseAuthentication):
    """Hash the presented key, find an active token, reject suspended users."""

    keyword = "Token"

    def authenticate(self, request: Any) -> tuple[Any, Token] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword.lower().encode():
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid token header.")
        try:
            raw = parts[1].decode()
        except UnicodeError as exc:
            raise AuthenticationFailed("Invalid token header.") from exc
        return self.authenticate_credentials(raw, request)

    def authenticate_credentials(self, raw: str, request: Any) -> tuple[Any, Token]:
        token = Token.find_active(raw)
        if token is None:
            raise AuthenticationFailed("Invalid or expired token.")
        if not token.user.is_active:
            raise AuthenticationFailed("This account is suspended.")
        token.touch(request)
        return token.user, token

    def authenticate_header(self, request: Any) -> str:
        """Makes DRF answer 401 (not 403) for missing/invalid credentials."""
        return self.keyword
```

### `app/apps/accounts/schema.py`

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

"""OpenAPI (drf-spectacular) description of `Authorization: Token <token>`."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class TokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.TokenAuthentication"
    name = "TokenAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": 'Opaque API token, sent as "Token <token>".',
        }
```

### `app/apps/accounts/api_errors.py`

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

"""Accounts error codes (E-C-ACC-NNNN) and the exceptions that carry them."""

from apps.core.api_exceptions import BaseAPIException

APP_BASE = "E-C-ACC-"

ERR_INVALID_CREDENTIALS = APP_BASE + "0001"
ERR_SIGNUP_DISABLED = APP_BASE + "0002"
ERR_INVALID_RESET_LINK = APP_BASE + "0003"


class InvalidCredentialsError(BaseAPIException):
    status_code = 400
    default_detail = "Invalid email or password."
    err_cd = ERR_INVALID_CREDENTIALS


class SignupDisabledError(BaseAPIException):
    status_code = 403
    default_detail = "Sign-up is currently disabled."
    err_cd = ERR_SIGNUP_DISABLED


class InvalidResetLinkError(BaseAPIException):
    status_code = 400
    default_detail = "This password reset link is invalid or has expired."
    err_cd = ERR_INVALID_RESET_LINK
```

### `app/apps/accounts/signals.py`

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

"""Custom signals so other apps react to identity events without accounts importing them."""

from django.dispatch import Signal

# Sent after a successful self-serve registration. kwargs: user, request.
# The organization app listens to create the new user's first organization.
user_registered = Signal()
```

### `app/apps/accounts/serializers.py`

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

"""Accounts serializers — validation only; behaviour lives on the models."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .api_errors import InvalidResetLinkError
from .models import User


def _check_password(password: str, user: User | None = None) -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)}) from exc


class UserSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "permissions",
            "email_confirmed",
            "created_on",
        ]
        read_only_fields = ["id", "email", "role", "email_confirmed", "created_on"]

    def get_permissions(self, obj: User) -> list[str]:
        return obj.get_permissions()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_email(self, value: str) -> str:
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        candidate = User(
            email=attrs["email"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        _check_password(attrs["password"], candidate)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=pk, is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError) as exc:
            raise InvalidResetLinkError() from exc
        if not default_token_generator.check_token(user, attrs["token"]):
            raise InvalidResetLinkError()
        _check_password(attrs["new_password"], user)
        attrs["user"] = user
        return attrs
```

### `app/apps/accounts/throttles.py`

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

"""Brute-force protection for anonymous auth endpoints (rates in REST_FRAMEWORK)."""

from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"
```

### `app/apps/accounts/views.py`

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

"""Credential flows. Thin views: validation in serializers, behaviour on the models."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.models import SecurityEvent
from apps.core.options import Option
from apps.core.tasks import send_email
from apps.core.views import AnonymousView, AuthenticatedView

from .api_errors import InvalidCredentialsError, SignupDisabledError
from .models import Token, User
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .signals import user_registered
from .throttles import AuthRateThrottle, PasswordResetRateThrottle

RESET_SENT_MESSAGE = "If an account exists for this email, a reset link has been sent."


class RegisterView(AnonymousView):
    """POST /api/accounts/register/ → login payload (201)."""

    serializer_class = RegisterSerializer
    authentication_classes: list[type] = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        if not Option.get_bool(Option.Keys.SIGNUP_ENABLED):
            raise SignupDisabledError()
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_registered.send(sender=User, user=user, request=request)
        SecurityEvent.record(
            SecurityEvent.Type.USER_REGISTERED, request=request, actor=user
        )
        return Response(user.get_login_payload(request), status=status.HTTP_201_CREATED)


class LoginView(AnonymousView):
    """POST /api/accounts/login/ → {token, expires_on, user}."""

    serializer_class = LoginSerializer
    authentication_classes: list[type] = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        user = authenticate(
            request, email=email, password=serializer.validated_data["password"]
        )
        if user is None:
            SecurityEvent.record(
                SecurityEvent.Type.LOGIN_FAILED, request=request, email=email
            )
            raise InvalidCredentialsError()
        payload = user.get_login_payload(request)
        user_logged_in.send(sender=User, request=request, user=user)
        SecurityEvent.record(
            SecurityEvent.Type.LOGIN_SUCCEEDED, request=request, actor=user
        )
        return Response(payload)


class LogoutView(AuthenticatedView):
    """POST /api/accounts/logout/ → revokes the presented token (204)."""

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        if isinstance(request.auth, Token):
            request.auth.revoke()
        SecurityEvent.record(SecurityEvent.Type.LOGOUT, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(AuthenticatedView):
    """GET/PATCH /api/accounts/me/ — the current user's profile."""

    serializer_class = UserSerializer

    def get(self, request: Request) -> Response:
        return Response(self.serializer_class(request.user).data)

    def patch(self, request: Request) -> Response:
        serializer = self.serializer_class(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PasswordResetRequestView(AnonymousView):
    """POST /api/accounts/password-reset/ — always 200 (no account enumeration)."""

    serializer_class = PasswordResetRequestSerializer
    authentication_classes: list[type] = []
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            self._send_reset_email(user)
            SecurityEvent.record(
                SecurityEvent.Type.PASSWORD_RESET_REQUESTED, request=request, actor=user
            )
        return Response({"message": RESET_SENT_MESSAGE})

    @staticmethod
    def _send_reset_email(user: User) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        context = {
            "user": user,
            "reset_url": f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}",
            "project_name": settings.PROJECT_NAME,
            "legal_entity_name": settings.LEGAL_ENTITY_NAME,
            "valid_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
        }
        send_email.delay(
            user.email,
            f"Reset your {settings.PROJECT_NAME} password",
            render_to_string("accounts/email/password_reset.txt", context),
        )


class PasswordResetConfirmView(AnonymousView):
    """POST /api/accounts/password-reset/confirm/ {uid, token, new_password}."""

    serializer_class = PasswordResetConfirmSerializer
    authentication_classes: list[type] = []
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        user.revoke_all_tokens()
        SecurityEvent.record(
            SecurityEvent.Type.PASSWORD_CHANGED, request=request, actor=user
        )
        return Response({"message": "Your password has been reset. Please log in."})
```

### `app/apps/accounts/urls.py`

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

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path(
        "password-reset/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
```

### `app/apps/accounts/tasks.py`

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

"""Accounts maintenance tasks (routed to the `maintenance` queue)."""

from datetime import timedelta

from celery import shared_task

from .models import Token


@shared_task
def purge_stale_tokens(grace_days: int = 30) -> int:
    """Delete tokens expired/revoked more than `grace_days` ago."""
    deleted, _ = Token.objects.stale(timedelta(days=grace_days)).delete()
    return deleted
```

### `app/apps/accounts/admin.py`

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

"""Admin for users and (read-only) tokens."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.utils import timezone

from .models import Token, User


class UserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("email",)


class UserChangeForm(DjangoUserChangeForm):
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "role", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "is_superuser", "role"]
    search_fields = ["email", "first_name", "last_name"]
    readonly_fields = ["last_login", "created_on", "modified_on"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "role", "email_confirmed")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "created_on", "modified_on")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "created_on",
        "last_used_on",
        "expires_on",
        "revoked_on",
    ]
    list_select_related = ["user"]
    search_fields = ["user__email"]
    readonly_fields = [
        "user",
        "created_on",
        "last_used_on",
        "last_ip",
        "user_agent",
        "expires_on",
        "revoked_on",
    ]
    actions = ["revoke_selected"]

    def has_add_permission(self, request: Any) -> bool:
        return False  # tokens are issued by the API only

    @admin.action(description="Revoke selected tokens")
    def revoke_selected(self, request: Any, queryset: Any) -> None:
        queryset.filter(revoked_on__isnull=True).update(revoked_on=timezone.now())
```

### `app/apps/accounts/templates/accounts/email/password_reset.txt`

```django
{% autoescape off %}Hi {{ user.get_short_name }},

We received a request to reset your {{ project_name }} password.
Open the link below within {{ valid_minutes }} minutes to choose a new one:

{{ reset_url }}

If you did not request this, you can ignore this email — your password is unchanged.

— {{ project_name }}{% if legal_entity_name %} · {{ legal_entity_name }}{% endif %}
{% endautoescape %}
```

### `app/apps/accounts/tests/__init__.py`

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

### `app/apps/accounts/tests/test_auth.py`

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

"""Credential flows: happy paths, error paths, envelope shape and audit events."""

from datetime import timedelta

import pytest
from auditlog.models import LogEntry
from django.utils import timezone

from apps.accounts.api_errors import (
    ERR_INVALID_CREDENTIALS,
    ERR_INVALID_RESET_LINK,
    ERR_SIGNUP_DISABLED,
)
from apps.accounts.models import Token, User
from apps.core.api_errors import ERR_DATA_INVALID, ERR_UNAUTHORIZED
from apps.core.models import SecurityEvent
from apps.core.options import Option

pytestmark = pytest.mark.django_db


def _login(client, email, password):
    return client.post("/api/accounts/login/", {"email": email, "password": password})


def test_register_returns_token_and_user(api_client, password):
    response = api_client.post(
        "/api/accounts/register/", {"email": "New@Example.com", "password": password}
    )
    body = response.json()
    assert response.status_code == 201
    assert body["status"] is True
    assert body["data"]["user"]["email"] == "new@example.com"
    assert body["data"]["token"]
    assert SecurityEvent.objects.filter(event_type="user_registered").count() == 1


def test_register_rejects_duplicate_email_and_weak_password(api_client, user):
    response = api_client.post(
        "/api/accounts/register/", {"email": user.email.upper(), "password": "123"}
    )
    body = response.json()
    assert response.status_code == 400
    assert body["err_cd"] == ERR_DATA_INVALID
    assert "email" in body["error"]


def test_register_respects_signup_option(api_client, password):
    Option.set(Option.Keys.SIGNUP_ENABLED, "false")
    response = api_client.post(
        "/api/accounts/register/", {"email": "x@example.com", "password": password}
    )
    assert response.status_code == 403
    assert response.json()["err_cd"] == ERR_SIGNUP_DISABLED


def test_user_payload_permissions_follow_tenancy_mode(settings, user_factory):
    settings.MULTI_TENANT = False
    assert user_factory(role="owner").get_permissions() == ["*"]
    assert user_factory(role="guest").get_permissions() == []
    assert "user:manage" in user_factory(role="admin").get_permissions()
    settings.MULTI_TENANT = True
    assert user_factory(role="owner").get_permissions() == []
    assert user_factory(is_superuser=True).get_permissions() == ["*"]


def test_token_is_stored_hashed(user):
    raw, token = Token.issue(user)
    assert token.key_hash == Token.hash_key(raw)
    assert raw not in token.key_hash
    assert Token.find_active(raw) == token


def test_login_success_and_me(api_client, user, password):
    body = _login(api_client, "ALICE@example.com", password).json()
    assert body["status"] is True
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {body['data']['token']}")
    me = api_client.get("/api/accounts/me/").json()
    assert me["data"]["email"] == user.email
    assert me["data"]["permissions"] == user.get_permissions()
    assert SecurityEvent.objects.filter(
        event_type="login_succeeded", actor_email=user.email
    ).exists()


def test_login_failure_is_audited(api_client, user):
    response = _login(api_client, user.email, "wrong-password")
    assert response.status_code == 400
    assert response.json()["err_cd"] == ERR_INVALID_CREDENTIALS
    event = SecurityEvent.objects.get(event_type="login_failed")
    assert event.metadata == {"email": user.email}  # never the password


def test_inactive_user_cannot_login(api_client, user_factory, password):
    inactive = user_factory(is_active=False)
    assert _login(api_client, inactive.email, password).status_code == 400


def test_logout_revokes_token(auth_client):
    assert auth_client.post("/api/accounts/logout/").status_code == 204
    response = auth_client.get("/api/accounts/me/")
    assert response.status_code == 401
    assert response.json()["err_cd"] == ERR_UNAUTHORIZED


def test_audit_log_attributes_token_authenticated_writes(auth_client, user):
    auth_client.patch("/api/accounts/me/", {"first_name": "Zed"})
    entry = LogEntry.objects.get_for_object(user).order_by("-timestamp").first()
    assert entry.actor == user
    assert entry.changes_dict["first_name"] == ["Alice", "Zed"]
    assert "password" not in entry.changes_dict


def test_expired_token_is_rejected(api_client, user):
    raw, _ = Token.issue(user, ttl=timedelta(seconds=-1))
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw}")
    assert api_client.get("/api/accounts/me/").status_code == 401


def test_me_patch_cannot_change_role_or_email(auth_client, user):
    response = auth_client.patch(
        "/api/accounts/me/",
        {"first_name": "Al", "role": "owner", "email": "x@example.com"},
    )
    user.refresh_from_db()
    assert response.status_code == 200
    assert (user.first_name, user.role, user.email) == (
        "Al",
        "member",
        "alice@example.com",
    )


def test_password_reset_flow(api_client, user, mailoutbox):
    response = api_client.post("/api/accounts/password-reset/", {"email": user.email})
    assert response.status_code == 200
    assert len(mailoutbox) == 1
    link = next(
        line for line in mailoutbox[0].body.splitlines() if "/reset-password/" in line
    )
    uid, token = link.rstrip("/").split("/")[-2:]

    _, old_token = Token.issue(user)
    response = api_client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "An0ther-Str0ng-Pass"},
    )
    assert response.status_code == 200
    old_token.refresh_from_db()
    assert old_token.revoked_on is not None
    assert _login(api_client, user.email, "An0ther-Str0ng-Pass").status_code == 200


def test_password_reset_unknown_email_is_silent(api_client, mocker):
    delay = mocker.patch("apps.accounts.views.send_email.delay")
    response = api_client.post(
        "/api/accounts/password-reset/", {"email": "nobody@example.com"}
    )
    assert response.status_code == 200
    delay.assert_not_called()


def test_password_reset_rejects_bad_token(api_client, user):
    response = api_client.post(
        "/api/accounts/password-reset/confirm/",
        {"uid": "bad", "token": "bad", "new_password": "An0ther-Str0ng-Pass"},
    )
    assert response.status_code == 400
    assert response.json()["err_cd"] == ERR_INVALID_RESET_LINK


def test_stale_tokens_are_purged(user):
    from apps.accounts.tasks import purge_stale_tokens

    _, token = Token.issue(user)
    Token.objects.filter(pk=token.pk).update(
        expires_on=timezone.now() - timedelta(days=60)
    )
    assert purge_stale_tokens() == 1
    assert User.objects.filter(pk=user.pk).exists()
```
