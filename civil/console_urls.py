from django.urls import path

from apps.identity import console
from apps.identity.mfa_reset import person_mfa_reset

urlpatterns = [
    path("people/", console.people, name="console-people"),
    path("people/new/", console.person_edit, name="console-person-new"),
    path("people/<uuid:pk>/", console.person_edit, name="console-person"),
    path("people/<uuid:pk>/mfa-reset/", person_mfa_reset, name="console-person-mfa-reset"),
    path("apps/", console.apps, name="console-apps"),
    path("apps/new/", console.app_edit, name="console-app-new"),
    path("apps/<uuid:pk>/", console.app_edit, name="console-app"),
    path("apps/<uuid:pk>/toggle/", console.app_toggle, name="console-app-toggle"),
    path("orgs/", console.orgs, name="console-orgs"),
    path("orgs/new/", console.org_edit, name="console-org-new"),
    path("orgs/<uuid:pk>/", console.org_detail, name="console-org"),
    path("orgs/<uuid:pk>/edit/", console.org_edit, name="console-org-edit"),
    path("orgs/<uuid:pk>/sites/<uuid:site_pk>/delete/", console.site_delete, name="console-site-delete"),
    path("orgs/<uuid:pk>/members/", console.member_add, name="console-member-add"),
    path("orgs/<uuid:pk>/members/<uuid:user_pk>/remove/", console.member_remove,
         name="console-member-remove"),
]
