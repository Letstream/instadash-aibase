<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Realtime (Django Channels)

> **Opt-in per project — not part of Bootstrap.** Add websockets only when a feature genuinely
> needs server push (live boards, presence, notifications badges, long-running job progress).
> Polling or refetch-on-focus is often enough. When you do need it, this is the one way we do it:
> Django **Channels** on the existing ASGI app, **channels-redis** as the channel layer, token auth
> via the WebSocket **subprotocol**, tenant-scoped groups, and a single `broadcast_change()` helper
> that sends **ids, not data**. See [multi-tenancy](multi-tenancy.md), [accounts-and-auth](accounts-and-auth.md),
> [containerization-and-deployment](containerization-and-deployment.md), [testing](testing.md).

---

## 1. Enabling it

```bash
cd app
poetry add channels channels-redis
poetry add --group dev pytest-asyncio daphne   # channels.testing imports daphne
mkdir -p apps/realtime && poetry run python manage.py startapp realtime apps/realtime
```

```python
# settings/base.py
INSTALLED_APPS += ["channels", "apps.realtime"]      # "channels" in the third-party group

# after the CACHES block (reuses _REDIS_AUTH):
REDIS_CHANNELS_URL = "redis://{auth}{host}:{port}/{db}".format(
    auth=_REDIS_AUTH, host=env("REDIS_HOST", default="localhost"),
    port=env.int("REDIS_PORT", default=6379), db=env.int("REDIS_CHANNELS_DB", default=1),
)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_CHANNELS_URL], "capacity": 1500, "expiry": 10},
    }
}

# settings/testing.py
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
```

Redis is already the cache; the channel layer uses its own DB index. Record the decision (and the
`/ws/` endpoints) in the project's `DOCS.md`.

---

## 2. ASGI routing

The web process is already ASGI (`gunicorn app.asgi:application -k uvicorn.workers.UvicornWorker`),
so no new service is needed — the same web containers serve HTTP and websockets. (Daphne works too;
we standardise on uvicorn.) Websocket routes live under **`/ws/`**, the second prefix the frontend
proxies and the infra compose forward (with `Upgrade`/`Connection` headers).

```python
# app/app/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django_asgi_app = get_asgi_application()  # initialise Django BEFORE importing consumers/models

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from apps.realtime.auth import TokenAuthMiddleware  # noqa: E402
from apps.realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            TokenAuthMiddleware(URLRouter(websocket_urlpatterns)),
            settings.CORS_ALLOWED_ORIGINS,          # same allowlist as CORS (explicit origins)
        ),
    }
)
```

```python
# apps/realtime/routing.py
from django.urls import path

from .consumers import EventsConsumer

websocket_urlpatterns = [
    path("ws/events/", EventsConsumer.as_asgi()),                    # user (+ site) groups
    path("ws/org/<uuid:org_id>/", EventsConsumer.as_asgi()),         # + org group (multi-tenant)
]
```

---

## 3. Authentication — token in the subprotocol

Browsers can't set an `Authorization` header on `new WebSocket(...)`. The two usual options are a
query parameter or the `Sec-WebSocket-Protocol` header. **We send the token as a subprotocol**:

```js
new WebSocket(`${wsBase}/ws/org/${orgId}/`, ["token", apiToken])
```

**Why:** query strings end up in proxy/access logs, browser history and monitoring breadcrumbs —
a long-lived API token must never be in a URL. The subprotocol header is not logged by default,
needs no extra endpoint, and reuses the exact same opaque token and validation as the REST API. The
server accepts with the subprotocol **`"token"`** (never echoing the token back). If an
infrastructure component in front of you logs request headers, switch to a short-lived single-use
*ticket* (`POST /api/realtime/ticket/` → 30-second Redis key → `?ticket=`) — same consumer, different
middleware.

