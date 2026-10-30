"""The staff reset of a person's two-factor sign-in, from their person page.

The rule is the console's own — staff with ``change_user`` via ``_need``, and
only a superuser touches a superuser (``_may_edit``) — and never on your own
account: clearing your own factors is what the security page is for, which is
why this answers a refusal rather than a redirect. The person may be someone
who cannot sign in at all, so nothing here goes through ``login_required``;
``_need`` does the staff gate.
"""

from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from .console import _log, _may_edit, _need
from .models import User


def person_mfa_reset(request, pk):
    """POST only: reached from a button on the person page."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _need(request, "change", "user")
    person = get_object_or_404(User, pk=pk)
    if not _may_edit(request, person):
        return HttpResponseForbidden("You cannot reset that person's two-factor sign-in.")
    if person.pk == request.user.pk:
        return HttpResponseForbidden("You cannot reset your own two-factor sign-in here.")

    from apps.mfa.service import reset as reset_mfa

    reset_mfa(person)
    _log(request, person, CHANGE, "Two-factor sign-in reset in the console.")
    messages.success(request, "Reset. They will set it up again at their next sign-in.")
    return redirect("console-person", pk=pk)
