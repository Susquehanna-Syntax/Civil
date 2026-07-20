# Civil

Shared identity for the SQSY family (Vigil, Jackil, Sigil, Turnstil): one
account, one org, one **site** concept across every app. A Vigil alert and
the Jackil ticket it opens point at the same site row — that's the ecosystem.

**Version:** 2026.1.0 · **Scope:** identity ONLY — users, orgs, sites,
sessions. No roles, no permissions, no licenses, no billing, ever. Roles
stay per-product. Civil never phones home.

## How apps use it (opt-in — single-container installs don't change)

1. Deploy Civil (`docker compose up -d`), create your admin + users.
2. In Django admin, add a **Registered app** per product with its callback
   redirect base (e.g. `https://vigil.lan/accounts/civil/callback`).
3. In each product, set its `*_CIVIL_URL` setting/env to point here and
   enable Civil auth.

Login flow: the app redirects to `/sso/authorize?app=<slug>&redirect_uri=…
&state=…`; Civil authenticates the browser session and redirects back with
a 60-second Ed25519-signed JWT; the app verifies it **locally** against the
cached key from `GET /api/v1/pubkey/` and starts its own normal Django
session, provisioning the user by their stable UUID (`sub`).

**Civil down = no new logins.** Existing sessions in every app keep
working, monitoring never blinks. Civil is consulted at login time only.

## Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /sso/authorize` | session | Issue the SSO handoff token (allowlisted redirects only) |
| `GET /api/v1/pubkey/` | none | The JWT verification key apps cache |
| `GET /api/v1/whoami/` | session | Current identity + orgs |
| `GET /api/v1/health/` | none | Liveness |
| `/login/`, `/logout/`, `/admin/` | — | Humans |

## Running it

```bash
# Docker (production-ish): set DJANGO_SECRET_KEY in .env first
docker compose up -d          # serves on :8100, data + JWT key in the volume

# Development
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DJANGO_DEBUG=true .venv/bin/python manage.py migrate
DJANGO_DEBUG=true .venv/bin/python manage.py createsuperuser
DJANGO_DEBUG=true .venv/bin/python manage.py runserver

# Tests
DJANGO_DEBUG=true .venv/bin/python manage.py test
```

## Token contract (what apps verify)

60-second EdDSA JWT, audience-bound to one registered app:

```json
{
  "iss": "civil", "aud": "vigil",
  "sub": "<stable user uuid>",
  "preferred_username": "...", "email": "...", "name": "...",
  "orgs": [{"id": "...", "slug": "..."}],
  "iat": 0, "exp": 0
}
```

Every SQSY app carries the same `civilsso` client app (Vigil, Jackil, Sigil,
Turnstil): it verifies locally against the cached key, maps `sub` to a local
account via a CivilIdentity row (local PKs never change, existing usernames
are never auto-claimed), and runs its own normal Django session from there.

## Security notes

- The JWT keypair is generated at Civil's first boot and lives in the DB —
  the data volume is both your identity store and your key store. Back it up.
- SSO tokens are audience-bound to one app, 60-second-lived, and only ever
  sent to admin-registered redirect bases (exact prefix match).
- This key has nothing to do with SQSY's license signing key. Different
  trust domain; Civil runs on *your* infrastructure and signs only logins.
