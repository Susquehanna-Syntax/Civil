# Civil

Civil is the shared sign-in service for the SQSY apps (Vigil, Jackil, and
Turnstil). You create one account and one organization, and every app uses
them. Sites are also shared. When Vigil raises an alert and Jackil opens a
ticket for it, both point at the same site record.

**Version:** 2026.1.0

Civil handles identity only: users, organizations, sites, and sessions. It does
not manage roles or permissions, and it does not handle licenses or billing.
Each app keeps its own roles. Civil does not contact SQSY servers.

## Set up sign-in for your apps

Using Civil is optional. A single-container install works without it.

1. Deploy Civil with `docker compose up -d`, then create your admin account and users.
2. In the Django admin, add a **Registered app** for each product. Give it the
   callback address for that app, such as `https://vigil.lan/accounts/civil/callback`.
3. In each product, set its `*_CIVIL_URL` setting or environment variable to
   the address of your Civil server. Then turn on Civil sign-in in that product.

### How sign-in works

1. The app sends you to `/sso/authorize?app=<slug>&redirect_uri=…&state=…`.
2. Civil checks your session in the browser and sends you back to the app with
   a token. The token is signed with Ed25519 and expires after 60 seconds.
3. The app checks the token on its own, using the key it cached from
   `GET /api/v1/pubkey/`. It then starts its own Django session. The user is
   matched by their stable UUID (`sub`).

**If Civil is down, nobody can sign in to an app for the first time.** People who
are already signed in keep their sessions, and monitoring keeps running. Civil is
only needed at sign-in.

## Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /sso/authorize` | session | Issue a sign-in token. Only registered redirect addresses are allowed. |
| `GET /api/v1/pubkey/` | none | The key apps use to check tokens |
| `GET /api/v1/whoami/` | session | Your identity and organizations |
| `GET /api/v1/health/` | none | Health check |
| `/login/`, `/logout/`, `/admin/` | — | Sign-in pages for people |

## Run Civil

```bash
# Docker: set DJANGO_SECRET_KEY in .env first
docker compose up -d          # serves on port 8100; data and the JWT key are stored in the volume

# Development
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DJANGO_DEBUG=true .venv/bin/python manage.py migrate
DJANGO_DEBUG=true .venv/bin/python manage.py createsuperuser
DJANGO_DEBUG=true .venv/bin/python manage.py runserver

# Tests
DJANGO_DEBUG=true .venv/bin/python manage.py test
```

## Token format

Each token is an EdDSA JWT. It lasts 60 seconds and is limited to one registered app:

```json
{
  "iss": "civil", "aud": "vigil",
  "sub": "<stable user uuid>",
  "preferred_username": "...", "email": "...", "name": "...",
  "orgs": [{"id": "...", "slug": "..."}],
  "iat": 0, "exp": 0
}
```

Each app checks the token against the cached key. It finds the local account
through a `CivilIdentity` row that links the user's `sub` to the account. Local
IDs never change. Existing usernames are never linked automatically. After that,
the app starts its own normal session.

## Two-factor sign-in

Every Civil sign-in, including `/admin/`, needs a second factor after the
password. You can use one of these:

- A six-digit code from an authenticator app
- A security key or passkey
- One of ten one-time recovery codes

If you have no second factor, you set up an authenticator during your first
sign-in. You see your recovery codes once, so save them then.

To add a security key or passkey, go to the Security page. This needs
`MFA_PUBLIC_URL` set to the HTTPS address people use to reach Civil.

Staff can reset a person's second factor from that person's page in the console.
Apps treat a Civil sign-in as already using two factors, because Civil always
asks for one.

## Security notes

- Civil creates the JWT key pair on its first start, and stores it in the
  database. The data volume holds both your accounts and your keys. Back it up.
- Each sign-in token works for one app only and lasts 60 seconds. Civil sends a
  token only to a redirect address that starts with a registered base address.
- The token key is separate from the SQSY license signing key. Civil runs on your
  own infrastructure and signs only sign-in tokens.
