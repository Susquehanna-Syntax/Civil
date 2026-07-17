"""The whole HTTP surface: login, SSO authorize, pubkey, whoami.

Civil never phones home, holds no license logic, and is not in any app's
hot path — it is consulted at login time only. Down Civil = no new logins;
everything already logged in keeps working on the products' own sessions.
"""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET

from .models import RegisteredApp, SigningKeyRecord
from .tokens import issue_sso_token


@require_GET
def pubkey(request):
    """The verification key apps cache. Public on purpose — it's a public key."""
    return JsonResponse({
        "issuer": "civil",
        "algorithm": "EdDSA",
        "public_key_pem": SigningKeyRecord.get().public_pem,
    })


@require_GET
@login_required
def authorize(request):
    """SSO handoff: ``/sso/authorize?app=vigil&redirect_uri=...&state=...``

    The redirect allowlist (RegisteredApp.redirect_base, admin-managed) is
    the security boundary — a token is only ever sent to a URL under a
    registered base, so a crafted link can't exfiltrate one. The token
    lives 60 seconds and is consumed once at the app's callback.
    """
    slug = request.GET.get("app", "")
    redirect_uri = request.GET.get("redirect_uri", "")
    state = request.GET.get("state", "")

    app = RegisteredApp.objects.filter(slug=slug, enabled=True).first()
    if app is None:
        return HttpResponseBadRequest(f"unknown or disabled app {slug!r}")
    if not redirect_uri.startswith(app.redirect_base):
        return HttpResponseBadRequest(
            "redirect_uri is not under this app's registered redirect base"
        )

    token = issue_sso_token(request.user, app.slug)
    sep = "&" if "?" in redirect_uri else "?"
    query = urlencode({"token": token, "state": state})
    from django.shortcuts import redirect
    response = redirect(f"{redirect_uri}{sep}{query}")
    # The token is single-use and 60s-lived, but still: no caches, anywhere.
    response["Cache-Control"] = "no-store"
    return response


@require_GET
@login_required
def whoami(request):
    u = request.user
    return JsonResponse({
        "sub": str(u.id),
        "username": u.username,
        "email": u.email,
        "name": u.get_full_name(),
        "orgs": [
            {"id": str(m.org.id), "slug": m.org.slug}
            for m in u.memberships.select_related("org")
        ],
    })
