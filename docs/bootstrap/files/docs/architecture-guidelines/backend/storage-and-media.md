<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Storage & Media Backends

> How static files and user-uploaded media are stored and served. The model is **three tiers of
> storage** (static / public media / private media) implemented as swappable backends, gated by a
> flag so the same code runs on object storage in production and the local filesystem in dev/CI.
> The rules that matter: **private by default**, **per-tenant keys**, **presigned URLs — never
> public ACLs for user data**. See [configuration-and-settings](configuration-and-settings.md),
> [multi-tenancy](multi-tenancy.md), [security](../../security.md).

---

## 1. The three storage tiers

| Tier | Backend | ACL | Overwrite | Used for |
|------|---------|-----|-----------|----------|
| **Static** | `StaticStorage` | public-read | yes | `collectstatic` output: JS/CSS/admin assets. Cache-busted, safe to overwrite. |
| **Public media** | `PublicMediaStorage` | public-read | no | Intentionally-public uploads served straight from a CDN/custom domain (brand logos, public thumbnails, generated public images). |
| **Private media** | `PrivateMediaStorage` | private | no | Everything user-owned: attachments, documents, exports. Served **only** via short-lived presigned URLs. |

**Default to private.** Anything a user uploads that belongs to their tenant goes to *private*.
Route to *public* only when the asset is deliberately world-readable. Never make user data
public just to avoid signing a URL.

---

## 2. The backend classes (`app/storage_backends.py`)

