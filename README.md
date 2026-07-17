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

## Security notes

- The JWT keypair is generated at Civil's first boot and lives in the DB —
  the data volume is both your identity store and your key store. Back it up.
- SSO tokens are audience-bound to one app, 60-second-lived, and only ever
  sent to admin-registered redirect bases (exact prefix match).
- This key has nothing to do with SQSY's license signing key. Different
  trust domain; Civil runs on *your* infrastructure and signs only logins.
