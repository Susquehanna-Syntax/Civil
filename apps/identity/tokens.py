"""JWT issuance — the contract every SQSY app verifies against.

Token shape (EdDSA/Ed25519, 60-second expiry for SSO handoff):

    {
      "iss": "civil",
      "aud": "<app slug>",          # the RegisteredApp this token is FOR
      "sub": "<user uuid>",         # the stable cross-app identity
      "preferred_username": "...",
      "email": "...",
      "name": "...",
      "orgs": [{"id": "...", "slug": "..."}],
      "iat": ..., "exp": ...
    }

Apps verify locally with the cached public key (``GET /api/v1/pubkey/``) —
no call to Civil in the hot path, so a down Civil never blocks an
already-issued token or an existing session. Short expiry is safe because
the token is consumed once, immediately, at the SSO callback; the app then
runs its own Django session as usual.
"""

from __future__ import annotations

import time

import jwt

from .models import SigningKeyRecord, User

ISSUER = "civil"
SSO_TOKEN_TTL_SECONDS = 60


def issue_sso_token(user: User, app_slug: str) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": app_slug,
        "sub": str(user.id),
        "preferred_username": user.username,
        "email": user.email,
        "name": user.get_full_name(),
        "orgs": [
            {"id": str(m.org.id), "slug": m.org.slug}
            for m in user.memberships.select_related("org")
        ],
        "iat": now,
        "exp": now + SSO_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(claims, SigningKeyRecord.get().private_pem, algorithm="EdDSA")


def verify_token(token: str, app_slug: str) -> dict:
    """Verify a token against our own key — used by tests and the whoami
    endpoint. Product apps use their own cached copy of the public key."""
    return jwt.decode(
        token,
        SigningKeyRecord.get().public_pem,
        algorithms=["EdDSA"],
        audience=app_slug,
        issuer=ISSUER,
    )
