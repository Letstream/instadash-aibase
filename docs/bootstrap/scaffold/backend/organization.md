# Scaffold — `apps/organization` (multi-tenant only)

> Tenancy: `Organization` (owner is a **ForeignKey** — a user may own many), `OrganizationRole`
> (permission codes), `OrganizationUser` (membership join), `OrganizationInvite`, the abstract
> `OrgScopedModel` + scoped queryset, `TenantMiddleware` (`X-Organization-Id`), my-orgs / roles /
> members / invites endpoints, and the cross-tenant isolation tests.
> Rationale: [multi-tenancy](../../../architecture-guidelines/backend/multi-tenancy.md). Index: [README](README.md).

**Skip this whole file for single-tenant projects** (`TENANCY_MODE=single`): don't create the app;
`base.py` and `urls.py` already leave it out, and `AuthenticatedView` switches to `HasRole`.

Created with `django-admin startapp organization apps/organization`; overwrite the generated files
and delete `apps/organization/tests.py`.

---

### `app/apps/organization/apps.py`

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
from django.db.models.signals import post_migrate


def _seed_default_roles(sender: AppConfig, **kwargs: object) -> None:
    from .models import OrganizationRole

    OrganizationRole.ensure_defaults()


class OrganizationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organization"
    label = "organization"
    verbose_name = "Organizations"

    def ready(self) -> None:
        """Wire signals, seed global roles after migrate, register audited models."""
        from auditlog.registry import auditlog

        from . import signals  # noqa: F401
        from .models import (
            Organization,
            OrganizationInvite,
            OrganizationRole,
            OrganizationUser,
        )

        post_migrate.connect(_seed_default_roles, sender=self)
        for model in (
            Organization,
            OrganizationRole,
            OrganizationUser,
            OrganizationInvite,
        ):
            auditlog.register(model, exclude_fields=["modified_on"])
```

### `app/apps/organization/permission_constants.py`

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

"""Permission codes ("resource:action"). Feature apps add their own codes in their
own permission_constants.py and grant them through OrganizationRole.permissions."""

ALL = "*"

ORG_READ = "organization:read"
ORG_EDIT = "organization:edit"

USER_READ = "user:read"
USER_MANAGE = "user:manage"  # invite, change role, remove members
```

### `app/apps/organization/models.py`

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

"""Tenancy models and the OrgScopedModel base every tenant-owned model extends."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, ClassVar, Self

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDTimeStampedModel

from . import permission_constants as perms

NO_ACCESS = "You do not have access to this organization."


class InviteError(Exception):
    """An invitation cannot be accepted (expired, wrong recipient)."""


# --------------------------------------------------------------------------
# Organization
# --------------------------------------------------------------------------
class OrganizationQuerySet(models.QuerySet):
    def accessible_to(self, user: Any) -> Self:
        """Orgs the user owns or is an active member of."""
        if not (user and user.is_authenticated):
            return self.none()
        return self.filter(
            Q(owner=user) | Q(members__user=user, members__is_active=True)
        ).distinct()

    def with_membership_of(self, user: Any) -> Self:
        """Prefetch the user's own membership (avoids N+1 in listings)."""
        return self.prefetch_related(
            Prefetch(
                "members",
                queryset=OrganizationUser.objects.filter(
                    user=user, is_active=True
                ).select_related("role"),
                to_attr="prefetched_memberships",
            )
        )

    def get_for_member(self, user: Any, org_id: Any) -> Organization:
        """The org iff `user` may access it; otherwise PermissionDenied (never 404)."""
        try:
            return self.accessible_to(user).get(pk=org_id)
        except (self.model.DoesNotExist, ValidationError, ValueError) as exc:
            raise PermissionDenied(NO_ACCESS) from exc


