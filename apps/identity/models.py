"""Civil's entire data model: users, orgs, sites, sessions. Nothing else.

Scope is identity ONLY (SQSY-LICENSING.md §9). Roles, permissions, licenses,
seat billing, and anything touching the SQSY signing key are explicitly out —
roles stay per-product (Vigil's roles and Jackil's roles aren't the same
shape), and licenses live in the product that owns them. The moment Civil
owns authz, three products are blocked on one schema change, from two people.

Every PK is a UUID from day one so a local-auth install can migrate into
Civil (or back out) without ID reconciliation.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A person, shared across every SQSY app that opts into Civil.

    ``id`` is the stable identity apps key on — a Vigil user and a Jackil
    requester with the same UUID are the same human.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self) -> str:
        return self.username


class Org(models.Model):
    """An organization — the top-level administrative container."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Site(models.Model):
    """An administrative boundary — a campus, a department, a client org.

    Not a physical location. This is the ONE site concept spanning SQSY
    (§9): a Vigil alert and the Jackil ticket it opens reference the same
    site row, which is what makes the cross-product story real.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("org", "slug"), name="uniq_site_slug_per_org"),
        ]

    def __str__(self) -> str:
        return f"{self.org.slug}/{self.slug}"


class OrgMembership(models.Model):
    """User ↔ Org. Membership only — what a member may DO is each product's
    business (roles are per-product, permanently)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="memberships")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "org"), name="uniq_membership"),
        ]


class RegisteredApp(models.Model):
    """An SQSY app allowed to receive SSO tokens (Vigil, Jackil, Sigil, …).

    The redirect allowlist is the SSO security boundary: tokens are only ever
    sent to URLs under an admin-registered base. No dynamic registration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=50, unique=True)   # "vigil"
    name = models.CharField(max_length=100)
    redirect_base = models.URLField(
        help_text="SSO redirects must start with this exact prefix, "
        "e.g. https://vigil.example.com/accounts/civil/callback"
    )
    enabled = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.slug


class SigningKeyRecord(models.Model):
    """Civil's own Ed25519 JWT keypair — generated at first boot, one row.

    Unrelated to SQSY's license signing key in every way: different trust
    domain, different rotation cadence, and it lives on CUSTOMER infra.
    Private key stays in this DB; apps fetch and cache the public half from
    ``GET /api/v1/pubkey/`` so they can verify tokens locally while Civil is
    down (Civil down = no NEW logins, existing sessions keep working).
    """

    private_pem = models.TextField()
    public_pem = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get(cls) -> "SigningKeyRecord":
        row = cls.objects.order_by("created_at").first()
        if row is None:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
            from cryptography.hazmat.primitives import serialization

            key = Ed25519PrivateKey.generate()
            row = cls.objects.create(
                private_pem=key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ).decode(),
                public_pem=key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode(),
            )
        return row
