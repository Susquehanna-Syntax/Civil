"""The second step of signing in: every account proves a second factor.

A correct password no longer signs anyone in. It parks the user's id in the
session as *pending* and sends the browser to ``/mfa/verify/``, where one of
two things finishes the sign-in:

  * a six-digit TOTP code, or an unused recovery code,
  * for an account with neither, enrolling TOTP right there — scan, confirm a
    code — before Civil opens. The enrolment code IS the second factor, so the
    recovery codes handed out afterwards cannot open a door on their own; they
    are shown once, to be read, and not asked for again until the phone is gone.

``auth.login`` is only ever called from here, after a factor checks out, so a
pending session is an anonymous session in every other view: the API, the
console and SSO all see no user.

Guesses count against the same per-user code limit the security page uses,
so the second step cannot be brute-forced from the sign-in page either.
"""

import time

from django.contrib import auth, messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from . import conf, recovery
from .models import MfaProfile
from .qr import totp_qr_svg
from .totp import (
    confirm_secret,
    consume_totp,
    generate_secret,
    has_second_factor,
    otpauth_uri,
)

PENDING_KEY = "mfa_pending"
ENROL_KEY = "mfa_enrol_secret"
FRESH_CODES_KEY = "mfa:fresh_codes"
AFTER_CODES_KEY = "mfa:after_codes"
#: Long enough to find a phone; short enough that a password typed on a shared
#: machine and walked away from does not stay half signed in.
PENDING_SECONDS = 300