class Organization(UUIDTimeStampedModel):
    """A tenant. The owner has implicit full access ("*")."""

    name = models.CharField(max_length=150)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # transfer ownership before deleting a user
        related_name="owned_organizations",
    )

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def is_owner(self, user: Any) -> bool:
        return bool(user and user.is_authenticated and self.owner_id == user.pk)

    def get_membership(self, user: Any) -> OrganizationUser | None:
        """The user's active membership (cached per instance, prefetch-aware)."""
        if not (user and user.is_authenticated):
            return None
        cache: dict[Any, OrganizationUser | None] = self.__dict__.setdefault(
            "_membership_cache", {}
        )
        if user.pk not in cache:
            prefetched = getattr(self, "prefetched_memberships", None)
            if prefetched is not None:
                cache[user.pk] = next(
                    (m for m in prefetched if m.user_id == user.pk), None
                )
            else:
                cache[user.pk] = (
                    self.members.select_related("role")
                    .filter(user_id=user.pk, is_active=True)
                    .first()
                )
        return cache[user.pk]

    def has_member(self, user: Any) -> bool:
        """Owner or active member."""
        return self.is_owner(user) or self.get_membership(user) is not None

    def get_permissions(self, user: Any) -> list[str]:
        """Effective permission codes for `user` in this org."""
        if self.is_owner(user):
            return [perms.ALL]
        membership = self.get_membership(user)
        if membership is None or not membership.role.is_active:
            return []
        return list(membership.role.permissions or [])

    def has_permission(self, user: Any, code: str) -> bool:
        """Owner → "*" → explicit code."""
        granted = self.get_permissions(user)
        return perms.ALL in granted or code in granted

    def describe_for(self, user: Any) -> dict[str, Any]:
        """Payload for my-orgs: who am I in this org and what may I do."""
        membership = self.get_membership(user)
        return {
            "id": self.pk,
            "name": self.name,
            "is_owner": self.is_owner(user),
            "role": membership.role.name if membership else None,
            "permissions": self.get_permissions(user),
        }


# --------------------------------------------------------------------------
# The tenant base model
# --------------------------------------------------------------------------
class OrgScopedQuerySet(models.QuerySet):
    """Tenant filters. Use these in EVERY read path of tenant data."""

    def for_org(self, organization: Any) -> Self:
        """Rows of one org (the org must already be validated, e.g. request.organization)."""
        if not organization:  # truthiness: request.organization is a lazy object
            return self.none()
        return self.filter(organization=organization)

    def visible_to(self, user: Any, organization: Any) -> Self:
        """Rows of `organization` iff `user` belongs to it (superusers included)."""
        if not organization or not (user and user.is_authenticated):
            return self.none()
        if not (user.is_superuser or organization.has_member(user)):
            return self.none()
        return self.for_org(organization)


class OrgScopedModel(TimeStampedModel):
    """Abstract base for every tenant-owned model: org FK + scoped manager."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = OrgScopedQuerySet.as_manager()

    class Meta:
        abstract = True

    def is_accessible_by(self, user: Any) -> bool:
        """Object-level check for writes and cross-links."""
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or self.organization.has_member(user)


# --------------------------------------------------------------------------
# Roles, memberships, invites
# --------------------------------------------------------------------------
class OrganizationRoleQuerySet(models.QuerySet):
    def available_to(self, organization: Any) -> Self:
        """Global roles plus the org's own custom roles."""
        return self.filter(
            Q(organization__isnull=True) | Q(organization=organization), is_active=True
        )


class OrganizationRole(UUIDTimeStampedModel):
    """A named bundle of permission codes. organization=NULL → global default role."""

    class RoleType(models.TextChoices):
        ADMIN = "admin", "Admin"
        USER = "user", "User"

    DEFAULTS: ClassVar[tuple[tuple[str, str, list[str]], ...]] = (
        ("Admin", "admin", [perms.ALL]),
        ("Member", "user", [perms.ORG_READ, perms.USER_READ]),
    )

    name = models.CharField(max_length=64)
    role_type = models.CharField(
        max_length=16, choices=RoleType.choices, default=RoleType.USER
    )
    permissions = models.JSONField(default=list, blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
    )
    is_active = models.BooleanField(default=True)

    objects = OrganizationRoleQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_org_role_name"
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(organization__isnull=True),
                name="uniq_global_role_name",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def ensure_defaults(cls) -> None:
        """Idempotently create the global default roles (runs after every migrate)."""
        for name, role_type, codes in cls.DEFAULTS:
            cls.objects.get_or_create(
                name=name,
                organization=None,
                defaults={"role_type": role_type, "permissions": codes},
            )