```python
# apps/realtime/auth.py
"""Resolve `scope["user"]` from the ["token", "<token>"] subprotocol pair."""

from typing import Any

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import Token

SUBPROTOCOL = "token"


@database_sync_to_async
def _user_for_token(raw: str) -> Any:
    token = Token.find_active(raw)
    if token is None or not token.user.is_active:
        return AnonymousUser()
    return token.user


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope: dict, receive: Any, send: Any) -> Any:
        scope["user"] = AnonymousUser()
        protocols = scope.get("subprotocols") or []
        if len(protocols) >= 2 and protocols[0] == SUBPROTOCOL:
            scope["user"] = await _user_for_token(protocols[1])
        return await super().__call__(scope, receive, send)
```

---

## 4. Tenant-scoped groups & the consumer

Group names are the isolation boundary — a socket only ever joins groups the server derived from
the **authenticated user** and a **membership check**, never from anything the client claims:

| Group | Joined when | Receives |
|-------|-------------|----------|
| `user.<user_id>` | every authenticated connection | personal events (notifications, `auth.revoked`) |
| `org.<org_id>` | multi-tenant, URL `ws/org/<org_id>/`, caller is owner/active member | changes to that tenant's data |
| `site` | single-tenant projects | changes visible to all users |

```python
# apps/realtime/groups.py
def group_for_user(user_id) -> str:
    return f"user.{user_id}"


def group_for_org(org_id) -> str:
    return f"org.{org_id}"


SITE_GROUP = "site"
```

```python
# apps/realtime/consumers.py
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from .auth import SUBPROTOCOL
from .groups import SITE_GROUP, group_for_org, group_for_user

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


@database_sync_to_async
def _is_member(user: Any, org_id: Any) -> bool:
    from apps.organization.models import Organization

    org = Organization.objects.filter(pk=org_id).first()
    return bool(org and org.has_member(user))


class EventsConsumer(AsyncJsonWebsocketConsumer):
    """Push-only channel: the server sends change notices; clients refetch over REST."""

    async def connect(self) -> None:
        self.joined: list[str] = []
        user = self.scope["user"]
        if not user.is_authenticated:
            return await self._reject(CLOSE_UNAUTHENTICATED)
        groups = [group_for_user(user.pk)]
        org_id = self.scope["url_route"]["kwargs"].get("org_id")
        if settings.MULTI_TENANT and org_id:
            if not await _is_member(user, org_id):
                return await self._reject(CLOSE_FORBIDDEN)
            groups.append(group_for_org(org_id))
        elif not settings.MULTI_TENANT:
            groups.append(SITE_GROUP)
        for group in groups:                          # join BEFORE accepting: no lost events
            await self.channel_layer.group_add(group, self.channel_name)
        self.joined = groups
        await self.accept(subprotocol=SUBPROTOCOL)

    async def _reject(self, code: int) -> None:
        """Accept then close, so the browser sees our close code (a refused handshake is 1006)."""
        await self.accept(subprotocol=SUBPROTOCOL)
        await self.close(code=code)

    async def disconnect(self, code: int) -> None:
        for group in self.joined:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def entity_change(self, event: dict) -> None:   # handles {"type": "entity.change"}
        await self.send_json({k: v for k, v in event.items()})

    async def auth_revoked(self, event: dict) -> None:    # handles {"type": "auth.revoked"}
        await self.close(code=CLOSE_UNAUTHENTICATED)
```

The socket is **push-only**: client → server messages are limited to `ping`. Mutations always go
through the REST API, where permissions, validation and audit already live.

---

## 5. `broadcast_change()` — call it after every mutation others should see

```python
# apps/realtime/broadcast.py
"""Fan out change notices to websocket groups — after the DB transaction commits."""

from collections.abc import Iterable
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from .groups import SITE_GROUP, group_for_org, group_for_user


def broadcast_change(
    *,
    resource: str,
    action: str,
    object_id: Any,
    organization_id: Any = None,
    user_ids: Iterable[Any] = (),
) -> None:
    """Notify subscribers that `resource` `object_id` was created/updated/deleted.

    Sends identifiers only — clients refetch through the API, so per-role permissions and
    field visibility are enforced exactly once, in the REST layer.
    """
    message = {
        "type": "entity.change",
        "resource": resource,
        "action": action,
        "id": str(object_id),
    }
    groups = [group_for_user(user_id) for user_id in user_ids]
    if settings.MULTI_TENANT and organization_id:
        groups.append(group_for_org(organization_id))
    elif not settings.MULTI_TENANT:
        groups.append(SITE_GROUP)

    def _send() -> None:
        layer = get_channel_layer()
        if layer is None:
            return
        for group in groups:
            async_to_sync(layer.group_send)(group, {**message})

    transaction.on_commit(_send)   # never announce a change that might roll back
```