Subclass the `django-storages` S3 backend once per tier. Keep them in the **project package**, not
an app (they're configuration, not domain logic). Models reference storage through **callables**,
never through a concrete backend instance.

```python
from django.core.files.storage import Storage, storages
from storages.backends.s3 import S3Storage


class StaticStorage(S3Storage):
    location = "static"
    default_acl = "public-read"
    file_overwrite = True            # hashed asset names → safe to overwrite
    querystring_auth = False


class PublicMediaStorage(S3Storage):
    location = "public"
    default_acl = "public-read"
    file_overwrite = False           # never clobber a distinct upload
    querystring_auth = False


class PrivateMediaStorage(S3Storage):
    location = "private"
    default_acl = None               # objects are PRIVATE
    file_overwrite = False
    custom_domain = False            # force signed S3 URLs, never the CDN domain
    querystring_auth = True          # .url returns a presigned URL


def private_storage() -> Storage:
    return storages["default"]       # the private tier (or FileSystemStorage locally)


def public_storage() -> Storage:
    return storages["public"]
```

**Why callables matter:** a model field declared `FileField(storage=private_storage)` resolves the
backend from `STORAGES` at runtime, and migrations serialise the *function reference* — so flipping
`USE_AWS` swaps S3 ↔ local disk with **no model change and no new migration**.

If the bucket has ACLs disabled ("bucket owner enforced"), set `default_acl = None` on the public
tiers too and grant read on the `static/` and `public/` prefixes via bucket policy.

---

## 3. Wiring it in settings

Use Django's `STORAGES` dict. `base.py` defines local defaults and, behind `USE_AWS`, the S3 tiers —
all values from env:

```python
STORAGES = {
    "default":     {"BACKEND": "django.core.files.storage.FileSystemStorage"},   # private tier
    "public":      {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
FILE_UPLOAD_FOLDER_PATTERN = "%Y/%m/%d"          # date-sharded folder segment (see §4)

if USE_AWS:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="") or None       # None → IAM role
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="") or None
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="") or None
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="") or None   # MinIO locally
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="") or None # CDN, public tiers only
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_QUERYSTRING_EXPIRE = env.int("AWS_QUERYSTRING_EXPIRE", default=3600)
    AWS_DEFAULT_ACL = None
    STORAGES = {
        "default":     {"BACKEND": "app.storage_backends.PrivateMediaStorage"},  # private by default
        "public":      {"BACKEND": "app.storage_backends.PublicMediaStorage"},
        "staticfiles": {"BACKEND": "app.storage_backends.StaticStorage"},
    }
```

- `default` is the **private** backend, so a `FileField` with no explicit storage is private — a
  safe default. Choose the public tier only per field.
- `testing.py` forces the local filesystem `STORAGES` so CI never touches S3.
- Credentials come from env — never hardcoded. Prefer instance/workload IAM roles over static keys
  in production (leave the key variables empty).

---

## 4. Using storage on models

Reference the callables and generate **per-tenant, collision-proof** keys with an `upload_to`
callable:

```python
from app.storage_backends import private_storage, public_storage


def attachment_key(instance, filename: str) -> str:
    # org/<org_id>/attachments/<yyyy/mm/dd>/<uuid>-<filename> — tenant-partitioned, unguessable
    date = timezone.now().strftime(settings.FILE_UPLOAD_FOLDER_PATTERN)
    return f"org/{instance.organization_id}/attachments/{date}/{uuid.uuid4()}-{filename}"


class Attachment(OrgScopedModel):
    file = models.FileField(storage=private_storage, upload_to=attachment_key)


class OrgLogo(OrgScopedModel):
    image = models.ImageField(storage=public_storage, upload_to=logo_key)   # intentionally public
```

**Key rules**
- **Partition every object key by tenant** (`org/<org_id>/…`) in multi-tenant projects. This is
  defense-in-depth even for private storage — see [multi-tenancy](multi-tenancy.md). Single-tenant
  projects partition by owning resource instead (`users/<id>/…`).
- Include a **UUID** in the filename so uploads never collide or overwrite, and keys aren't guessable.
- Keep the tenant on the model (`OrgScopedModel`) so `upload_to` can read `organization_id`.

---

## 5. Serving files

**Private media — presigned URLs only.** Accessing `.url` on a `PrivateMediaStorage` file returns
a short-lived signed URL (governed by `AWS_QUERYSTRING_EXPIRE`). Expose it through a serializer
field, and re-check tenant access before handing it out:

```python
class AttachmentSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    def get_file(self, obj):
        # obj is already tenant-scoped by the queryset; return a fresh presigned GET URL
        return {"url": obj.file.url, "name": obj.file.name.rsplit("/", 1)[-1]}
```

**Direct browser uploads — presigned PUT/POST.** For large files, hand the client a presigned
upload URL (via an `S3Utils`-style helper) so bytes go straight to the bucket, bypassing the app
server. The client then submits only the returned object key back to the API.

**Public media** is served directly from the CDN/custom domain (`AWS_S3_CUSTOM_DOMAIN`); no signing.

Never build S3 URLs by hand or expose the bucket publicly for private data — always go through the
storage backend's `.url` (signed) or a presign helper.

---

## 6. Local development & CI

- With `USE_AWS=False`, both callables resolve to `FileSystemStorage`; files land under
  `MEDIA_ROOT` and are served locally in `DEBUG`. Zero cloud dependency to run the app.
- To exercise the **real S3 code path** locally, point boto3 at a local **MinIO** instance
  (`AWS_S3_ENDPOINT_URL=http://localhost:9000`, `USE_AWS=True`) — the infra compose stack can
  provide one ([infra](../../infra.md)). Same presigned-URL flow, no AWS account needed.
- CI (`testing.py`) always uses the local filesystem backend.

---

## 7. Base64 / data-URI uploads

For JSON APIs that accept inline files, use the reusable `Base64FileField` / `Base64ImageField`
serializer fields (see [core-app-reference](core-app-reference.md) §6) — they decode the data URI,
**enforce a mime allowlist and size cap**, and produce a `ContentFile` that saves through whichever
storage backend the model field declares. Validation happens at the field, not in the view.

---

## 8. Security checklist

- [ ] User data goes to **private** storage (`default_acl=None`); public storage is opt-in per field.
- [ ] `STORAGES["default"]` points at the private backend, so unspecified `FileField`s are private.
- [ ] Object keys are **tenant-partitioned** (`org/<id>/…`) and include a UUID.
- [ ] Private files served **only** via presigned URLs with a short expiry; the bucket has no public
      ACL and blocks public access.
- [ ] Uploads validate **mime type + size** (base64 fields, or explicit validators).
- [ ] Storage credentials come from env / IAM roles — never committed.
- [ ] Models use the `private_storage` / `public_storage` callables; `USE_AWS` toggles S3 ↔ local
      filesystem with no model or migration changes; CI uses local storage.