def safe_next(request, candidate: str) -> str:
    """Same-host relative targets only; anything else is an open redirect."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}
    ):
        return candidate
    return "/"


def begin(request, user, next_url: str = "/", backend: str = ""):
    """Park ``user`` as pending and send the browser to the second step."""
    request.session.pop(ENROL_KEY, None)
    request.session[PENDING_KEY] = {
        "uid": str(user.pk),
        "exp": time.time() + PENDING_SECONDS,
        "next": safe_next(request, next_url),
        "backend": backend or getattr(user, "backend", "")
        or "django.contrib.auth.backends.ModelBackend",
    }
    return redirect("mfa:verify")


def _pending(request):
    """(user, state) for a live pending sign-in, or (None, None)."""
    state = request.session.get(PENDING_KEY) or {}
    if not state or _expired(state):
        _forget(request)
        return None, None
    user = get_user_model().objects.filter(pk=state.get("uid"), is_active=True).first()
    if user is None:
        _forget(request)
        return None, None
    return user, state


def _expired(state) -> bool:
    """Whether a parked sign-in outlived ``PENDING_SECONDS``.

    The deadline is wall-clock (``time.time()``) because that is the clock the
    one-time codes are cut on; comparing it against anything else — an aware
    datetime, say — would expire every pending sign-in at once or none at all.
    """
    return not state or time.time() >= (state.get("exp") or 0)


def _forget(request) -> None:
    request.session.pop(PENDING_KEY, None)
    request.session.pop(ENROL_KEY, None)


def _finish(request, user, state) -> str:
    """Sign in for real. Returns where to go next."""
    _forget(request)
    auth.login(request, user, backend=state["backend"])
    return state.get("next") or "/"


def verify(request):
    """The second step. Enrolment for a factor-less account happens on the
    setup page, which confirms a code before it replaces anything — and signs
    a pending user in once that code checks out."""
    user, state = _pending(request)
    if user is None:
        return redirect("login")

    if not has_second_factor(user):
        return setup(request)

    error = None
    if request.method == "POST":
        ok, err = consume_totp(user, request.POST.get("code", ""))
        if ok:
            return redirect(_finish(request, user, state))
        error = err

    return render(
        request,
        "mfa/verify.html",
        {"error": error, "username": user.get_username()},
        status=400 if error else 200,
    )


def codes(request):
    """The fresh recovery codes — shown once, then gone from the session."""
    fresh = request.session.get(FRESH_CODES_KEY)
    user, _state = _pending(request)
    if not fresh:
        return redirect("mfa:verify" if user else "home")
    if request.method == "POST":
        request.session.pop(FRESH_CODES_KEY, None)
        after = request.session.pop(AFTER_CODES_KEY, None)
        if user is None:
            return redirect(after or "mfa:security")
        # Codes alone don't sign anyone in — except when reading them *is* what
        # finished the step: an account that enrolled on its way through has
        # already answered with the enrolment code, and its pending state is
        # still parked. Sign that one in here, at the last click.
        return redirect(_finish(request, user, _state))

    return render(
        request,
        "mfa/codes.html",
        {"codes": fresh, "pending": user is not None},
    )


class MfaLoginView(auth_views.LoginView):
    """The password step. A correct password only *starts* a sign-in."""

    template_name = "login.html"

    def form_valid(self, form):
        user = form.get_user()
        backend = getattr(user, "backend", "")
        if not conf.required(user) or backend in conf.trusted_backends():
            return super().form_valid(form)
        # Park the user as pending instead of signing them in.
        return begin(
            self.request,
            user,
            self.get_redirect_url() or self.get_default_redirect_url(),
            backend,
        )


# -- The signed-in security page ---------------------------------------------


def _confirmed_for_post(request, user) -> bool:
    """Every action that changes a factor needs a code from the current one."""
    ok, err = consume_totp(user, request.POST.get("code", ""))
    if not ok:
        messages.error(request, err or "That code didn't match.")
    return ok


@login_required
def security(request):
    user = request.user
    profile = MfaProfile.objects.filter(user=user).first()
    has_authenticator = bool(profile is not None and profile.confirmed())
    if request.method == "POST" and has_authenticator:
        action = request.POST.get("action", "")
        if action == "codes":
            if _confirmed_for_post(request, user):
                request.session[FRESH_CODES_KEY] = recovery.make_codes(user)
                return redirect("mfa:codes")
        elif action == "setup" and _confirmed_for_post(request, user):
            # The old secret stays until the new one checks out on setup.
            request.session[ENROL_KEY] = generate_secret()
            return redirect("mfa:setup")

    return render(
        request,
        "mfa/security_page.html",
        {
            "has_authenticator": has_authenticator,
            "recovery_remaining": recovery.remaining(user),
        },
    )
def setup(request):
    """A new authenticator, confirmed with a code before the old secret is
    replaced. A signed-in user arrives from the security page; a pending
    sign-in arrives from ``verify`` for an account with no factor yet.

    The confirm-before-replace order is what makes recovery codes generated
    during enrolment harmless on their own: they are shown, but the sign-in
    still waits for a code from the authenticator that was just enrolled.
    """
    if request.user.is_authenticated:
        user, state = request.user, None
    else:
        user, state = _pending(request)
    if user is None:
        return redirect("login")

    secret = request.session.get(ENROL_KEY)
    if not secret:
        secret = generate_secret()
        request.session[ENROL_KEY] = secret

    error = None
    if request.method == "POST":
        ok, error = confirm_secret(user, secret, request.POST.get("code", ""))
        if ok:
            request.session.pop(ENROL_KEY, None)
            # A new authenticator comes with a new set of recovery codes: the
            # old set may have been written down beside the phone just lost.
            codes = recovery.make_codes(user)
            after = "mfa:security"
            if state is not None:
                after = _finish(request, user, state)
            request.session[FRESH_CODES_KEY] = codes
            request.session[AFTER_CODES_KEY] = after
            messages.success(request, "Authenticator set up.")
            return redirect("mfa:codes")

    return render(
        request,
        "mfa/setup.html",
        {
            "error": error,
            "totp_secret": secret,
            "totp_qr_svg": totp_qr_svg(otpauth_uri(secret, user.get_username())),
        },
        status=400 if error else 200,
    )