Call it from the view/service **after** the write, never from `save()` signals (bulk operations and
imports would flood the layer):

```python
def perform_update(self, serializer):
    order = serializer.save()
    broadcast_change(resource="order", action="updated", object_id=order.pk,
                     organization_id=order.organization_id)
```

On logout / membership removal, push `{"type": "auth.revoked"}` to `user.<id>` so open sockets
close; a revoked token can't reconnect because the handshake re-validates it.

---

## 6. Frontend expectations

- **One socket per tab**, opened after login with `["token", token]`; for multi-tenant, the URL
  carries the active org — **reconnect** on org switch.
- **Reconnect with exponential backoff + jitter** (1 s → 30 s cap), reset after a stable connection.
- **Close codes:** `4401` → stop reconnecting, refresh auth / go to login; `4403` → stop for that
  org (membership gone); anything else → back off and retry.
- **Heartbeat:** send `{"type": "ping"}` every ~25 s; treat a missing `pong` as a dead socket.
- **No replay:** events missed while disconnected are gone — after every (re)connect, **refetch**
  the visible queries. On `entity.change`, invalidate/refetch the matching resource by id instead of
  trusting a payload.

---

## 7. Testing (`channels.testing.WebsocketCommunicator`)

```python
import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from app.asgi import application
from apps.accounts.models import Token

ORIGIN = [(b"origin", b"http://localhost:5173")]   # must be in CORS_ALLOWED_ORIGINS for tests


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_member_receives_org_events(user, organization):
    raw, _ = await database_sync_to_async(Token.issue)(user)
    ws = WebsocketCommunicator(
        application, f"/ws/org/{organization.pk}/", headers=ORIGIN, subprotocols=["token", raw]
    )
    connected, subprotocol = await ws.connect()
    assert connected and subprotocol == "token"

    await get_channel_layer().group_send(
        f"org.{organization.pk}",
        {"type": "entity.change", "resource": "order", "action": "created", "id": "1"},
    )
    assert (await ws.receive_json_from())["resource"] == "order"
    await ws.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_foreign_org_is_rejected(user, other_organization):
    raw, _ = await database_sync_to_async(Token.issue)(user)
    ws = WebsocketCommunicator(
        application, f"/ws/org/{other_organization.pk}/", headers=ORIGIN, subprotocols=["token", raw]
    )
    await ws.connect()
    assert (await ws.receive_output())["code"] == 4403   # accepted, then closed with 4403
```

Also unit-test `broadcast_change()` with `django_capture_on_commit_callbacks(execute=True)` and the
in-memory layer, and add a cross-tenant test per broadcast call site (org B's socket never receives
org A's events).

---

## 8. Checklist

- [ ] Realtime is recorded as enabled in `DOCS.md`; `channels`/`channels-redis` added deliberately.
- [ ] ASGI router: `OriginValidator` → `TokenAuthMiddleware` → `URLRouter` under `/ws/`.
- [ ] Token only via the `["token", <token>]` subprotocol; accepted subprotocol is `"token"`.
- [ ] Groups derived server-side (`user.<id>`, `org.<id>` after a membership check, `site`).
- [ ] `broadcast_change()` sends ids only, on commit, from views/services — not model signals.
- [ ] Sockets close on `auth.revoked`; clients reconnect with backoff and refetch after reconnect.
- [ ] Tests: connect/receive, unauthenticated (4401), foreign org (4403), cross-tenant broadcast.
