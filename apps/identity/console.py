"""The pages people use: a home that lists your apps, and a staff console
for people, apps and organisations. Reading a section needs its view
permission and changing it the matching add/change/delete one, as in the
Django admin; every change is logged to the admin's history."""

import uuid
from functools import wraps
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from .forms import AppForm, OrgForm, PersonForm, SiteForm
from .models import Org, OrgMembership, RegisteredApp, Site, User


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def _need(request, action, model):
    if not request.user.has_perm(f"identity.{action}_{model}"):
        raise PermissionDenied


def _need_view(request, model):
    if not (request.user.has_perm(f"identity.view_{model}")
            or request.user.has_perm(f"identity.change_{model}")):
        raise PermissionDenied


def _log(request, obj, flag, message):
    LogEntry.objects.log_actions(request.user.pk, [obj], flag, change_message=message,
                                 single_object=True)


def app_home(app):
    """Where to send someone opening an app: the origin of its callback."""
    parts = urlparse(app.redirect_base)
    return f"{parts.scheme}://{parts.netloc}/"


@login_required
def home(request):
    apps = [{"app": a, "url": app_home(a)}
            for a in RegisteredApp.objects.filter(enabled=True).order_by("name")]
    orgs = Org.objects.filter(memberships__user=request.user).annotate(
        site_count=Count("sites", distinct=True)).order_by("name")
    return render(request, "console/home.html", {"apps": apps, "orgs": orgs})


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "console/password.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        messages.success(self.request, "Password changed.")
        return super().form_valid(form)


# -- People ------------------------------------------------------------------

@staff_required
def people(request):
    _need_view(request, "user")
    q = request.GET.get("q", "").strip()
    users = User.objects.prefetch_related("memberships__org").order_by("username")
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q)
                             | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    return render(request, "console/people.html", {"users": users, "q": q})


def _may_edit(request, person):
    """Only a superuser edits a superuser: anyone else could take one over
    by setting its password."""
    return not person.is_superuser or request.user.is_superuser


@staff_required
def person_edit(request, pk=None):
    person = get_object_or_404(User, pk=pk) if pk else None
    _need(request, "change" if person else "add", "user")
    if person and not _may_edit(request, person):
        raise PermissionDenied
    editing_self = person is not None and person.pk == request.user.pk
    form = PersonForm(request.POST or None, instance=person,
                      can_grant_staff=request.user.is_superuser, editing_self=editing_self)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        if editing_self and form.cleaned_data.get("password"):
            update_session_auth_hash(request, saved)
        _log(request, saved, CHANGE if person else ADDITION,
             "Changed in the console." if person else "Added in the console.")
        messages.success(request, f"Saved {saved.username}.")
        return redirect("console-people")
    return render(request, "console/person_form.html", {
        "form": form, "person": person, "editing_self": editing_self,
        "can_reset_mfa": (person is not None and not editing_self
                          and request.user.has_perm("identity.change_user")
                          and _may_edit(request, person))})


# -- Apps --------------------------------------------------------------------

@staff_required
def apps(request):
    _need_view(request, "registeredapp")
    rows = [{"app": a, "url": app_home(a)} for a in RegisteredApp.objects.order_by("name")]
    return render(request, "console/apps.html", {"rows": rows})


@staff_required
def app_edit(request, pk=None):
    app = get_object_or_404(RegisteredApp, pk=pk) if pk else None
    _need(request, "change" if app else "add", "registeredapp")
    form = AppForm(request.POST or None, instance=app)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        _log(request, saved, CHANGE if app else ADDITION, "Saved in the console.")
        messages.success(request, f"Saved {saved.name}.")
        return redirect("console-apps")
    return render(request, "console/app_form.html", {"form": form, "app": app})


@staff_required
@require_POST
def app_toggle(request, pk):
    _need(request, "change", "registeredapp")
    app = get_object_or_404(RegisteredApp, pk=pk)
    app.enabled = not app.enabled
    app.save(update_fields=["enabled"])
    state = "allowed" if app.enabled else "stopped"
    _log(request, app, CHANGE, f"Sign-ins {state} in the console.")
    messages.success(request, f"Sign-ins to {app.name} {state}.")
    return redirect("console-apps")


# -- Organisations -----------------------------------------------------------

@staff_required
def orgs(request):
    _need_view(request, "org")
    rows = Org.objects.annotate(member_count=Count("memberships", distinct=True),
                                site_count=Count("sites", distinct=True)).order_by("name")
    return render(request, "console/orgs.html", {"orgs": rows})


@staff_required
def org_edit(request, pk=None):
    org = get_object_or_404(Org, pk=pk) if pk else None
    _need(request, "change" if org else "add", "org")
    form = OrgForm(request.POST or None, instance=org)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        _log(request, saved, CHANGE if org else ADDITION, "Saved in the console.")
        messages.success(request, f"Saved {saved.name}.")
        return redirect("console-org", pk=saved.pk)
    return render(request, "console/org_form.html", {"form": form, "org": org})


@staff_required
def org_detail(request, pk):
    _need_view(request, "org")
    org = get_object_or_404(Org, pk=pk)
    site_form = SiteForm(org=org)
    if request.method == "POST":
        _need(request, "add", "site")
        site_form = SiteForm(request.POST, org=org)
        if site_form.is_valid():
            site = site_form.save()
            _log(request, site, ADDITION, "Added in the console.")
            messages.success(request, f"Added the site {site.name}.")
            return redirect("console-org", pk=org.pk)
    members = org.memberships.select_related("user").order_by("user__username")
    member_ids = members.values_list("user_id", flat=True)
    return render(request, "console/org_detail.html", {
        "org": org, "sites": org.sites.order_by("name"), "members": members,
        "site_form": site_form,
        "others": User.objects.exclude(pk__in=member_ids).filter(is_active=True)
                              .order_by("username"),
        "can_change": request.user.has_perm("identity.change_org"),
    })


@staff_required
@require_POST
def site_delete(request, pk, site_pk):
    _need(request, "delete", "site")
    site = get_object_or_404(Site, pk=site_pk, org_id=pk)
    _log(request, site, DELETION, "Deleted in the console.")
    site.delete()
    messages.success(request, f"Deleted the site {site.name}.")
    return redirect("console-org", pk=pk)


@staff_required
@require_POST
def member_add(request, pk):
    _need(request, "change", "org")
    org = get_object_or_404(Org, pk=pk)
    try:
        user = get_object_or_404(User, pk=uuid.UUID(request.POST.get("user", "")))
    except ValueError:
        raise Http404 from None
    OrgMembership.objects.get_or_create(user=user, org=org)
    _log(request, org, CHANGE, f"Added {user.username} in the console.")
    messages.success(request, f"Added {user.username}.")
    return redirect("console-org", pk=pk)


@staff_required
@require_POST
def member_remove(request, pk, user_pk):
    _need(request, "change", "org")
    org = get_object_or_404(Org, pk=pk)
    membership = get_object_or_404(OrgMembership, org=org, user_id=user_pk)
    username = membership.user.username
    membership.delete()
    _log(request, org, CHANGE, f"Removed {username} in the console.")
    messages.success(request, f"Removed {username}.")
    return redirect("console-org", pk=pk)
