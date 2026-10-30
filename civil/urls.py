from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import include, path

from apps.identity import console
from apps.identity import views as identity
from apps.mfa.admin_guard import admin_login_redirect
from apps.mfa.views import MfaLoginView


def health(request):
    return JsonResponse({"status": "ok", "service": "civil"})


urlpatterns = [
    # The admin's own password form is not a second factor: anonymous and
    # plain-password sessions go through Civil's two-step sign-in instead.
    path("admin/login/", admin_login_redirect, name="admin-login"),
    path("admin/", admin.site.urls),
    path("login/", MfaLoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("mfa/", include("apps.mfa.urls")),
    path("password/", console.PasswordChangeView.as_view(), name="password"),
    path("console/", include("civil.console_urls")),
    path("sso/authorize", identity.authorize, name="sso-authorize"),
    path("api/v1/pubkey/", identity.pubkey, name="pubkey"),
    path("api/v1/whoami/", identity.whoami, name="whoami"),
    path("api/v1/health/", health, name="health"),
    path("", console.home, name="home"),
]