class OrganizationUser(OrgScopedModel):
    """Membership join: user ↔ organization with a role. Roles never live on User."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.ForeignKey(
        OrganizationRole, on_delete=models.PROTECT, related_name="memberships"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uniq_org_user"
            )
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.organization_id}"


class OrganizationInvite(OrgScopedModel):
    """A pending invitation, accepted by the user whose email matches."""

    TTL = timedelta(days=7)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invites"
    )
    email = models.EmailField()
    role = models.ForeignKey(
        OrganizationRole, on_delete=models.PROTECT, related_name="invites"
    )
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invites",
    )
    expires_on = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="uniq_org_invite_email"
            )
        ]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = self.email.lower()
        if self.expires_on is None:
            self.expires_on = timezone.now() + self.TTL
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return self.expires_on <= timezone.now()

    def accept(self, user: Any) -> OrganizationUser:
        """Turn the invite into an active membership, then delete it."""
        if self.is_expired:
            raise InviteError("This invitation has expired.")
        if user.email.lower() != self.email:
            raise InviteError("This invitation was sent to a different email address.")
        with transaction.atomic():
            membership, _ = OrganizationUser.objects.update_or_create(
                organization=self.organization,
                user=user,
                defaults={"role": self.role, "is_active": True},
            )
            self.delete()
        return membership
```

### `app/apps/organization/middleware.py`

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

"""Resolve the active tenant from X-Organization-Id → request.organization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.utils.functional import SimpleLazyObject

from .models import Organization


class TenantMiddleware:
    """Attach a *lazy* `request.organization`.

    DRF authenticates `Authorization: Token …` inside the view, after middleware has run,
    so the org is resolved on first access (by then `request.user` is the token user).
    Resolution validates membership: a header naming an org the caller can't access raises
    PermissionDenied → 403 envelope. No header → None. Never trust the header alone.
    """

    HEADER = "X-Organization-Id"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        org_id = request.headers.get(self.HEADER)
        request.organization = SimpleLazyObject(lambda: self._resolve(request, org_id))
        return self.get_response(request)

    @staticmethod
    def _resolve(request: HttpRequest, org_id: str | None) -> Any:
        if not org_id:
            return None
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return Organization.objects.get_for_member(user, org_id)
```

### `app/apps/organization/signals.py`

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

"""React to identity events without the accounts app importing tenancy."""

from typing import Any

from django.dispatch import receiver

from apps.accounts.signals import user_registered

from .models import Organization


@receiver(user_registered)
def create_first_organization(sender: Any, user: Any, **kwargs: Any) -> None:
    """Self-serve sign-up gets its own organization (the user is its owner)."""
    Organization.objects.create(name=f"{user.get_short_name()}'s workspace", owner=user)
```

### `app/apps/organization/serializers.py`

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

"""Organization serializers."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import Organization, OrganizationInvite, OrganizationRole, OrganizationUser


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "created_on"]
        read_only_fields = ["id", "created_on"]


class MyOrgSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    is_owner = serializers.BooleanField()
    role = serializers.CharField(allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField())


class RoleSerializer(serializers.ModelSerializer):
    is_global = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationRole
        fields = ["id", "name", "role_type", "permissions", "is_global"]

    def get_is_global(self, obj: OrganizationRole) -> bool:
        return obj.organization_id is None


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    role = RoleSerializer(read_only=True)

    class Meta:
        model = OrganizationUser
        fields = ["id", "email", "name", "role", "is_active", "created_on"]


class _RoleIdMixin:
    """Validates `role_id` against the roles available to the request's org."""

    def validate_role_id(self, value: Any) -> OrganizationRole:
        organization = self.context["organization"]
        role = (
            OrganizationRole.objects.available_to(organization).filter(pk=value).first()
        )
        if role is None:
            raise serializers.ValidationError("Role not found.")
        return role


class MemberRoleSerializer(_RoleIdMixin, serializers.Serializer):
    role_id = serializers.UUIDField()


class InviteSerializer(_RoleIdMixin, serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = OrganizationInvite
        fields = ["id", "email", "role", "role_id", "expires_on", "created_on"]
        read_only_fields = ["id", "expires_on", "created_on"]

    def validate_email(self, value: str) -> str:
        value = value.lower()
        organization = self.context["organization"]
        if organization.owner.email.lower() == value:
            raise serializers.ValidationError("This user owns the organization.")
        if organization.members.filter(
            user__email__iexact=value, is_active=True
        ).exists():
            raise serializers.ValidationError("This user is already a member.")
        if organization.invites.filter(email=value).exists():
            raise serializers.ValidationError("An invitation is already pending.")
        return value

    def create(self, validated_data: dict[str, Any]) -> OrganizationInvite:
        validated_data["role"] = validated_data.pop("role_id")
        return super().create(validated_data)


class InvitePublicSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name")
    inviter_name = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvite
        fields = ["id", "email", "organization_name", "inviter_name", "expires_on"]

    def get_inviter_name(self, obj: OrganizationInvite) -> str | None:
        return obj.inviter.get_full_name() if obj.inviter else None
```

### `app/apps/organization/views.py`

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

"""Tenancy endpoints: my-orgs, create org, roles, members, invites."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.models import SecurityEvent
from apps.core.tasks import send_email
from apps.core.views import AnonymousView, AuthenticatedView

from . import permission_constants as perms
from .models import (
    InviteError,
    Organization,
    OrganizationInvite,
    OrganizationRole,
    OrganizationUser,
)
from .serializers import (
    InvitePublicSerializer,
    InviteSerializer,
    MemberRoleSerializer,
    MemberSerializer,
    MyOrgSerializer,
    OrganizationSerializer,
    RoleSerializer,
)


class OrgContextMixin:
    """Puts the validated request.organization into serializer context."""

    def get_serializer_context(self) -> dict[str, Any]:
        context = super().get_serializer_context()  # type: ignore[misc]
        context["organization"] = self.request.organization  # type: ignore[attr-defined]
        return context


class MyOrgsView(AuthenticatedView):
    """GET /api/organization/my-orgs/ — switchable tenants with role + permissions."""

    serializer_class = MyOrgSerializer

    def get(self, request: Request) -> Response:
        organizations = (
            Organization.objects.accessible_to(request.user)
            .with_membership_of(request.user)
            .select_related("owner")
        )
        payload = [org.describe_for(request.user) for org in organizations]
        return Response(self.serializer_class(payload, many=True).data)


class OrganizationCreateView(AuthenticatedView):
    """POST /api/organization/ — create another org owned by the caller."""

    serializer_class = OrganizationSerializer

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RoleListView(AuthenticatedView, generics.ListAPIView):
    """GET /api/organization/roles/ — global + org roles."""

    org_permissions = [perms.USER_READ]
    serializer_class = RoleSerializer
    queryset = OrganizationRole.objects.none()  # schema only; get_queryset scopes
    pagination_class = None

    def get_queryset(self) -> Any:
        return OrganizationRole.objects.available_to(self.request.organization)


class MemberListView(AuthenticatedView, generics.ListAPIView):
    """GET /api/organization/members/ — memberships of the request org only."""

    org_permissions = [perms.USER_READ]
    serializer_class = MemberSerializer
    queryset = OrganizationUser.objects.none()  # schema only; get_queryset scopes
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    ordering = ["created_on"]

    def get_queryset(self) -> Any:
        return OrganizationUser.objects.visible_to(
            self.request.user, self.request.organization
        ).select_related("user", "role")


class MemberDetailView(AuthenticatedView):
    """PATCH (change role) / DELETE (remove) /api/organization/members/<id>/."""

    org_permissions = [perms.USER_MANAGE]
    serializer_class = MemberRoleSerializer

    def _get_member(self, pk: Any) -> OrganizationUser:
        member = (
            OrganizationUser.objects.for_org(self.request.organization)
            .select_related("user", "role")
            .filter(pk=pk)
            .first()
        )
        if member is None:
            raise self.NotFoundError()
        if member.user_id == self.request.user.pk:
            raise self.PermissionDeniedError(
                detail="You cannot change your own membership."
            )
        return member

    def patch(self, request: Request, pk: Any) -> Response:
        member = self._get_member(pk)
        serializer = self.serializer_class(
            data=request.data, context={"organization": request.organization}
        )
        serializer.is_valid(raise_exception=True)
        previous = member.role.name
        member.role = serializer.validated_data["role_id"]
        member.save(update_fields=["role"])
        SecurityEvent.record(
            SecurityEvent.Type.ROLE_CHANGED,
            request=request,
            member_id=str(member.pk),
            from_role=previous,
            to_role=member.role.name,
        )
        return Response(MemberSerializer(member).data)

    def delete(self, request: Request, pk: Any) -> Response:
        member = self._get_member(pk)
        SecurityEvent.record(
            SecurityEvent.Type.MEMBER_REMOVED,
            request=request,
            member_id=str(member.pk),
            member_email=member.user.email,
        )
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InviteListCreateView(
    OrgContextMixin, AuthenticatedView, generics.ListCreateAPIView
):
    """GET/POST /api/organization/invites/ — pending invites of the request org."""

    org_permissions = [perms.USER_MANAGE]
    serializer_class = InviteSerializer
    queryset = OrganizationInvite.objects.none()  # schema only; get_queryset scopes

    def get_queryset(self) -> Any:
        return OrganizationInvite.objects.visible_to(
            self.request.user, self.request.organization
        ).select_related("role")

    def perform_create(self, serializer: InviteSerializer) -> None:
        invite = serializer.save(
            organization=self.request.organization, inviter=self.request.user
        )
        self._send_invite_email(invite)
        SecurityEvent.record(
            SecurityEvent.Type.MEMBER_INVITED,
            request=self.request,
            invite_email=invite.email,
            role=invite.role.name,
        )

    @staticmethod
    def _send_invite_email(invite: OrganizationInvite) -> None:
        context = {
            "invite": invite,
            "accept_url": f"{settings.FRONTEND_URL}/invite/{invite.pk}",
            "project_name": settings.PROJECT_NAME,
            "legal_entity_name": settings.LEGAL_ENTITY_NAME,
        }
        send_email.delay(
            invite.email,
            f"You're invited to {invite.organization.name} on {settings.PROJECT_NAME}",
            render_to_string("organization/email/invite.txt", context),
        )


class InvitePublicView(AnonymousView):
    """GET /api/organization/invites/<id>/public/ — preview before sign-up (no auth)."""

    serializer_class = InvitePublicSerializer

    authentication_classes: list[type] = []

    def get(self, request: Request, pk: Any) -> Response:
        invite = (
            OrganizationInvite.objects.select_related("organization", "inviter")
            .filter(pk=pk, expires_on__gt=timezone.now())
            .first()
        )
        if invite is None:
            raise self.NotFoundError()
        return Response(self.serializer_class(invite).data)


class InviteAcceptView(AuthenticatedView):
    """POST /api/organization/invites/<id>/accept/ — by the invited (authenticated) user."""

    serializer_class = MyOrgSerializer

    def post(self, request: Request, pk: Any) -> Response:
        invite = (
            OrganizationInvite.objects.select_related("organization", "role")
            .filter(pk=pk)
            .first()
        )
        if invite is None:
            raise self.NotFoundError()
        organization = invite.organization
        try:
            invite.accept(request.user)
        except InviteError as exc:
            raise serializers.ValidationError({"invite": [str(exc)]}) from exc
        SecurityEvent.record(
            SecurityEvent.Type.INVITE_ACCEPTED,
            request=request,
            organization=organization,
        )
        return Response(
            self.serializer_class(organization.describe_for(request.user)).data
        )
```

### `app/apps/organization/urls.py`

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

app_name = "organization"

urlpatterns = [
    path("", views.OrganizationCreateView.as_view(), name="organization-create"),
    path("my-orgs/", views.MyOrgsView.as_view(), name="my-orgs"),
    path("roles/", views.RoleListView.as_view(), name="role-list"),
    path("members/", views.MemberListView.as_view(), name="member-list"),
    path("members/<uuid:pk>/", views.MemberDetailView.as_view(), name="member-detail"),
    path("invites/", views.InviteListCreateView.as_view(), name="invite-list"),
    path(
        "invites/<uuid:pk>/public/",
        views.InvitePublicView.as_view(),
        name="invite-public",
    ),
    path(
        "invites/<uuid:pk>/accept/",
        views.InviteAcceptView.as_view(),
        name="invite-accept",
    ),
]
```

### `app/apps/organization/admin.py`

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

from django.contrib import admin

from .models import Organization, OrganizationInvite, OrganizationRole, OrganizationUser


class MembershipInline(admin.TabularInline):
    model = OrganizationUser
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_on"]
    search_fields = ["name", "owner__email"]
    autocomplete_fields = ["owner"]
    inlines = [MembershipInline]


@admin.register(OrganizationRole)
class OrganizationRoleAdmin(admin.ModelAdmin):
    list_display = ["name", "role_type", "organization", "is_active"]
    list_filter = ["role_type", "is_active"]


@admin.register(OrganizationInvite)
class OrganizationInviteAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "expires_on"]
    search_fields = ["email", "organization__name"]
```

### `app/apps/organization/templates/organization/email/invite.txt`

```django
{% autoescape off %}Hi,

{% if invite.inviter %}{{ invite.inviter.get_full_name }}{% else %}Someone{% endif %} invited you to join "{{ invite.organization.name }}" on {{ project_name }}.

Accept the invitation (valid until {{ invite.expires_on|date:"Y-m-d" }}):
{{ accept_url }}

— {{ project_name }}{% if legal_entity_name %} · {{ legal_entity_name }}{% endif %}
{% endautoescape %}
```

### `app/apps/organization/tests/__init__.py`

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

### `app/apps/organization/tests/test_tenancy.py`

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

"""Tenant isolation is the #1 leak vector — these tests are mandatory, not optional."""

import pytest
from ddf import G

from apps.core.api_errors import ERR_PERMISSION_DENIED
from apps.core.models import SecurityEvent
from apps.organization.models import (
    Organization,
    OrganizationInvite,
    OrganizationRole,
    OrganizationUser,
)

pytestmark = pytest.mark.django_db


# ---- cross-tenant isolation (model + API) ---------------------------------
def test_scoped_queryset_hides_other_tenants(
    user, organization, other_organization, member_role
):
    G(
        OrganizationInvite,
        organization=organization,
        role=member_role,
        email="a@example.com",
    )
    G(
        OrganizationInvite,
        organization=other_organization,
        role=member_role,
        email="b@example.com",
    )
    assert OrganizationInvite.objects.visible_to(user, organization).count() == 1
    assert OrganizationInvite.objects.visible_to(user, other_organization).count() == 0


def test_header_for_foreign_org_is_forbidden(
    auth_client_factory, user, other_organization
):
    client = auth_client_factory(user, other_organization)
    response = client.get("/api/organization/members/")
    assert response.status_code == 403
    assert response.json()["err_cd"] == ERR_PERMISSION_DENIED


def test_members_list_contains_only_own_org(
    org_client, member, other_organization, member_role
):
    stranger = G(OrganizationUser, organization=other_organization, role=member_role)
    emails = {
        row["email"]
        for row in org_client.get("/api/organization/members/").json()["data"][
            "results"
        ]
    }
    assert member.email in emails
    assert stranger.user.email not in emails


def test_my_orgs_lists_owned_and_member_orgs_only(
    auth_client_factory, member, organization, other_organization
):
    body = auth_client_factory(member).get("/api/organization/my-orgs/").json()
    assert [row["id"] for row in body["data"]] == [str(organization.pk)]
    assert body["data"][0]["role"] == "Member"
    assert body["data"][0]["is_owner"] is False


def test_missing_header_denies_org_scoped_endpoint(auth_client):
    assert auth_client.get("/api/organization/members/").status_code == 403


# ---- RBAC --------------------------------------------------------------------
def test_member_without_user_manage_cannot_invite(
    auth_client_factory, member, organization, member_role
):
    client = auth_client_factory(member, organization)
    response = client.post(
        "/api/organization/invites/",
        {"email": "new@example.com", "role_id": str(member_role.pk)},
    )
    assert response.status_code == 403


def test_owner_changes_member_role_and_it_is_audited(org_client, member, organization):
    admin_role = OrganizationRole.objects.get(name="Admin", organization__isnull=True)
    membership = OrganizationUser.objects.get(organization=organization, user=member)
    response = org_client.patch(
        f"/api/organization/members/{membership.pk}/", {"role_id": str(admin_role.pk)}
    )
    assert response.status_code == 200
    assert organization.has_permission(member, "anything:at-all") is True
    assert SecurityEvent.objects.filter(event_type="role_changed").exists()


# ---- invites -------------------------------------------------------------------
def test_invite_accept_flow(
    org_client, auth_client_factory, user_factory, organization, member_role, mailoutbox
):
    response = org_client.post(
        "/api/organization/invites/",
        {"email": "Dave@Example.com", "role_id": str(member_role.pk)},
    )
    assert response.status_code == 201
    invite_id = response.json()["data"]["id"]
    assert len(mailoutbox) == 1 and invite_id in mailoutbox[0].body

    wrong = auth_client_factory(user_factory(email="eve@example.com"))
    assert (
        wrong.post(f"/api/organization/invites/{invite_id}/accept/").status_code == 400
    )

    dave = user_factory(email="dave@example.com")
    response = auth_client_factory(dave).post(
        f"/api/organization/invites/{invite_id}/accept/"
    )
    assert response.status_code == 200
    assert organization.has_member(dave)
    assert not OrganizationInvite.objects.filter(pk=invite_id).exists()


def test_public_invite_preview_needs_no_auth(
    api_client, organization, member_role, user
):
    invite = OrganizationInvite.objects.create(
        organization=organization, role=member_role, email="f@example.com", inviter=user
    )
    body = api_client.get(f"/api/organization/invites/{invite.pk}/public/").json()
    assert body["data"]["organization_name"] == organization.name


def test_registration_creates_first_organization(api_client, password):
    api_client.post(
        "/api/accounts/register/", {"email": "gina@example.com", "password": password}
    )
    assert Organization.objects.filter(owner__email="gina@example.com").count() == 1
```
